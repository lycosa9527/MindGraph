#include "super_kitty_agent_shared.hpp"

#include "kitty_ws.hpp"

std::string g_super_kitty_token;
std::string g_super_kitty_scope;
std::string g_super_kitty_diagram_type = "mindmap";
std::string g_super_kitty_asr_text;
std::string g_super_kitty_utterance_id;
std::string g_super_kitty_choices[k_super_kitty_choice_max];
std::mutex g_super_kitty_asr_mutex;
bool g_super_kitty_asr_done = false;
std::atomic<bool> g_super_kitty_speaking{false};
std::atomic<bool> g_super_kitty_playing_pcm{false};
std::atomic<bool> g_super_kitty_interrupt{false};
std::atomic<bool> g_super_kitty_asr_late_commit{false};
std::atomic<uint32_t> g_super_kitty_utterance{1};

void super_kitty_send_obj(boost::json::object obj)
{
    kitty_ws_send_json(boost::json::serialize(obj));
}
