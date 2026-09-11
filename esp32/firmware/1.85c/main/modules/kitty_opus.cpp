/*
 * 16 kHz mono VoIP Opus for Kitty asr_audio (100 ms frames, PSRAM encoder).
 */
#include "kitty_opus.hpp"

#include <cstring>
#include <vector>

#include "esp_audio_types.h"
#include "esp_log.h"
#include "esp_opus_enc.h"

namespace {

constexpr const char *TAG = "kitty_opus";
constexpr int k_sample_rate = 16000;
constexpr int k_bitrate = 16000;
constexpr int k_complexity = 2;

void *g_enc = nullptr;
std::vector<uint8_t> g_out;
int g_in_size = 0;

} // namespace

bool kitty_opus_open()
{
    if (g_enc != nullptr) {
        return true;
    }
    esp_opus_enc_config_t cfg = ESP_OPUS_ENC_CONFIG_DEFAULT();
    cfg.sample_rate = k_sample_rate;
    cfg.channel = 1;
    cfg.bits_per_sample = 16;
    cfg.bitrate = k_bitrate;
    cfg.frame_duration = ESP_OPUS_ENC_FRAME_DURATION_100_MS;
    cfg.application_mode = ESP_OPUS_ENC_APPLICATION_VOIP;
    cfg.complexity = k_complexity;
    cfg.enable_vbr = true;
    if (esp_opus_enc_open(&cfg, sizeof(cfg), &g_enc) != ESP_AUDIO_ERR_OK || g_enc == nullptr) {
        ESP_LOGE(TAG, "open failed");
        g_enc = nullptr;
        return false;
    }
    int out_size = 0;
    if (esp_opus_enc_get_frame_size(g_enc, &g_in_size, &out_size) != ESP_AUDIO_ERR_OK || out_size <= 0) {
        ESP_LOGE(TAG, "frame size failed");
        kitty_opus_close();
        return false;
    }
    g_out.assign(static_cast<size_t>(out_size), 0);
    ESP_LOGI(TAG, "open in=%d out=%d", g_in_size, out_size);
    return true;
}

void kitty_opus_close()
{
    if (g_enc != nullptr) {
        esp_opus_enc_close(g_enc);
        g_enc = nullptr;
    }
    g_in_size = 0;
    g_out.clear();
}

bool kitty_opus_encode(const int16_t *samples, size_t count, std::vector<uint8_t> &out)
{
    if (samples == nullptr || count == 0 || !kitty_opus_open()) {
        return false;
    }
    const auto bytes = static_cast<uint32_t>(count * sizeof(int16_t));
    if (g_in_size > 0 && static_cast<int>(bytes) != g_in_size) {
        ESP_LOGW(TAG, "frame bytes=%u expected=%d", static_cast<unsigned>(bytes), g_in_size);
        return false;
    }
    esp_audio_enc_in_frame_t in_frame{};
    std::vector<uint8_t> pcm(bytes);
    std::memcpy(pcm.data(), samples, bytes);
    in_frame.buffer = pcm.data();
    in_frame.len = bytes;
    esp_audio_enc_out_frame_t out_frame{};
    out_frame.buffer = g_out.data();
    out_frame.len = static_cast<uint32_t>(g_out.size());
    if (esp_opus_enc_process(g_enc, &in_frame, &out_frame) != ESP_AUDIO_ERR_OK || out_frame.encoded_bytes == 0) {
        return false;
    }
    out.assign(g_out.data(), g_out.data() + out_frame.encoded_bytes);
    return true;
}
