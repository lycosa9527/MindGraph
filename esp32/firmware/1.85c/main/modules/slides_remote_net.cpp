#include "slides_remote_net.hpp"

#include "boost/json.hpp"

#include "kitty_net.hpp"

namespace {

constexpr size_t k_http_cap = 16 * 1024;

bool json_string(const boost::json::object &obj, const char *key, std::string &out)
{
    const auto *field = obj.if_contains(key);
    if (field == nullptr || field->is_null() || !field->is_string()) {
        return false;
    }
    out = std::string(field->as_string().c_str());
    return !out.empty();
}

int json_int(const boost::json::object &obj, const char *key, int fallback)
{
    const auto *field = obj.if_contains(key);
    if (field == nullptr || field->is_null()) {
        return fallback;
    }
    if (field->is_int64()) {
        return static_cast<int>(field->as_int64());
    }
    if (field->is_uint64()) {
        return static_cast<int>(field->as_uint64());
    }
    return fallback;
}

bool json_bool(const boost::json::object &obj, const char *key, bool fallback)
{
    const auto *field = obj.if_contains(key);
    if (field == nullptr || field->is_null() || !field->is_bool()) {
        return fallback;
    }
    return field->as_bool();
}

} // namespace

bool slides_http_json(
    const std::string &token,
    const char *method,
    const std::string &path,
    const std::string &body,
    int &status,
    std::string &response
)
{
    return kitty_net_http_json(method, path, body, token, status, response, k_http_cap);
}

bool slides_parse_snapshot(const std::string &body, SlidesSnapshot &out)
{
    boost::system::error_code err;
    const auto root = boost::json::parse(body, err);
    if (err || !root.is_object()) {
        return false;
    }
    const auto &obj = root.as_object();
    out = SlidesSnapshot{};
    json_string(obj, "state", out.state);
    json_string(obj, "session_id", out.session_id);
    json_string(obj, "title", out.title);
    json_string(obj, "traversal", out.traversal);
    out.slide_index = json_int(obj, "slide_index", 0);
    out.slide_count = json_int(obj, "slide_count", 0);
    out.autoplay = json_bool(obj, "autoplay", false);
    out.can_prev = json_bool(obj, "can_prev", false);
    out.can_next = json_bool(obj, "can_next", false);
    return true;
}

bool slides_session_live(const SlidesSnapshot &snap)
{
    return snap.state == "live" && !snap.session_id.empty();
}

bool slides_fetch_active(const std::string &token, SlidesSnapshot &out, int &status)
{
    std::string body;
    if (!slides_http_json(token, "GET", "/api/slides/remote/sessions/active", "", status, body)) {
        return false;
    }
    if (status != 200) {
        return false;
    }
    return slides_parse_snapshot(body, out);
}

bool slides_post_command(const std::string &token, const std::string &json, int &status)
{
    std::string body;
    return slides_http_json(token, "POST", "/api/slides/remote/command", json, status, body);
}
