#include "kitty_agent_shared.hpp"

#include "mbedtls/base64.h"

#include "kitty_ws.hpp"

std::string g_kitty_token;
std::string g_kitty_scope;
std::string g_kitty_diagram_type = "circle_map";
std::string g_kitty_asr_text;
std::string g_kitty_utterance_id;
std::string g_kitty_choice_a;
std::string g_kitty_choice_b;
std::mutex g_kitty_asr_mutex;
bool g_kitty_asr_done = false;
std::atomic<bool> g_kitty_speaking{false};
std::atomic<bool> g_kitty_playing_pcm{false};
std::atomic<bool> g_kitty_interrupt{false};
std::atomic<bool> g_kitty_listen_auto{false};
std::atomic<bool> g_kitty_pending_auto_listen{false};
std::atomic<uint32_t> g_kitty_utterance{1};

bool kitty_b64_encode(const uint8_t *data, size_t length, std::string &out)
{
    size_t needed = 0;
    mbedtls_base64_encode(nullptr, 0, &needed, data, length);
    out.assign(needed, '\0');
    size_t written = 0;
    if (mbedtls_base64_encode(reinterpret_cast<unsigned char *>(out.data()), needed, &written, data, length) != 0) {
        out.clear();
        return false;
    }
    if (written < out.size()) {
        out.resize(written);
    }
    while (!out.empty() && out.back() == '\0') {
        out.pop_back();
    }
    return !out.empty();
}

bool kitty_b64_decode(const std::string &in, std::vector<uint8_t> &out)
{
    size_t needed = 0;
    if (mbedtls_base64_decode(nullptr, 0, &needed, reinterpret_cast<const unsigned char *>(in.data()), in.size()) != 0
        && needed == 0) {
        return false;
    }
    out.assign(needed, 0);
    size_t written = 0;
    if (mbedtls_base64_decode(out.data(), out.size(), &written, reinterpret_cast<const unsigned char *>(in.data()), in.size())
        != 0) {
        out.clear();
        return false;
    }
    out.resize(written);
    return true;
}

void kitty_send_obj(boost::json::object obj)
{
    kitty_ws_send_json(boost::json::serialize(obj));
}
