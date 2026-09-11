#pragma once

#include <cstdint>
#include <string>

bool recorder_session_open(const std::string &token);
void recorder_session_close();
bool recorder_session_is_open();
bool recorder_session_is_ready();
bool recorder_session_wait_ready(int timeout_ms);
bool recorder_session_send_pcm(const int16_t *samples, size_t count);
bool recorder_session_request_stop();
bool recorder_session_wait_stopped(int timeout_ms);
void recorder_session_handle_json(const std::string &raw);
std::string recorder_session_transcript();
void recorder_session_clear_transcript();
bool recorder_session_take_error(std::string &message);
uint8_t recorder_session_mic_level();
void recorder_session_set_mic_level(uint8_t level);
