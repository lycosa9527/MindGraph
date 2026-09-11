#include "recorder_session.hpp"

#include <atomic>
#include <mutex>
#include <string>

#include "boost/chrono.hpp"
#include "boost/json.hpp"
#include "boost/thread.hpp"
#include "esp_log.h"

#include "kitty_agent_shared.hpp"
#include "kitty_ws.hpp"

#include "recorder_net.hpp"

namespace {

constexpr const char *TAG = "recorder_session";
constexpr size_t k_transcript_max = 16000;

std::mutex g_mutex;
std::string g_transcript;
std::string g_error;
std::atomic<bool> g_ready{false};
std::atomic<bool> g_stopped{false};
std::atomic<uint8_t> g_mic_level{0};

void copy_sentences(const boost::json::array &sentences, std::string &out)
{
    out.clear();
    for (const auto &entry : sentences) {
        if (!entry.is_object()) {
            continue;
        }
        const auto *text = entry.as_object().if_contains("text");
        if (text == nullptr || !text->is_string()) {
            continue;
        }
        const std::string line = std::string(text->as_string().c_str());
        if (line.empty()) {
            continue;
        }
        if (!out.empty()) {
            out += '\n';
        }
        out += line;
        if (out.size() > k_transcript_max) {
            out.erase(0, out.size() - k_transcript_max);
            break;
        }
    }
}

} // namespace

bool recorder_session_open(const std::string &token)
{
    recorder_session_close();
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        g_error.clear();
    }
    g_ready.store(false);
    g_stopped.store(false);
    kitty_ws_set_handler(recorder_session_handle_json);
    const std::string url = recorder_net_ws_url();
    if (!kitty_ws_connect(url, token)) {
        ESP_LOGW(TAG, "connect failed");
        return false;
    }
    for (int i = 0; i < 80 && !kitty_ws_is_open(); ++i) {
        boost::this_thread::sleep_for(boost::chrono::milliseconds(50));
    }
    if (!kitty_ws_is_open()) {
        ESP_LOGW(TAG, "socket never opened");
        recorder_session_close();
        return false;
    }
    boost::json::object start;
    start["type"] = "start";
    start["diarization_enabled"] = true;
    if (!kitty_ws_send_json(boost::json::serialize(start))) {
        recorder_session_close();
        return false;
    }
    return true;
}

void recorder_session_close()
{
    kitty_ws_close();
    g_ready.store(false);
    g_stopped.store(false);
    g_mic_level.store(0);
}

bool recorder_session_is_open()
{
    return kitty_ws_is_open();
}

bool recorder_session_is_ready()
{
    return g_ready.load() && kitty_ws_is_open();
}

bool recorder_session_wait_ready(int timeout_ms)
{
    const int steps = timeout_ms / 50;
    for (int i = 0; i < steps; ++i) {
        if (g_ready.load()) {
            return true;
        }
        std::string error;
        if (recorder_session_take_error(error)) {
            return false;
        }
        if (!kitty_ws_is_open()) {
            return false;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(50));
    }
    return g_ready.load();
}

bool recorder_session_send_pcm(const int16_t *samples, size_t count)
{
    if (samples == nullptr || count == 0 || !recorder_session_is_ready()) {
        return false;
    }
    std::string encoded;
    if (!kitty_b64_encode(reinterpret_cast<const uint8_t *>(samples), count * sizeof(int16_t), encoded)) {
        return false;
    }
    boost::json::object audio;
    audio["type"] = "append";
    audio["audio"] = encoded;
    return kitty_ws_send_json(boost::json::serialize(audio));
}

bool recorder_session_request_stop()
{
    if (!kitty_ws_is_open()) {
        g_stopped.store(true);
        return true;
    }
    boost::json::object stop;
    stop["type"] = "stop";
    const bool sent = kitty_ws_send_json(boost::json::serialize(stop));
    if (!sent) {
        g_stopped.store(true);
    }
    return sent;
}

bool recorder_session_wait_stopped(int timeout_ms)
{
    const int steps = timeout_ms / 50;
    for (int i = 0; i < steps; ++i) {
        if (g_stopped.load() || !kitty_ws_is_open()) {
            return true;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(50));
    }
    return g_stopped.load() || !kitty_ws_is_open();
}

void recorder_session_handle_json(const std::string &raw)
{
    boost::system::error_code parse_err;
    const auto root = boost::json::parse(raw, parse_err);
    if (parse_err || !root.is_object()) {
        return;
    }
    const auto &obj = root.as_object();
    const auto *type = obj.if_contains("type");
    if (type == nullptr || !type->is_string()) {
        return;
    }
    const std::string kind = std::string(type->as_string().c_str());
    if (kind == "started") {
        g_ready.store(true);
        return;
    }
    if (kind == "stopped") {
        g_stopped.store(true);
        g_ready.store(false);
        return;
    }
    if (kind == "error") {
        std::lock_guard<std::mutex> lock(g_mutex);
        const auto *message = obj.if_contains("message");
        g_error = message != nullptr && message->is_string()
            ? std::string(message->as_string().c_str())
            : "语音服务出错";
        g_ready.store(false);
        return;
    }
    if (kind != "snapshot") {
        return;
    }
    const auto *sentences = obj.if_contains("sentences");
    if (sentences == nullptr || !sentences->is_array()) {
        return;
    }
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_sentences(sentences->as_array(), g_transcript);
}

std::string recorder_session_transcript()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_transcript;
}

void recorder_session_clear_transcript()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_transcript.clear();
}

bool recorder_session_take_error(std::string &message)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_error.empty()) {
        return false;
    }
    message = g_error;
    g_error.clear();
    return true;
}

uint8_t recorder_session_mic_level()
{
    return g_mic_level.load();
}

void recorder_session_set_mic_level(uint8_t level)
{
    g_mic_level.store(level);
}
