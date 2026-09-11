#pragma once

#include <atomic>
#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

#include "boost/json.hpp"

#include "kitty_net.hpp"

constexpr size_t k_kitty_frame_samples = 1600;
constexpr uint32_t k_kitty_hold_poll_ms = 20;
constexpr int k_kitty_choice_max = 4;

extern std::string g_kitty_token;
extern std::string g_kitty_scope;
extern std::string g_kitty_diagram_type;
extern std::string g_kitty_asr_text;
extern std::string g_kitty_utterance_id;
extern std::string g_kitty_choices[k_kitty_choice_max];
extern std::mutex g_kitty_asr_mutex;
extern bool g_kitty_asr_done;
extern std::atomic<bool> g_kitty_speaking;
extern std::atomic<bool> g_kitty_playing_pcm;
extern std::atomic<bool> g_kitty_interrupt;
extern std::atomic<bool> g_kitty_listen_auto;
extern std::atomic<bool> g_kitty_pending_auto_listen;
extern std::atomic<uint32_t> g_kitty_utterance;

bool kitty_b64_encode(const uint8_t *data, size_t length, std::string &out);
bool kitty_b64_decode(const std::string &in, std::vector<uint8_t> &out);
void kitty_send_obj(boost::json::object obj);
void kitty_agent_handle_inbound(const std::string &raw);
void kitty_agent_run_ptt();
void kitty_agent_run_auto_listen();
void kitty_agent_commit_asr();
void kitty_agent_send_clarify_choice(int index);
void kitty_agent_begin_user_turn();
void kitty_agent_begin_user_turn_once();
bool kitty_agent_has_library_scope();
bool kitty_agent_bind_ws();
bool kitty_agent_connect_session();
bool kitty_agent_attach_scope(const KittyDiagramItem &item);
