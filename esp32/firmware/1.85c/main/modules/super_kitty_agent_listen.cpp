#include "super_kitty_agent_shared.hpp"

#include "boost/chrono.hpp"
#include "boost/json.hpp"
#include "boost/thread.hpp"
#include "esp_log.h"

#include "kitty_agent_shared.hpp"
#include "kitty_audio.hpp"
#include "kitty_ws.hpp"
#include "super_kitty_audio.hpp"
#include "super_kitty_phrase.hpp"
#include "super_kitty_ui.hpp"
#include "super_kitty_wake.hpp"

namespace {

constexpr const char *TAG = "skitty_listen";
std::atomic<bool> g_turn_ready{false};

void interrupt_speech()
{
    g_super_kitty_interrupt.store(true);
    super_kitty_send_obj({{"type", "abort"}, {"reason", "user"}});
    kitty_audio_spk_stop();
    kitty_audio_spk_open();
    g_super_kitty_speaking.store(false);
    g_super_kitty_playing_pcm.store(false);
    g_super_kitty_interrupt.store(false);
}

void reset_asr()
{
    std::lock_guard<std::mutex> lock(g_super_kitty_asr_mutex);
    g_super_kitty_asr_text.clear();
    g_super_kitty_asr_done = false;
    g_super_kitty_asr_late_commit.store(false);
    g_turn_ready.store(false);
}

std::string next_utterance_id()
{
    const uint32_t utterance = g_super_kitty_utterance.fetch_add(1);
    g_super_kitty_utterance_id = "sk" + std::to_string(utterance);
    return g_super_kitty_utterance_id;
}

void send_asr_start(const std::string &utterance_id)
{
    boost::json::object start;
    start["type"] = "asr_start";
    start["utterance_id"] = utterance_id;
    start["language_hints"] = boost::json::array{"zh"};
    start["format"] = "pcm";
    start["sample_rate"] = 16000;
    super_kitty_send_obj(std::move(start));
}

bool stream_until_idle(const std::string &utterance_id)
{
    std::vector<int16_t> frame(k_super_kitty_frame_samples, 0);
    int frames_sent = 0;
    int idle_ticks = 0;
    int voiced = 0;
    super_kitty_audio_clear();
    while (kitty_ws_is_open() && !super_kitty_ui_is_hidden()) {
        bool done = false;
        {
            std::lock_guard<std::mutex> lock(g_super_kitty_asr_mutex);
            done = g_super_kitty_asr_done;
        }
        if (done) {
            break;
        }
        if (!super_kitty_audio_read(frame.data(), frame.size())) {
            boost::this_thread::sleep_for(boost::chrono::milliseconds(k_super_kitty_hold_poll_ms));
            ++idle_ticks;
            if (idle_ticks > 250) {
                break;
            }
            continue;
        }
        const uint8_t level = super_kitty_audio_level();
        super_kitty_ui_set_listen_level(level);
        if (level < 12) {
            ++idle_ticks;
        } else {
            idle_ticks = 0;
            ++voiced;
        }
        if (voiced > 8 && idle_ticks > 40) {
            break;
        }
        if (frames_sent > 80) {
            break;
        }
        std::string encoded;
        if (!kitty_b64_encode(
                reinterpret_cast<const uint8_t *>(frame.data()),
                frame.size() * sizeof(int16_t),
                encoded
            )) {
            continue;
        }
        boost::json::object audio;
        audio["type"] = "asr_audio";
        audio["data"] = encoded;
        audio["format"] = "pcm";
        audio["utterance_id"] = utterance_id;
        super_kitty_send_obj(std::move(audio));
        ++frames_sent;
    }
    if (super_kitty_ui_is_hidden() || !kitty_ws_is_open()) {
        return false;
    }
    boost::json::object stop;
    stop["type"] = "asr_stop";
    stop["utterance_id"] = utterance_id;
    super_kitty_send_obj(std::move(stop));
    ESP_LOGI(TAG, "listen stop utt=%s frames=%d", utterance_id.c_str(), frames_sent);
    for (int i = 0; i < 160; ++i) {
        if (super_kitty_ui_is_hidden() || !kitty_ws_is_open()) {
            return false;
        }
        bool done = false;
        {
            std::lock_guard<std::mutex> lock(g_super_kitty_asr_mutex);
            done = g_super_kitty_asr_done;
        }
        if (done) {
            break;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(50));
    }
    return true;
}

void clear_choices()
{
    for (std::string &choice : g_super_kitty_choices) {
        choice.clear();
    }
}

} // namespace

void super_kitty_agent_begin_user_turn()
{
    clear_choices();
    super_kitty_ui_begin_user_turn();
    g_turn_ready.store(true);
}

void super_kitty_agent_begin_user_turn_once()
{
    if (g_turn_ready.exchange(true)) {
        return;
    }
    clear_choices();
    super_kitty_ui_begin_user_turn();
}

void super_kitty_agent_commit_asr()
{
    std::string text;
    std::string utterance_id;
    {
        std::lock_guard<std::mutex> lock(g_super_kitty_asr_mutex);
        text = g_super_kitty_asr_text;
        utterance_id = g_super_kitty_utterance_id;
        g_super_kitty_asr_text.clear();
        g_super_kitty_asr_done = false;
    }
    if (text.empty()) {
        g_super_kitty_asr_late_commit.store(true);
        super_kitty_ui_set_state(KittyUiState::idle);
        return;
    }
    std::string request = super_kitty_phrase_strip(text);
    if (request.empty()) {
        request = "你好";
    }
    g_super_kitty_asr_late_commit.store(false);
    super_kitty_ui_set_user_text(request);
    super_kitty_ui_set_state(KittyUiState::thinking);
    boost::json::object msg;
    msg["type"] = "text";
    msg["text"] = request;
    msg["ingress_source"] = "asr";
    if (!utterance_id.empty()) {
        msg["utterance_id"] = utterance_id;
    }
    if (!kitty_ws_send_json(boost::json::serialize(msg))) {
        ESP_LOGW(TAG, "commit send failed utt=%s", utterance_id.c_str());
        g_super_kitty_asr_late_commit.store(true);
    }
}

void super_kitty_agent_run_addressed_listen()
{
    reset_asr();
    if (super_kitty_ui_is_hidden() || !kitty_ws_is_open()) {
        return;
    }
    interrupt_speech();
    super_kitty_wake_ignore(true);
    super_kitty_agent_begin_user_turn();
    super_kitty_ui_set_state(KittyUiState::listening);
    const std::string utterance_id = next_utterance_id();
    send_asr_start(utterance_id);
    const bool streamed = stream_until_idle(utterance_id);
    if (streamed) {
        super_kitty_agent_commit_asr();
    }
    super_kitty_wake_ignore(false);
}

void super_kitty_agent_send_clarify_choice(int index)
{
    if (index < 1 || index > k_super_kitty_choice_max) {
        return;
    }
    const std::string label = g_super_kitty_choices[index - 1];
    if (label.empty()) {
        return;
    }
    super_kitty_agent_begin_user_turn();
    super_kitty_ui_set_user_text(label);
    super_kitty_ui_set_state(KittyUiState::thinking);
    boost::json::object msg;
    msg["type"] = "text";
    msg["text"] = label;
    msg["ingress_source"] = "clarify_choice";
    super_kitty_send_obj(std::move(msg));
}
