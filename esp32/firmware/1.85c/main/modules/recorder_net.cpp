#include "recorder_net.hpp"

#include <cstdio>
#include <ctime>
#include <string>

#include "boost/json.hpp"
#include "esp_log.h"

#include "kitty_net.hpp"

namespace {

constexpr const char *TAG = "recorder_net";
constexpr int k_save_timeout_ms = 20000;
constexpr int k_generate_timeout_ms = 180000;

bool json_string_field(const boost::json::value &root, const char *key, std::string &out)
{
    if (!root.is_object()) {
        return false;
    }
    const auto *field = root.as_object().if_contains(key);
    if (field == nullptr || !field->is_string()) {
        return false;
    }
    out = std::string(field->as_string().c_str());
    return !out.empty();
}

} // namespace

std::string recorder_net_ws_url()
{
    std::string origin = kitty_net_origin();
    if (origin.rfind("https://", 0) == 0) {
        origin.replace(0, 5, "wss");
    } else if (origin.rfind("http://", 0) == 0) {
        origin.replace(0, 4, "ws");
    }
    return origin + "/api/ws/voice-notes";
}

std::string recorder_net_default_title()
{
    const std::time_t now = std::time(nullptr);
    std::tm local{};
    localtime_r(&now, &local);
    char buf[80] = {};
    std::snprintf(
        buf,
        sizeof(buf),
        "voice recording_%04d%02d%02d%02d%02d",
        local.tm_year + 1900,
        local.tm_mon + 1,
        local.tm_mday,
        local.tm_hour,
        local.tm_min
    );
    return buf;
}

bool recorder_net_finish(
    const std::string &token,
    const std::string &transcript,
    const std::string &title,
    bool generate,
    const std::string &diagram_id,
    std::string &out_id,
    std::string &out_title
)
{
    out_id.clear();
    out_title.clear();
    if (transcript.empty() || !kitty_net_server_configured()) {
        return false;
    }
    boost::json::object body;
    body["transcript"] = transcript;
    body["title"] = title.empty() ? recorder_net_default_title() : title;
    body["generate"] = generate;
    if (!diagram_id.empty()) {
        body["diagram_id"] = diagram_id;
    }
    int status = 0;
    std::string response;
    const int timeout_ms = generate ? k_generate_timeout_ms : k_save_timeout_ms;
    if (!kitty_net_http_json(
            "POST",
            "/api/voice-notes/watch/finish",
            boost::json::serialize(body),
            token,
            status,
            response,
            4096,
            timeout_ms
        )) {
        ESP_LOGW(TAG, "finish transport failed");
        return false;
    }
    if (status != 200) {
        ESP_LOGW(TAG, "finish status=%d", status);
        return false;
    }
    boost::system::error_code parse_err;
    const auto root = boost::json::parse(response, parse_err);
    if (parse_err || !root.is_object()) {
        return false;
    }
    const auto *ok = root.as_object().if_contains("ok");
    if (ok == nullptr || !ok->is_bool() || !ok->as_bool()) {
        return false;
    }
    json_string_field(root, "diagram_id", out_id);
    json_string_field(root, "title", out_title);
    return !out_id.empty();
}
