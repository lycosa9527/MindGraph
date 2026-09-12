#include "recorder_agent.hpp"

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <string>
#include <vector>

#include "boost/chrono.hpp"
#include "boost/thread.hpp"
#include "esp_log.h"
#include "esp_netif.h"

#include "brookesia/lib_utils/thread_config.hpp"
#include "private/utils.hpp"

#include "kitty_audio.hpp"
#include "kitty_net.hpp"
#include "recorder_net.hpp"
#include "recorder_session.hpp"
#include "recorder_ui.hpp"

namespace {

constexpr const char *TAG = "recorder_agent";
constexpr size_t k_frame_samples = 1600;
constexpr int k_loop_ms = 80;
constexpr int k_hold_poll_ms = 20;

std::atomic<bool> g_run{false};
std::atomic<bool> g_thread_live{false};
std::atomic<bool> g_paused{false};
std::atomic<bool> g_capture{false};

std::string g_token;
std::string g_diagram_id;
std::string g_title;
int64_t g_started_at = 0;
int64_t g_paused_ms = 0;
std::atomic<bool> g_persisted{false};
std::atomic<bool> g_block_home{false};

void pause_capture();
bool stop_capture();
void generate_mindmap();

int64_t now_ms()
{
    return boost::chrono::duration_cast<boost::chrono::milliseconds>(
        boost::chrono::steady_clock::now().time_since_epoch()
    ).count();
}

void paint_elapsed()
{
    int64_t elapsed = g_paused_ms;
    if (g_capture.load() && !g_paused.load() && g_started_at > 0) {
        elapsed += now_ms() - g_started_at;
    }
    if (elapsed < 0) {
        elapsed = 0;
    }
    int total_sec = static_cast<int>(elapsed / 1000);
    if (total_sec > 99 * 60 + 59) {
        total_sec = 99 * 60 + 59;
    }
    char buf[16] = {};
    std::snprintf(buf, sizeof(buf), "%02d:%02d", total_sec / 60, total_sec % 60);
    recorder_ui_set_elapsed(buf);
}

void paint_flags()
{
    const bool capture = g_capture.load();
    const bool paused = g_paused.load();
    const bool has_text = !recorder_session_transcript().empty();
    recorder_ui_set_can_start(!capture);
    recorder_ui_set_can_pause(capture && !paused);
    recorder_ui_set_can_resume(capture && paused);
    recorder_ui_set_can_stop(capture);
    recorder_ui_set_can_generate(has_text && !capture);
}

void paint_transcript()
{
    recorder_ui_set_transcript(recorder_session_transcript());
}

bool persist_transcript()
{
    const std::string text = recorder_session_transcript();
    if (text.empty()) {
        return false;
    }
    if (g_persisted.load() && !g_diagram_id.empty()) {
        return true;
    }
    if (g_title.empty()) {
        g_title = recorder_net_default_title();
    }
    std::string out_id;
    std::string out_title;
    const bool saved = recorder_net_finish(
        g_token,
        text,
        g_title,
        false,
        g_diagram_id,
        out_id,
        out_title
    );
    if (!saved) {
        return false;
    }
    g_diagram_id = out_id;
    if (!out_title.empty()) {
        g_title = out_title;
    }
    g_persisted.store(true);
    return true;
}

bool wait_for_token()
{
    if (kitty_net_load_token(g_token)) {
        ESP_LOGI(TAG, "token ready");
        return true;
    }
    recorder_ui_set_phase(RecorderUiPhase::error);
    recorder_ui_set_status("需要 mgat_");
    return false;
}

bool wait_for_network()
{
    for (int i = 0; i < 80 && g_run.load(); ++i) {
        if (recorder_ui_is_hidden()) {
            return false;
        }
        esp_netif_t *sta = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
        esp_netif_ip_info_t ip{};
        const bool have_ip = sta != nullptr
            && esp_netif_get_ip_info(sta, &ip) == ESP_OK
            && ip.ip.addr != 0;
        if (have_ip && std::time(nullptr) > 1700000000) {
            return true;
        }
        recorder_ui_set_status("连接中");
        boost::this_thread::sleep_for(boost::chrono::milliseconds(500));
    }
    recorder_ui_set_phase(RecorderUiPhase::error);
    recorder_ui_set_status("没有网络");
    return false;
}

bool home_is_allowed()
{
    if (!g_capture.load() && !g_block_home.load()) {
        return true;
    }
    if (g_capture.load()) {
        recorder_ui_set_status("先停止录音");
    }
    return false;
}

void apply_idle()
{
    g_capture.store(false);
    g_paused.store(false);
    g_block_home.store(false);
    g_started_at = 0;
    recorder_ui_set_busy(false);
    recorder_ui_set_mic_level(0);
    const bool has_text = !recorder_session_transcript().empty();
    recorder_ui_set_phase(has_text ? RecorderUiPhase::ready : RecorderUiPhase::idle);
    if (!has_text) {
        recorder_ui_set_status("等待开始");
    } else if (g_persisted.load()) {
        recorder_ui_set_status("已保存");
    } else {
        recorder_ui_set_status("可生成思维导图");
    }
    paint_flags();
    paint_elapsed();
    paint_transcript();
}

RecorderUiAction stream_until_pause_or_stop()
{
    std::vector<int16_t> frame(k_frame_samples, 0);
    if (!kitty_audio_mic_open()) {
        recorder_ui_set_phase(RecorderUiPhase::error);
        recorder_ui_set_status("麦克风不可用");
        return RecorderUiAction::none;
    }
    RecorderUiAction leftover = RecorderUiAction::none;
    while (g_run.load() && g_capture.load() && !g_paused.load() && !recorder_ui_is_hidden()) {
        leftover = recorder_ui_take_action();
        if (leftover == RecorderUiAction::pause || leftover == RecorderUiAction::start) {
            leftover = RecorderUiAction::none;
            pause_capture();
            break;
        }
        if (leftover == RecorderUiAction::stop) {
            break;
        }
        leftover = RecorderUiAction::none;
        if (!recorder_session_is_ready()) {
            break;
        }
        if (!kitty_audio_mic_read(frame.data(), frame.size())) {
            boost::this_thread::sleep_for(boost::chrono::milliseconds(k_hold_poll_ms));
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
        const uint8_t level = static_cast<uint8_t>(peak > 32767 ? 255 : peak / 128);
        recorder_session_set_mic_level(level);
        recorder_ui_set_mic_level(level);
        kitty_audio_boost_pcm(frame.data(), frame.size());
        recorder_session_send_pcm(frame.data(), frame.size());
        paint_transcript();
        paint_elapsed();
    }
    kitty_audio_mic_close();
    recorder_ui_set_mic_level(0);
    return leftover;
}

bool begin_capture()
{
    recorder_session_clear_transcript();
    g_diagram_id.clear();
    g_title.clear();
    g_persisted.store(false);
    g_paused_ms = 0;
    g_block_home.store(true);
    recorder_ui_set_busy(true);
    recorder_ui_set_phase(RecorderUiPhase::connecting);
    recorder_ui_set_status("连接中");
    if (!recorder_session_open(g_token)) {
        g_block_home.store(false);
        recorder_ui_set_busy(false);
        recorder_ui_set_phase(RecorderUiPhase::error);
        recorder_ui_set_status("无法连接");
        paint_flags();
        return false;
    }
    if (!recorder_session_wait_ready(15000)) {
        recorder_session_close();
        g_block_home.store(false);
        recorder_ui_set_busy(false);
        recorder_ui_set_phase(RecorderUiPhase::error);
        recorder_ui_set_status("语音服务超时");
        paint_flags();
        return false;
    }
    g_capture.store(true);
    g_paused.store(false);
    g_block_home.store(true);
    g_started_at = now_ms();
    recorder_ui_set_busy(false);
    recorder_ui_set_phase(RecorderUiPhase::recording);
    recorder_ui_set_status("录音中");
    paint_flags();
    const RecorderUiAction leftover = stream_until_pause_or_stop();
    if (leftover == RecorderUiAction::stop) {
        stop_capture();
    }
    return true;
}

void pause_capture()
{
    if (!g_capture.load() || g_paused.load()) {
        return;
    }
    g_paused_ms += now_ms() - g_started_at;
    g_paused.store(true);
    recorder_ui_set_phase(RecorderUiPhase::paused);
    recorder_ui_set_status("已暂停");
    recorder_ui_set_mic_level(0);
    paint_flags();
}

void resume_capture()
{
    if (!g_capture.load() || !g_paused.load()) {
        return;
    }
    g_started_at = now_ms();
    g_paused.store(false);
    recorder_ui_set_phase(RecorderUiPhase::recording);
    recorder_ui_set_status("录音中");
    paint_flags();
    const RecorderUiAction leftover = stream_until_pause_or_stop();
    if (leftover == RecorderUiAction::stop) {
        stop_capture();
    }
}

bool stop_capture()
{
    if (!g_capture.load()) {
        return true;
    }
    recorder_ui_set_busy(true);
    g_block_home.store(true);
    recorder_ui_set_phase(RecorderUiPhase::stopping);
    recorder_ui_set_status("停止中");
    if (!g_paused.load() && g_started_at > 0) {
        g_paused_ms += now_ms() - g_started_at;
    }
    g_paused.store(false);
    g_capture.store(false);
    recorder_session_request_stop();
    recorder_session_wait_stopped(2000);
    recorder_session_close();
    paint_transcript();
    const std::string text = recorder_session_transcript();
    if (text.empty()) {
        recorder_ui_set_busy(false);
        apply_idle();
        recorder_ui_set_status("没有听到内容");
        return false;
    }
    recorder_ui_set_phase(RecorderUiPhase::saving);
    recorder_ui_set_status("保存中");
    const bool saved = persist_transcript();
    recorder_ui_set_busy(false);
    apply_idle();
    if (!saved) {
        recorder_ui_set_status("转录已在本地");
    }
    return saved;
}

void generate_mindmap()
{
    if (g_capture.load()) {
        stop_capture();
    }
    const std::string text = recorder_session_transcript();
    if (text.empty()) {
        recorder_ui_set_status("先录一段再生成");
        return;
    }
    recorder_ui_set_busy(true);
    g_block_home.store(true);
    recorder_ui_set_phase(RecorderUiPhase::generating);
    recorder_ui_set_status("正在生成思维导图");
    paint_flags();
    if (g_title.empty()) {
        g_title = recorder_net_default_title();
    }
    std::string out_id;
    std::string out_title;
    const bool ok = recorder_net_finish(g_token, text, g_title, true, g_diagram_id, out_id, out_title);
    if (ok) {
        g_diagram_id = out_id;
        if (!out_title.empty()) {
            g_title = out_title;
        }
        g_persisted.store(true);
        recorder_ui_set_phase(RecorderUiPhase::ready);
        recorder_ui_set_status("思维导图已保存");
    } else {
        recorder_ui_set_phase(RecorderUiPhase::error);
        recorder_ui_set_status("生成失败");
    }
    g_block_home.store(false);
    recorder_ui_set_busy(false);
    paint_flags();
}

void handle_action(RecorderUiAction action)
{
    if (action == RecorderUiAction::start) {
        if (g_paused.load()) {
            resume_capture();
            return;
        }
        if (g_capture.load()) {
            pause_capture();
            return;
        }
        begin_capture();
        return;
    }
    if (action == RecorderUiAction::pause) {
        pause_capture();
        return;
    }
    if (action == RecorderUiAction::resume) {
        resume_capture();
        return;
    }
    if (action == RecorderUiAction::stop) {
        stop_capture();
        return;
    }
    if (action == RecorderUiAction::generate) {
        if (g_capture.load()) {
            return;
        }
        generate_mindmap();
    }
}

void reset_session_state()
{
    recorder_session_clear_transcript();
    g_diagram_id.clear();
    g_title.clear();
    g_persisted.store(false);
    g_paused_ms = 0;
    g_started_at = 0;
    g_capture.store(false);
    g_paused.store(false);
    g_block_home.store(false);
    recorder_ui_set_elapsed("00:00");
    recorder_ui_set_mic_level(0);
    recorder_ui_set_transcript("");
}

void leave_session(bool fresh_face)
{
    if (recorder_session_is_open()) {
        recorder_session_request_stop();
        recorder_session_wait_stopped(2000);
    }
    g_capture.store(false);
    g_paused.store(false);
    persist_transcript();
    recorder_session_close();
    kitty_audio_mic_close();
    if (fresh_face) {
        reset_session_state();
    }
}

void agent_loop()
{
    reset_session_state();
    recorder_ui_set_status("连接中");
    if (!wait_for_network() || !wait_for_token()) {
        g_run.store(false);
        g_thread_live.store(false);
        return;
    }
    apply_idle();
    while (g_run.load()) {
        if (recorder_ui_is_hidden()) {
            leave_session(true);
            while (g_run.load() && recorder_ui_is_hidden()) {
                boost::this_thread::sleep_for(boost::chrono::milliseconds(k_loop_ms));
            }
            if (g_run.load()) {
                apply_idle();
            }
            continue;
        }
        const RecorderUiAction action = recorder_ui_take_action();
        if (action != RecorderUiAction::none) {
            handle_action(action);
        }
        paint_elapsed();
        std::string error;
        if (recorder_session_take_error(error)) {
            recorder_ui_set_phase(RecorderUiPhase::error);
            recorder_ui_set_status(error);
            leave_session(false);
            g_capture.store(false);
            g_paused.store(false);
            paint_flags();
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_loop_ms));
    }
    leave_session(true);
    g_thread_live.store(false);
}

} // namespace

bool recorder_agent_start()
{
    g_run.store(true);
    bool expected = false;
    if (!g_thread_live.compare_exchange_strong(expected, true)) {
        return true;
    }
    BROOKESIA_THREAD_CONFIG_GUARD({
        .name = "recorder_agent",
        .stack_size = 24 * 1024,
        .stack_in_ext = true,
    });
    boost::thread(agent_loop).detach();
    return true;
}

void recorder_agent_stop()
{
    g_run.store(false);
    g_capture.store(false);
    g_paused.store(false);
    g_block_home.store(false);
}

bool recorder_agent_allows_home()
{
    return home_is_allowed();
}

extern "C" bool mindgraph_home_gesture_allowed(void)
{
    return recorder_agent_allows_home();
}
