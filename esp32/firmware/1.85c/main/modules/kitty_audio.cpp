/*
 * V1 PCM5101 playback + MEMS I2S capture.
 * Speaker goes through HAL CodecPlayer so Settings volume/mute apply.
 * Mic stays on the board-manager device (32-bit MEMS unpack).
 */
#include "sdkconfig.h"

#include <cmath>
#include <cstdint>
#include <cstring>
#include <vector>

#include "esp_log.h"

#include "kitty_audio.hpp"

#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
#include "brookesia/hal_interface/interface.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_player.hpp"
#include "dev_audio_codec.h"
#include "esp_board_manager.h"
#include "esp_codec_dev.h"
#endif

namespace {

constexpr const char *TAG = "kitty_audio";
constexpr uint32_t k_mic_rate = 16000;
constexpr uint32_t k_spk_rate = 22050;
constexpr int k_spk_bits = 16;
constexpr int k_mic_bits = 32;
constexpr int k_mic_ch = 2;
constexpr int k_spk_ch = 2;

#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
using CodecPlayerIface = esp_brookesia::hal::audio::CodecPlayerIface;
using PlayerHandle = esp_brookesia::hal::InterfaceHandle<CodecPlayerIface>;

void *g_mic_handles = nullptr;
std::vector<int32_t> g_mic_raw;
bool g_mic_open = false;
bool g_spk_open = false;

PlayerHandle &speaker_player()
{
    static PlayerHandle handle;
    if (!handle) {
        handle = esp_brookesia::hal::acquire_first_interface<CodecPlayerIface>();
    }
    return handle;
}

esp_codec_dev_handle_t codec_dev(void *handles)
{
    if (handles == nullptr) {
        return nullptr;
    }
    return reinterpret_cast<dev_audio_codec_handles_t *>(handles)->codec_dev;
}

bool init_named_device(const char *name, void **handles_out)
{
    if (!esp_board_manager_check_name(name)) {
        ESP_LOGW(TAG, "device %s missing", name);
        return false;
    }
    if (esp_board_manager_init_device_by_name(name) != ESP_OK) {
        ESP_LOGE(TAG, "init %s failed", name);
        return false;
    }
    if (esp_board_manager_get_device_handle(name, handles_out) != ESP_OK || *handles_out == nullptr) {
        ESP_LOGE(TAG, "handle %s failed", name);
        return false;
    }
    return true;
}

bool open_dev(void *handles, int sample_rate, int channel, int bits, bool in)
{
    esp_codec_dev_handle_t dev = codec_dev(handles);
    if (dev == nullptr) {
        return false;
    }
    esp_codec_dev_sample_info_t fs = {};
    fs.bits_per_sample = static_cast<uint8_t>(bits);
    fs.channel = static_cast<uint8_t>(channel);
    fs.sample_rate = static_cast<uint32_t>(sample_rate);
    const esp_err_t err = esp_codec_dev_open(dev, &fs);
    if (err != ESP_CODEC_DEV_OK) {
        ESP_LOGE(
            TAG,
            "codec open %s failed: %d bits=%d ch=%d",
            in ? "mic" : "spk",
            static_cast<int>(err),
            bits,
            channel
        );
        return false;
    }
    return true;
}

void unpack_mems_frame(const int32_t *raw, int16_t *out, size_t frames)
{
    for (size_t i = 0; i < frames; ++i) {
        const int32_t left = raw[i * 2] >> 16;
        const int32_t right = raw[i * 2 + 1] >> 16;
        const int left_amp = left < 0 ? -left : left;
        const int right_amp = right < 0 ? -right : right;
        int32_t chosen = left_amp >= right_amp ? left : right;
        if (chosen > 32767) {
            chosen = 32767;
        } else if (chosen < -32768) {
            chosen = -32768;
        }
        out[i] = static_cast<int16_t>(chosen);
    }
}

void close_dev(void *handles)
{
    esp_codec_dev_handle_t dev = codec_dev(handles);
    if (dev != nullptr) {
        esp_codec_dev_close(dev);
    }
}

int16_t rms_i16(const int16_t *samples, size_t count)
{
    if (samples == nullptr || count == 0) {
        return 0;
    }
    int64_t acc = 0;
    for (size_t i = 0; i < count; ++i) {
        const int32_t s = samples[i];
        acc += static_cast<int64_t>(s) * s;
    }
    return static_cast<int16_t>(std::sqrt(static_cast<double>(acc / static_cast<int64_t>(count))));
}

void fill_tone(std::vector<int16_t> &stereo, uint32_t rate, float hz, float seconds)
{
    const size_t frames = static_cast<size_t>(rate * seconds);
    stereo.assign(frames * 2, 0);
    for (size_t i = 0; i < frames; ++i) {
        const float sample = std::sin(2.0f * 3.14159265f * hz * static_cast<float>(i) / static_cast<float>(rate));
        const auto value = static_cast<int16_t>(sample * 8000.0f);
        stereo[i * 2] = value;
        stereo[i * 2 + 1] = value;
    }
}

void fill_click(std::vector<int16_t> &stereo)
{
    const size_t frames = static_cast<size_t>(k_spk_rate * 48 / 1000);
    stereo.assign(frames * 2, 0);
    for (size_t i = 0; i < frames; ++i) {
        const float t = static_cast<float>(i) / static_cast<float>(k_spk_rate);
        const float fade = 1.0f - static_cast<float>(i) / static_cast<float>(frames);
        const float env = fade * fade;
        const float sample = std::sin(2.0f * 3.14159265f * 1680.0f * t) * env;
        const auto value = static_cast<int16_t>(sample * 5200.0f);
        stereo[i * 2] = value;
        stereo[i * 2 + 1] = value;
    }
}

const std::vector<int16_t> &click_pcm()
{
    static const std::vector<int16_t> pcm = []() {
        std::vector<int16_t> stereo;
        fill_click(stereo);
        return stereo;
    }();
    return pcm;
}
#endif

} // namespace

bool kitty_audio_init()
{
#if !CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    ESP_LOGW(TAG, "audio HAL disabled");
    return false;
#else
    const bool mic = init_named_device("audio_adc", &g_mic_handles);
    ESP_LOGI(TAG, "audio devices mic=%d", static_cast<int>(mic));
    return mic;
#endif
}

void kitty_audio_run_smoke()
{
#if !CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    return;
#else
    if (g_mic_handles != nullptr && open_dev(g_mic_handles, k_mic_rate, k_mic_ch, k_mic_bits, true)) {
        std::vector<int16_t> frame(1600, 0);
        g_mic_raw.assign(frame.size() * 2, 0);
        const esp_err_t err = esp_codec_dev_read(
            codec_dev(g_mic_handles),
            g_mic_raw.data(),
            static_cast<int>(g_mic_raw.size() * sizeof(int32_t))
        );
        if (err == ESP_CODEC_DEV_OK) {
            unpack_mems_frame(g_mic_raw.data(), frame.data(), frame.size());
            kitty_audio_boost_pcm(frame.data(), frame.size());
        }
        ESP_LOGI(
            TAG,
            "mic smoke 16kHz n=%u rms=%d err=%d wide32",
            static_cast<unsigned>(frame.size()),
            static_cast<int>(rms_i16(frame.data(), frame.size())),
            static_cast<int>(err)
        );
        close_dev(g_mic_handles);
    }
    if (kitty_audio_spk_open()) {
        std::vector<int16_t> tone;
        fill_tone(tone, k_spk_rate, 880.0f, 0.35f);
        const bool wrote = kitty_audio_spk_write(tone.data(), tone.size());
        ESP_LOGI(
            TAG,
            "spk smoke 22050 Hz tone frames=%u ok=%d (attach speaker to hear it)",
            static_cast<unsigned>(tone.size() / 2),
            static_cast<int>(wrote)
        );
        kitty_audio_spk_close();
    }
#endif
}

bool kitty_audio_mic_open()
{
#if !CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    return false;
#else
    if (g_mic_open) {
        return true;
    }
    g_mic_open = open_dev(g_mic_handles, k_mic_rate, k_mic_ch, k_mic_bits, true);
    return g_mic_open;
#endif
}

void kitty_audio_mic_close()
{
#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    if (g_mic_open) {
        close_dev(g_mic_handles);
        g_mic_open = false;
    }
#endif
}

void kitty_audio_boost_pcm(int16_t *samples, size_t count)
{
    if (samples == nullptr || count == 0) {
        return;
    }
    int64_t sum = 0;
    for (size_t i = 0; i < count; ++i) {
        sum += samples[i];
    }
    const int mean = static_cast<int>(sum / static_cast<int64_t>(count));
    int peak = 0;
    for (size_t i = 0; i < count; ++i) {
        int centered = static_cast<int>(samples[i]) - mean;
        if (centered > 32767) {
            centered = 32767;
        } else if (centered < -32768) {
            centered = -32768;
        }
        samples[i] = static_cast<int16_t>(centered);
        int amp = centered < 0 ? -centered : centered;
        if (amp > peak) {
            peak = amp;
        }
    }
    if (peak < 16 || peak >= 12000) {
        return;
    }
    int gain = 12000 / peak;
    if (gain > 48) {
        gain = 48;
    }
    for (size_t i = 0; i < count; ++i) {
        const int scaled = static_cast<int>(samples[i]) * gain;
        if (scaled > 32767) {
            samples[i] = 32767;
        } else if (scaled < -32768) {
            samples[i] = -32768;
        } else {
            samples[i] = static_cast<int16_t>(scaled);
        }
    }
}

bool kitty_audio_mic_read(int16_t *samples, size_t count)
{
#if !CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    (void)samples;
    (void)count;
    return false;
#else
    if (!g_mic_open || samples == nullptr || count == 0) {
        return false;
    }
    if (g_mic_raw.size() < count * 2) {
        g_mic_raw.resize(count * 2);
    }
    const esp_err_t err = esp_codec_dev_read(
        codec_dev(g_mic_handles),
        g_mic_raw.data(),
        static_cast<int>(count * 2 * sizeof(int32_t))
    );
    if (err != ESP_CODEC_DEV_OK) {
        return false;
    }
    unpack_mems_frame(g_mic_raw.data(), samples, count);
    return true;
#endif
}

bool kitty_audio_spk_open()
{
#if !CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    return false;
#else
    if (g_spk_open) {
        return true;
    }
    auto &player = speaker_player();
    if (!player) {
        ESP_LOGE(TAG, "codec player missing");
        return false;
    }
    const CodecPlayerIface::Config config{
        .bits = static_cast<uint8_t>(k_spk_bits),
        .channels = static_cast<uint8_t>(k_spk_ch),
        .sample_rate = k_spk_rate,
    };
    g_spk_open = player->open(config);
    return g_spk_open;
#endif
}

void kitty_audio_spk_close()
{
#if CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    if (g_spk_open) {
        auto &player = speaker_player();
        if (player) {
            player->close();
        }
        g_spk_open = false;
    }
#endif
}

bool kitty_audio_spk_write(const int16_t *samples, size_t count)
{
#if !CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    (void)samples;
    (void)count;
    return false;
#else
    if (!g_spk_open || samples == nullptr || count == 0) {
        return false;
    }
    auto &player = speaker_player();
    if (!player) {
        return false;
    }
    return player->write_data(
        reinterpret_cast<const uint8_t *>(samples),
        count * sizeof(int16_t)
    );
#endif
}

void kitty_audio_spk_stop()
{
    kitty_audio_spk_close();
}

void kitty_audio_play_click()
{
#if !CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    return;
#else
    if (g_mic_open) {
        return;
    }
    const bool was_open = g_spk_open;
    if (!kitty_audio_spk_open()) {
        return;
    }
    const std::vector<int16_t> &pcm = click_pcm();
    kitty_audio_spk_write(pcm.data(), pcm.size());
    if (!was_open) {
        kitty_audio_spk_close();
    }
#endif
}
