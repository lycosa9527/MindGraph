#include "super_kitty_audio.hpp"

#include <atomic>
#include <cstring>
#include <mutex>
#include <vector>

#include "esp_heap_caps.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#include "super_kitty_wake.hpp"

#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
#include "brookesia/hal_interface/interface.hpp"
#include "brookesia/hal_interface/interfaces/audio/processor.hpp"
#endif

namespace {

constexpr const char *TAG = "skitty_audio";
constexpr size_t k_ring_samples = 16000 * 2;
constexpr uint32_t k_fetch_interval_ms = 10;
constexpr uint32_t k_fetch_bytes = 1024;
constexpr uint32_t k_fetch_stack = 8 * 1024;
constexpr UBaseType_t k_fetch_prio = 6;

#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
using EncoderIface = esp_brookesia::hal::audio::EncoderIface;
using EncoderHandle = esp_brookesia::hal::InterfaceHandle<EncoderIface>;

EncoderHandle g_encoder;
#endif

std::mutex g_ring_mutex;
std::vector<int16_t> g_ring;
size_t g_ring_w = 0;
size_t g_ring_r = 0;
size_t g_ring_n = 0;
std::atomic<uint8_t> g_level{0};
std::atomic<bool> g_afe_on{false};
std::atomic<bool> g_started{false};
std::atomic<bool> g_pcm_seen{false};
std::atomic<bool> g_fetch_stop{false};
TaskHandle_t g_fetch_task = nullptr;

void ring_push(const int16_t *samples, size_t count)
{
    if (samples == nullptr || count == 0) {
        return;
    }
    std::lock_guard<std::mutex> lock(g_ring_mutex);
    if (g_ring.size() < k_ring_samples) {
        g_ring.assign(k_ring_samples, 0);
    }
    for (size_t i = 0; i < count; ++i) {
        if (g_ring_n == k_ring_samples) {
            g_ring_r = (g_ring_r + 1) % k_ring_samples;
            --g_ring_n;
        }
        g_ring[g_ring_w] = samples[i];
        g_ring_w = (g_ring_w + 1) % k_ring_samples;
        ++g_ring_n;
    }
}

size_t ring_pop(int16_t *samples, size_t count)
{
    std::lock_guard<std::mutex> lock(g_ring_mutex);
    const size_t n = count < g_ring_n ? count : g_ring_n;
    for (size_t i = 0; i < n; ++i) {
        samples[i] = g_ring[g_ring_r];
        g_ring_r = (g_ring_r + 1) % k_ring_samples;
    }
    g_ring_n -= n;
    return n;
}

void update_level(const int16_t *samples, size_t count)
{
    int peak = 0;
    for (size_t i = 0; i < count; ++i) {
        int amp = samples[i];
        if (amp < 0) {
            amp = -amp;
        }
        if (amp > peak) {
            peak = amp;
        }
    }
    g_level.store(static_cast<uint8_t>(peak > 32767 ? 255 : peak / 128));
}

void accept_afe_pcm(const uint8_t *data, size_t size)
{
    if (data == nullptr || size < 2) {
        return;
    }
    const size_t count = size / sizeof(int16_t);
    const auto *samples = reinterpret_cast<const int16_t *>(data);
    update_level(samples, count);
    super_kitty_wake_feed(samples, count);
    ring_push(samples, count);
    if (!g_pcm_seen.exchange(true)) {
        ESP_LOGI(TAG, "AFE pcm live bytes=%u", static_cast<unsigned>(size));
    }
}

#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
void on_afe_event(esp_brookesia::hal::audio::AfeEvent event)
{
    ESP_LOGI(TAG, "afe event=%u", static_cast<unsigned>(event));
}

void on_raw_i2s(const uint8_t *data, size_t size)
{
    (void)data;
    if (size == 0) {
        return;
    }
}

void fetch_task(void *arg)
{
    (void)arg;
    std::vector<uint8_t> buf(k_fetch_bytes, 0);
    while (!g_fetch_stop.load()) {
        int got = 0;
        if (g_encoder && g_encoder->is_started()) {
            got = g_encoder->read_encoded_data(buf.data(), buf.size());
        }
        if (got >= 2) {
            accept_afe_pcm(buf.data(), static_cast<size_t>(got));
        } else {
            vTaskDelay(pdMS_TO_TICKS(k_fetch_interval_ms));
        }
    }
    g_fetch_task = nullptr;
    vTaskDelete(nullptr);
}

bool start_fetch_task()
{
    if (g_fetch_task != nullptr) {
        return true;
    }
    g_fetch_stop.store(false);
    const BaseType_t ok = xTaskCreatePinnedToCore(
        fetch_task,
        "skitty_afe",
        k_fetch_stack,
        nullptr,
        k_fetch_prio,
        &g_fetch_task,
        1
    );
    if (ok != pdPASS) {
        g_fetch_task = nullptr;
        ESP_LOGE(TAG, "AFE fetch task create failed");
        return false;
    }
    ESP_LOGI(TAG, "AFE fetch pump started prio=%u", static_cast<unsigned>(k_fetch_prio));
    return true;
}

void stop_fetch_task()
{
    g_fetch_stop.store(true);
    for (int i = 0; i < 50 && g_fetch_task != nullptr; ++i) {
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    if (g_fetch_task != nullptr) {
        ESP_LOGW(TAG, "AFE fetch task still running after stop");
    }
}
#endif

} // namespace

bool super_kitty_audio_init()
{
    g_ring.assign(k_ring_samples, 0);
    g_ring_w = 0;
    g_ring_r = 0;
    g_ring_n = 0;
    g_pcm_seen.store(false);
#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    g_encoder = esp_brookesia::hal::acquire_first_interface<EncoderIface>();
    if (g_encoder) {
        ESP_LOGI(TAG, "AFE encoder ready");
        return true;
    }
    ESP_LOGE(TAG, "AFE encoder missing");
#endif
    return false;
}

bool super_kitty_audio_start()
{
    if (g_started.load()) {
        return true;
    }
#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    if (!g_encoder) {
        ESP_LOGE(TAG, "AFE encoder not acquired");
        return false;
    }
    using esp_brookesia::hal::audio::CodecFormat;
    using esp_brookesia::hal::audio::EncoderDynamicConfig;
    EncoderDynamicConfig config{};
    config.type = CodecFormat::PCM;
    config.general.channels = 1;
    config.general.sample_bits = 16;
    config.general.sample_rate = 16000;
    config.general.frame_duration = 100;
    config.fetch_interval_ms = k_fetch_interval_ms;
    config.fetch_data_size = k_fetch_bytes;
    config.enable_afe = true;
    EncoderIface::Callbacks callbacks;
    callbacks.afe_event = on_afe_event;
    callbacks.recorder_data = on_raw_i2s;
    if (!g_encoder->is_started()) {
        ESP_LOGI(
            TAG,
            "AFE start internal=%u psram=%u",
            static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),
            static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM))
        );
        if (!g_encoder->start(config, callbacks)) {
            ESP_LOGE(TAG, "AFE encoder start failed");
            return false;
        }
    } else {
        ESP_LOGW(TAG, "AFE encoder already running; attaching fetch pump");
    }
    if (!start_fetch_task()) {
        if (g_encoder->is_started()) {
            g_encoder->stop();
        }
        return false;
    }
    g_afe_on.store(true);
    g_started.store(true);
    ESP_LOGI(TAG, "AFE capture started (dual-mic AEC)");
    return true;
#else
    ESP_LOGE(TAG, "audio HAL disabled");
    return false;
#endif
}

void super_kitty_audio_stop()
{
#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    g_fetch_stop.store(true);
    if (g_encoder && g_encoder->is_started()) {
        g_encoder->stop();
    }
    stop_fetch_task();
#endif
    g_afe_on.store(false);
    g_started.store(false);
    super_kitty_audio_clear();
}

bool super_kitty_audio_read(int16_t *samples, size_t count)
{
    if (samples == nullptr || count == 0) {
        return false;
    }
    if (!g_afe_on.load()) {
        return false;
    }
    const size_t got = ring_pop(samples, count);
    if (got < count) {
        std::memset(samples + got, 0, (count - got) * sizeof(int16_t));
    }
    return got > 0;
}

uint8_t super_kitty_audio_level()
{
    return g_level.load();
}

void super_kitty_audio_clear()
{
    std::lock_guard<std::mutex> lock(g_ring_mutex);
    g_ring_w = 0;
    g_ring_r = 0;
    g_ring_n = 0;
}

bool super_kitty_audio_using_afe()
{
    return g_afe_on.load();
}
