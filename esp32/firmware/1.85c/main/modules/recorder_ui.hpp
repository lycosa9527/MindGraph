#pragma once

#include <cstdint>
#include <string>

enum class RecorderUiPhase {
    idle,
    connecting,
    recording,
    paused,
    stopping,
    saving,
    generating,
    ready,
    error,
};

enum class RecorderUiAction {
    none,
    start,
    pause,
    resume,
    stop,
    generate,
};

bool recorder_ui_start();
void recorder_ui_show();
void recorder_ui_hide();
bool recorder_ui_is_hidden();
void recorder_ui_set_phase(RecorderUiPhase phase);
void recorder_ui_set_status(const std::string &text);
void recorder_ui_set_elapsed(const std::string &text);
void recorder_ui_set_transcript(const std::string &text);
void recorder_ui_set_mic_level(uint8_t level);
void recorder_ui_set_can_start(bool enabled);
void recorder_ui_set_can_pause(bool enabled);
void recorder_ui_set_can_resume(bool enabled);
void recorder_ui_set_can_stop(bool enabled);
void recorder_ui_set_can_generate(bool enabled);
void recorder_ui_set_busy(bool busy);
RecorderUiAction recorder_ui_take_action();
