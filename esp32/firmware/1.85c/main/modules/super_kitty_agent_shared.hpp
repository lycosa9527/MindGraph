#pragma once

#include <atomic>
#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

#include "boost/json.hpp"

#include "kitty_net.hpp"

constexpr size_t k_super_kitty_frame_samples = 1600;
constexpr uint32_t k_super_kitty_hold_poll_ms = 20;
constexpr int k_super_kitty_choice_max = 4;

extern std::string g_super_kitty_token;
extern std::string g_super_kitty_scope;
extern std::string g_super_kitty_diagram_type;
extern std::string g_super_kitty_asr_text;
extern std::string g_super_kitty_utterance_id;
extern std::string g_super_kitty_choices[k_super_kitty_choice_max];
extern std::mutex g_super_kitty_asr_mutex;
extern bool g_super_kitty_asr_done;
extern std::atomic<bool> g_super_kitty_speaking;
extern std::atomic<bool> g_super_kitty_playing_pcm;
extern std::atomic<bool> g_super_kitty_interrupt;
extern std::atomic<bool> g_super_kitty_asr_late_commit;
extern std::atomic<uint32_t> g_super_kitty_utterance;

void super_kitty_send_obj(boost::json::object obj);
void super_kitty_agent_handle_inbound(const std::string &raw);
void super_kitty_agent_run_addressed_listen();
void super_kitty_agent_commit_asr();
void super_kitty_agent_send_clarify_choice(int index);
void super_kitty_agent_begin_user_turn();
void super_kitty_agent_begin_user_turn_once();
bool super_kitty_agent_is_library_id(const std::string &id);
bool super_kitty_agent_has_library_scope();
bool super_kitty_agent_bind_ws();
bool super_kitty_agent_connect_session(bool adopt_desktop);
bool super_kitty_agent_attach_scope(const KittyDiagramItem &item);
bool super_kitty_agent_follow_library(const KittyDiagramItem &item);
