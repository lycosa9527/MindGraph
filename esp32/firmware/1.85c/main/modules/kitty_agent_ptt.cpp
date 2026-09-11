#include "kitty_agent_shared.hpp"

#include "boost/chrono.hpp"
#include "boost/json.hpp"
#include "boost/thread.hpp"
#include "esp_log.h"

#include "kitty_audio.hpp"
#include "kitty_ui.hpp"
#include "kitty_ws.hpp"

namespace {

constexpr const char *TAG = "kitty_ptt";
std::atomic<bool> g_turn_ready{false};

void interrupt_speech()
{
    g_kitty_interrupt.store(true);
    kitty_send_obj({{"type", "abort"}, {"reason", "user_ptt"}});
    kitty_audio_spk_stop();
    g_kitty_speaking.store(false);
    g_kitty_playing_pcm.store(false);
    g_kitty_interrupt.store(false);
}

void reset_asr()
{
    std::lock_guard<std::mutex> lock(g_kitty_asr_mutex);
    g_kitty_asr_text.clear();
    g_kitty_asr_done = false;
    g_kitty_asr_late_commit.store(false);
    g_turn_ready.store(false);
}

std::string next_utterance_id()
{
    const uint32_t utterance = g_kitty_utterance.fetch_add(1);
    g_kitty_utterance_id = "w" + std::to_string(utterance);
    return g_kitty_utterance_id;
}

void send_asr_start(const std::string &utterance_id)
{
    boost::json::object start;
    start["type"] = "asr_start";
    start["utterance_id"] = utterance_id;
    start["language_hints"] = boost::json::array{"zh"};
    start["format"] = "pcm";
    start["sample_rate"] = 16000;
    kitty_send_obj(std::move(start));
}

bool encode_asr_frame(const int16_t *samples, size_t count, std::string &encoded)
{
    return kitty_b64_encode(reinterpret_cast<const uint8_t *>(samples), count * sizeof(int16_t), encoded);
}

bool stream_mic_until(const std::string &utterance_id, bool hold_only)
{
    std::vector<int16_t> frame(k_kitty_frame_samples, 0);
    int hold_peak = 0;
    int frames_sent = 0;
    int idle_ticks = 0;
    while (kitty_ws_is_open() && !kitty_ui_is_hidden()) {
        if (hold_only && !kitty_ui_hold_active()) {
            break;
        }
        if (!hold_only) {
            bool done = false;
            {
                std::lock_guard<std::mutex> lock(g_kitty_asr_mutex);
                done = g_kitty_asr_done;
            }
            if (done || kitty_ui_hold_active()) {
                break;
            }
            ++idle_ticks;
            if (idle_ticks > 600) {
                break;
            }
        }
        if (!kitty_audio_mic_read(frame.data(), frame.size())) {
            boost::this_thread::sleep_for(boost::chrono::milliseconds(k_kitty_hold_poll_ms));
            continue;
        }
        int peak = 0;
        for (const int16_t sample : frame) {
            int amp = sample;
            if (amp < 0) {
                amp = -amp;
            }
            if (amp > peak) {
                peak = amp;
            }
        }
        if (peak > hold_peak) {
            hold_peak = peak;
        }
        kitty_ui_set_mic_level(static_cast<uint8_t>(peak > 32767 ? 255 : peak / 128));
        kitty_audio_boost_pcm(frame.data(), frame.size());
        std::string encoded;
        if (!encode_asr_frame(frame.data(), frame.size(), encoded)) {
            continue;
        }
        boost::json::object audio;
        audio["type"] = "asr_audio";
        audio["data"] = encoded;
        audio["format"] = "pcm";
        audio["utterance_id"] = utterance_id;
        kitty_send_obj(std::move(audio));
        ++frames_sent;
    }
    kitty_audio_mic_close();
    kitty_ui_clear_hold();
    if (kitty_ui_is_hidden() || !kitty_ws_is_open()) {
        ESP_LOGI(TAG, "ptt aborted home utt=%s frames=%d", utterance_id.c_str(), frames_sent);
        return false;
    }
    boost::json::object stop;
    stop["type"] = "asr_stop";
    stop["utterance_id"] = utterance_id;
    stop["peak"] = hold_peak;
    kitty_send_obj(std::move(stop));
    ESP_LOGI(TAG, "ptt stop utt=%s frames=%d peak=%d", utterance_id.c_str(), frames_sent, hold_peak);
    for (int i = 0; i < 160; ++i) {
        if (kitty_ui_is_hidden() || !kitty_ws_is_open()) {
            return false;
        }
        bool done = false;
        {
            std::lock_guard<std::mutex> lock(g_kitty_asr_mutex);
            done = g_kitty_asr_done;
        }
        if (done) {
            break;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(50));
    }
    return true;
}

} // namespace

static void clear_choices()
{
    for (std::string &choice : g_kitty_choices) {
        choice.clear();
    }
}

void kitty_agent_begin_user_turn()
{
    clear_choices();
    kitty_ui_begin_user_turn();
    g_turn_ready.store(true);
}

void kitty_agent_begin_user_turn_once()
{
    if (g_turn_ready.exchange(true)) {
        return;
    }
    clear_choices();
    kitty_ui_begin_user_turn();
}

void kitty_agent_commit_asr()
{
    std::string text;
    std::string utterance_id;
    {
        std::lock_guard<std::mutex> lock(g_kitty_asr_mutex);
        text = g_kitty_asr_text;
        utterance_id = g_kitty_utterance_id;
        g_kitty_asr_text.clear();
        g_kitty_asr_done = false;
    }
    if (text.empty()) {
        g_kitty_asr_late_commit.store(true);
        if (g_turn_ready.load()) {
            kitty_ui_set_user_text("没听清");
        }
        kitty_ui_set_state(KittyUiState::idle);
        return;
    }
    g_kitty_asr_late_commit.store(false);
    kitty_ui_set_user_text(text);
    kitty_ui_set_state(KittyUiState::thinking);
    boost::json::object msg;
    msg["type"] = "text";
    msg["text"] = text;
    msg["ingress_source"] = "asr";
    if (!utterance_id.empty()) {
        msg["utterance_id"] = utterance_id;
    }
    const std::string payload = boost::json::serialize(msg);
    if (!kitty_ws_send_json(payload)) {
        ESP_LOGW(TAG, "commit send failed utt=%s", utterance_id.c_str());
        g_kitty_asr_late_commit.store(true);
    }
}

static bool hold_is_stable()
{
    for (int i = 0; i < 10; ++i) {
        if (!kitty_ui_hold_active() || kitty_ui_is_hidden()) {
            return false;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_kitty_hold_poll_ms));
    }
    return kitty_ui_hold_active();
}

void kitty_agent_run_ptt()
{
    reset_asr();
    if (!hold_is_stable() || kitty_ui_is_hidden()) {
        return;
    }
    interrupt_speech();
    kitty_agent_begin_user_turn();
    if (!kitty_audio_mic_open()) {
        kitty_ui_set_kitty_text("麦克风不可用");
        while (kitty_ui_hold_active() && !kitty_ui_is_hidden()) {
            boost::this_thread::sleep_for(boost::chrono::milliseconds(k_kitty_hold_poll_ms));
        }
        return;
    }
    kitty_ui_set_state(KittyUiState::listening);
    const std::string utterance_id = next_utterance_id();
    send_asr_start(utterance_id);
    if (!stream_mic_until(utterance_id, true)) {
        return;
    }
    kitty_agent_commit_asr();
}

void kitty_agent_run_auto_listen()
{
    g_kitty_pending_auto_listen.store(false);
    if (g_kitty_speaking.load() || g_kitty_playing_pcm.load()) {
        return;
    }
    reset_asr();
    if (!kitty_audio_mic_open()) {
        kitty_ui_set_kitty_text("麦克风不可用");
        return;
    }
    kitty_ui_set_state(KittyUiState::listening);
    const std::string utterance_id = next_utterance_id();
    send_asr_start(utterance_id);
    if (!stream_mic_until(utterance_id, false)) {
        return;
    }
    kitty_agent_commit_asr();
}

void kitty_agent_send_clarify_choice(int index)
{
    if (index < 1 || index > k_kitty_choice_max) {
        return;
    }
    const std::string label = g_kitty_choices[index - 1];
    if (label.empty()) {
        return;
    }
    kitty_agent_begin_user_turn();
    kitty_ui_set_user_text(label);
    kitty_ui_set_state(KittyUiState::thinking);
    boost::json::object msg;
    msg["type"] = "text";
    msg["text"] = label;
    msg["ingress_source"] = "clarify_choice";
    kitty_send_obj(std::move(msg));
}
