#include "super_kitty_wake.hpp"

#include <atomic>
#include <mutex>
#include <vector>

#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#if !CONFIG_SR_MN_EN_NONE
#include "esp_mn_iface.h"
#include "esp_mn_models.h"
#include "esp_mn_speech_commands.h"
#include "model_path.h"
#endif

namespace {

constexpr const char *TAG = "skitty_wake";
constexpr const char *k_address = "ni hao kitty";
constexpr const char *k_address_phonemes = "Nm ht KgTm";
constexpr size_t k_feed_cap = 16000;

std::atomic<bool> g_addressed{false};
std::atomic<bool> g_ignore{false};
std::atomic<bool> g_ready{false};
std::atomic<bool> g_create_done{false};
#if !CONFIG_SR_MN_EN_NONE
constexpr size_t k_mn_psram_need = 2400 * 1024;
constexpr uint32_t k_mn_stack = 12 * 1024;
constexpr UBaseType_t k_mn_prio = 2;
std::atomic<bool> g_mn_stop{false};
TaskHandle_t g_mn_task = nullptr;
StaticTask_t *g_mn_tcb = nullptr;
StackType_t *g_mn_stack_mem = nullptr;
std::mutex g_mn_mutex;
std::mutex g_feed_mutex;
const esp_mn_iface_t *g_mn = nullptr;
model_iface_data_t *g_mn_data = nullptr;
srmodel_list_t *g_models = nullptr;
int g_chunk = 0;
int16_t *g_feed = nullptr;
size_t g_feed_w = 0;
size_t g_feed_r = 0;
size_t g_feed_n = 0;
std::vector<int16_t> g_chunk_buf;

bool feed_alloc()
{
    if (g_feed != nullptr) {
        return true;
    }
    g_feed = static_cast<int16_t *>(heap_caps_malloc(
        k_feed_cap * sizeof(int16_t),
        MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT
    ));
    if (g_feed == nullptr) {
        g_feed = static_cast<int16_t *>(heap_caps_malloc(
            k_feed_cap * sizeof(int16_t),
            MALLOC_CAP_8BIT
        ));
    }
    if (g_feed == nullptr) {
        ESP_LOGE(TAG, "wake feed ring alloc failed");
        return false;
    }
    return true;
}

void feed_free()
{
    std::lock_guard<std::mutex> lock(g_feed_mutex);
    heap_caps_free(g_feed);
    g_feed = nullptr;
}

void feed_push(const int16_t *samples, size_t count)
{
    std::lock_guard<std::mutex> lock(g_feed_mutex);
    if (g_feed == nullptr) {
        return;
    }
    for (size_t i = 0; i < count; ++i) {
        if (g_feed_n == k_feed_cap) {
            g_feed_r = (g_feed_r + 1) % k_feed_cap;
            --g_feed_n;
        }
        g_feed[g_feed_w] = samples[i];
        g_feed_w = (g_feed_w + 1) % k_feed_cap;
        ++g_feed_n;
    }
}

bool feed_take_chunk(int16_t *dest, size_t count)
{
    std::lock_guard<std::mutex> lock(g_feed_mutex);
    if (g_feed == nullptr) {
        return false;
    }
    if (g_feed_n < count) {
        return false;
    }
    for (size_t i = 0; i < count; ++i) {
        dest[i] = g_feed[g_feed_r];
        g_feed_r = (g_feed_r + 1) % k_feed_cap;
    }
    g_feed_n -= count;
    return true;
}

void feed_clear()
{
    std::lock_guard<std::mutex> lock(g_feed_mutex);
    g_feed_w = 0;
    g_feed_r = 0;
    g_feed_n = 0;
}

void detect_chunk(int16_t *samples)
{
    std::lock_guard<std::mutex> lock(g_mn_mutex);
    if (g_mn == nullptr || g_mn_data == nullptr || g_ignore.load()) {
        return;
    }
    const esp_mn_state_t state = g_mn->detect(g_mn_data, samples);
    if (state == ESP_MN_STATE_DETECTED) {
        g_addressed.store(true);
        ESP_LOGI(TAG, "MultiNet address hit");
    }
}

bool register_address()
{
    if (esp_mn_commands_alloc(g_mn, g_mn_data) != ESP_OK) {
        ESP_LOGE(TAG, "MultiNet command alloc failed");
        return false;
    }
    if (esp_mn_commands_phoneme_add(1, k_address, k_address_phonemes) != ESP_OK) {
        ESP_LOGE(TAG, "MultiNet rejected %s phonemes=%s", k_address, k_address_phonemes);
        esp_mn_commands_free();
        return false;
    }
    if (esp_mn_commands_update() != nullptr) {
        ESP_LOGE(TAG, "MultiNet command update failed");
        esp_mn_commands_free();
        return false;
    }
    return true;
}

void log_heap(const char *where)
{
    ESP_LOGI(
        TAG,
        "%s internal=%u psram=%u largest=%u",
        where,
        static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),
        static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)),
        static_cast<unsigned>(heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM))
    );
}

bool psram_can_hold_multinet()
{
    const size_t largest = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
    if (largest >= k_mn_psram_need) {
        return true;
    }
    ESP_LOGE(TAG, "skip MultiNet create; PSRAM largest block=%u", static_cast<unsigned>(largest));
    return false;
}

void destroy_multinet(bool free_commands)
{
    std::lock_guard<std::mutex> lock(g_mn_mutex);
    if (free_commands && g_mn_data != nullptr) {
        esp_mn_commands_free();
    }
    if (g_mn != nullptr && g_mn_data != nullptr) {
        g_mn->destroy(g_mn_data);
    }
    g_mn_data = nullptr;
    g_mn = nullptr;
    g_chunk_buf.clear();
    if (g_models != nullptr) {
        esp_srmodel_deinit(g_models);
        g_models = nullptr;
    }
}

bool create_multinet()
{
    log_heap("mn before create");
    if (!psram_can_hold_multinet()) {
        return false;
    }
    if (!feed_alloc()) {
        return false;
    }
    feed_clear();
    g_models = esp_srmodel_init("model");
    char *name = nullptr;
    if (g_models != nullptr) {
        name = esp_srmodel_filter(g_models, ESP_MN_PREFIX, ESP_MN_ENGLISH);
    }
    if (name == nullptr) {
        ESP_LOGW(TAG, "no English MultiNet in model partition");
        destroy_multinet(false);
        return false;
    }
    g_mn = esp_mn_handle_from_name(name);
    if (g_mn == nullptr) {
        ESP_LOGE(TAG, "MultiNet handle missing name=%s", name);
        destroy_multinet(false);
        return false;
    }
    g_mn_data = g_mn->create(name, 6000);
    if (g_mn_data == nullptr) {
        ESP_LOGE(TAG, "MultiNet create failed");
        g_mn = nullptr;
        destroy_multinet(false);
        return false;
    }
    g_chunk = g_mn->get_samp_chunksize(g_mn_data);
    if (g_chunk <= 0) {
        g_chunk = 512;
    }
    g_chunk_buf.assign(static_cast<size_t>(g_chunk), 0);
    if (!register_address()) {
        destroy_multinet(false);
        return false;
    }
    log_heap("mn after create");
    ESP_LOGI(TAG, "MultiNet ready name=%s chunk=%d phrase=%s", name, g_chunk, k_address);
    return true;
}

void poll_detect()
{
    if (!g_ready.load() || g_chunk <= 0 || g_chunk_buf.size() < static_cast<size_t>(g_chunk)) {
        return;
    }
    int steps = 0;
    while (steps < 4 && feed_take_chunk(g_chunk_buf.data(), static_cast<size_t>(g_chunk))) {
        detect_chunk(g_chunk_buf.data());
        ++steps;
    }
}

void mn_task(void *arg);

void free_mn_task_mem()
{
    heap_caps_free(g_mn_stack_mem);
    heap_caps_free(g_mn_tcb);
    g_mn_stack_mem = nullptr;
    g_mn_tcb = nullptr;
}

bool create_mn_task()
{
    g_mn_stack_mem = static_cast<StackType_t *>(
        heap_caps_malloc(k_mn_stack, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)
    );
    g_mn_tcb = static_cast<StaticTask_t *>(
        heap_caps_malloc(sizeof(StaticTask_t), MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)
    );
    if (g_mn_stack_mem == nullptr || g_mn_tcb == nullptr) {
        free_mn_task_mem();
        ESP_LOGE(TAG, "MultiNet internal stack alloc failed");
        return false;
    }
    g_mn_task = xTaskCreateStaticPinnedToCore(
        mn_task,
        "skitty_mn",
        k_mn_stack,
        nullptr,
        k_mn_prio,
        g_mn_stack_mem,
        g_mn_tcb,
        0
    );
    if (g_mn_task == nullptr) {
        free_mn_task_mem();
        ESP_LOGE(TAG, "MultiNet task create failed");
        return false;
    }
    return true;
}

void mn_task(void *arg)
{
    (void)arg;
    const bool ok = create_multinet();
    g_ready.store(ok);
    g_create_done.store(true);
    if (!ok) {
        ESP_LOGW(TAG, "MultiNet task failed to create");
    }
    while (!g_mn_stop.load()) {
        poll_detect();
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    g_ready.store(false);
    destroy_multinet(true);
    feed_clear();
    feed_free();
    g_mn_task = nullptr;
    vTaskDelete(nullptr);
}
#endif

} // namespace

bool super_kitty_wake_start()
{
    g_addressed.store(false);
    g_ignore.store(false);
#if CONFIG_SR_MN_EN_NONE
    g_ready.store(false);
    ESP_LOGW(TAG, "English MultiNet not linked");
    return false;
#else
    if (g_mn_task != nullptr) {
        return true;
    }
    log_heap("wake start slim CJK");
    if (!psram_can_hold_multinet()) {
        g_ready.store(false);
        g_create_done.store(true);
        return false;
    }
    g_mn_stop.store(false);
    g_ready.store(false);
    g_create_done.store(false);
    if (!create_mn_task()) {
        return false;
    }
    ESP_LOGI(TAG, "MultiNet task started (internal stack)");
    return true;
#endif
}

void super_kitty_wake_stop()
{
    g_ready.store(false);
#if !CONFIG_SR_MN_EN_NONE
    g_mn_stop.store(true);
    for (int i = 0; i < 100 && g_mn_task != nullptr; ++i) {
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    if (g_mn_task != nullptr) {
        ESP_LOGW(TAG, "MultiNet task stop timed out");
    } else {
        vTaskDelay(pdMS_TO_TICKS(20));
        free_mn_task_mem();
    }
#endif
    g_addressed.store(false);
}

void super_kitty_wake_feed(const int16_t *samples, size_t count)
{
#if CONFIG_SR_MN_EN_NONE
    (void)samples;
    (void)count;
#else
    if (samples == nullptr || count == 0) {
        return;
    }
    feed_push(samples, count);
#endif
}

void super_kitty_wake_poll()
{
}

bool super_kitty_wake_take_address()
{
    return g_addressed.exchange(false);
}

void super_kitty_wake_ignore(bool ignore)
{
    g_ignore.store(ignore);
}

bool super_kitty_wake_multinet_ready()
{
    return g_ready.load();
}

bool super_kitty_wake_create_finished()
{
    return g_create_done.load();
}
