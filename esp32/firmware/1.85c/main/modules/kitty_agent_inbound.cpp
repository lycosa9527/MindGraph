#include "kitty_agent_shared.hpp"

#include "boost/json.hpp"
#include "esp_log.h"

#include "kitty_audio.hpp"
#include "kitty_ui.hpp"

namespace {

constexpr const char *TAG = "kitty_in";

void play_pcm_mono(const std::vector<uint8_t> &bytes)
{
    if (bytes.size() < 2 || g_kitty_interrupt.load()) {
        return;
    }
    if (!kitty_audio_spk_open()) {
        return;
    }
    g_kitty_playing_pcm.store(true);
    const size_t frames = bytes.size() / 2;
    std::vector<int16_t> stereo(frames * 2);
    const auto *mono = reinterpret_cast<const int16_t *>(bytes.data());
    for (size_t i = 0; i < frames; ++i) {
        stereo[i * 2] = mono[i];
        stereo[i * 2 + 1] = mono[i];
    }
    kitty_audio_spk_write(stereo.data(), stereo.size());
    g_kitty_playing_pcm.store(false);
}

void apply_clarify_options(const boost::json::object &obj)
{
    const auto *opts = obj.if_contains("clarify_options");
    if (opts == nullptr || !opts->is_array()) {
        return;
    }
    int index = 1;
    for (const auto &item : opts->as_array()) {
        if (index > 2) {
            break;
        }
        std::string label;
        if (item.is_string()) {
            label = item.as_string().c_str();
        } else if (item.is_object()) {
            const auto &row = item.as_object();
            const auto *text = row.if_contains("text");
            const auto *name = row.if_contains("label");
            if (text != nullptr && text->is_string()) {
                label = text->as_string().c_str();
            } else if (name != nullptr && name->is_string()) {
                label = name->as_string().c_str();
            }
        }
        if (label.empty()) {
            continue;
        }
        kitty_ui_set_choice(index, label);
        if (index == 1) {
            g_kitty_choice_a = label;
        } else {
            g_kitty_choice_b = label;
        }
        ++index;
    }
}

} // namespace

void kitty_agent_handle_inbound(const std::string &raw)
{
    boost::system::error_code err;
    const auto root = boost::json::parse(raw, err);
    if (err || !root.is_object()) {
        return;
    }
    const auto &obj = root.as_object();
    const auto *type_v = obj.if_contains("type");
    if (type_v == nullptr || !type_v->is_string()) {
        return;
    }
    const std::string type(type_v->as_string().c_str());
    if (type == "connected" || type == "hello") {
        kitty_ui_set_state(KittyUiState::idle);
        if (type == "hello") {
            const auto *mode = obj.if_contains("listen_mode");
            if (mode != nullptr && mode->is_string()) {
                const std::string listen(mode->as_string().c_str());
                g_kitty_listen_auto.store(listen == "auto");
            }
        }
        return;
    }
    if (type == "text_chunk") {
        const auto *text = obj.if_contains("text");
        if (text != nullptr && text->is_string()) {
            kitty_ui_set_kitty_text(std::string(text->as_string().c_str()));
        }
        apply_clarify_options(obj);
        if (!g_kitty_speaking.load()) {
            kitty_ui_set_state(KittyUiState::thinking);
        }
        return;
    }
    if (type == "asr_partial" || type == "asr_final" || type == "asr_stopped") {
        const auto *text = obj.if_contains("text");
        const std::string spoken = (text != nullptr && text->is_string())
            ? std::string(text->as_string().c_str())
            : "";
        {
            std::lock_guard<std::mutex> lock(g_kitty_asr_mutex);
            if (!spoken.empty()) {
                g_kitty_asr_text = spoken;
            }
            if (type != "asr_partial") {
                g_kitty_asr_done = true;
            }
        }
        if (!spoken.empty()) {
            kitty_ui_set_user_text(spoken);
            ESP_LOGI(TAG, "asr %s: %s", type.c_str(), spoken.c_str());
        }
        return;
    }
    if (type == "audio_chunk") {
        const auto *audio = obj.if_contains("audio");
        if (audio == nullptr || !audio->is_string() || g_kitty_interrupt.load()) {
            return;
        }
        std::vector<uint8_t> pcm;
        if (!kitty_b64_decode(std::string(audio->as_string().c_str()), pcm)) {
            return;
        }
        g_kitty_speaking.store(true);
        kitty_ui_set_state(KittyUiState::speaking);
        play_pcm_mono(pcm);
        return;
    }
    if (type == "tts_done" || type == "tts_interrupted") {
        g_kitty_speaking.store(false);
        kitty_ui_set_state(KittyUiState::idle);
        if (type == "tts_done" && g_kitty_listen_auto.load()) {
            g_kitty_pending_auto_listen.store(true);
        }
        return;
    }
    if (type == "error") {
        {
            std::lock_guard<std::mutex> lock(g_kitty_asr_mutex);
            g_kitty_asr_done = true;
        }
        kitty_ui_set_state(KittyUiState::error);
        const auto *msg = obj.if_contains("message");
        const auto *errv = obj.if_contains("error");
        if (msg != nullptr && msg->is_string()) {
            kitty_ui_set_kitty_text(std::string(msg->as_string().c_str()));
        } else if (errv != nullptr && errv->is_string()) {
            kitty_ui_set_kitty_text(std::string(errv->as_string().c_str()));
        }
    }
}
