#include "sdkconfig.h"

#include <ctime>
#include <cstring>
#include <string>
#include <vector>

#include "boost/json.hpp"
#include "esp_http_client.h"
#include "esp_log.h"

#include "kitty_net.hpp"

namespace {

constexpr const char *TAG = "kitty_net";
constexpr int k_http_timeout_ms = 12000;
constexpr size_t k_http_max = 8192;

#if defined(CONFIG_MINDGRAPH_KITTY_SERVER_URL)
constexpr const char *k_origin = CONFIG_MINDGRAPH_KITTY_SERVER_URL;
#else
constexpr const char *k_origin = "";
#endif
#if defined(CONFIG_MINDGRAPH_KITTY_MGAT)
constexpr const char *k_baked_mgat = CONFIG_MINDGRAPH_KITTY_MGAT;
#else
constexpr const char *k_baked_mgat = "";
#endif
#if defined(CONFIG_MINDGRAPH_KITTY_ACCOUNT)
constexpr const char *k_account = CONFIG_MINDGRAPH_KITTY_ACCOUNT;
#else
constexpr const char *k_account = "";
#endif

std::string trim_slash(const char *raw)
{
    std::string out = raw != nullptr ? raw : "";
    while (!out.empty() && out.back() == '/') {
        out.pop_back();
    }
    return out;
}

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

bool kitty_net_server_configured()
{
    return !trim_slash(k_origin).empty();
}

std::string kitty_net_origin()
{
    return trim_slash(k_origin);
}

std::string kitty_net_account()
{
    return k_account != nullptr ? k_account : "";
}

std::string kitty_net_ws_url(const std::string &scope)
{
    std::string origin = kitty_net_origin();
    if (origin.rfind("https://", 0) == 0) {
        origin.replace(0, 5, "wss");
    } else if (origin.rfind("http://", 0) == 0) {
        origin.replace(0, 4, "ws");
    }
    return origin + "/ws/kitty/" + scope;
}

bool kitty_net_load_token(std::string &token)
{
    if (k_baked_mgat == nullptr || k_baked_mgat[0] == '\0') {
        token.clear();
        return false;
    }
    token = k_baked_mgat;
    return true;
}

bool kitty_net_http_json(
    const char *method,
    const std::string &path,
    const std::string &body,
    const std::string &bearer,
    int &status,
    std::string &response,
    size_t max_bytes,
    int timeout_ms
)
{
    const size_t cap = max_bytes == 0 ? k_http_max : max_bytes;
    const std::string url = kitty_net_origin() + path;
    if (url.size() <= path.size()) {
        return false;
    }
    esp_http_client_config_t config = {};
    config.url = url.c_str();
    config.timeout_ms = timeout_ms > 0 ? timeout_ms : k_http_timeout_ms;
    config.transport_type = HTTP_TRANSPORT_OVER_SSL;
    config.tls_version = ESP_HTTP_CLIENT_TLS_VER_TLS_1_2;
    config.user_agent = "MindGraph-Watch/1.0";
    ESP_LOGI(TAG, "https %s %s tls=1.2", method, path.c_str());
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == nullptr) {
        return false;
    }
    esp_http_client_set_method(client, std::strcmp(method, "GET") == 0 ? HTTP_METHOD_GET : HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Accept", "application/json");
    esp_http_client_set_header(client, "X-MG-Client", "esp32-watch");
    if (!bearer.empty()) {
        const std::string auth = "Bearer " + bearer;
        esp_http_client_set_header(client, "Authorization", auth.c_str());
    }
    if (k_account != nullptr && k_account[0] != '\0') {
        esp_http_client_set_header(client, "X-MG-Account", k_account);
    }
    if (!body.empty()) {
        esp_http_client_set_header(client, "Content-Type", "application/json");
        esp_http_client_set_post_field(client, body.c_str(), static_cast<int>(body.size()));
    }
    esp_err_t err = esp_http_client_open(client, static_cast<int>(body.size()));
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "http open %s failed: %s", url.c_str(), esp_err_to_name(err));
        esp_http_client_cleanup(client);
        return false;
    }
    if (!body.empty()) {
        esp_http_client_write(client, body.c_str(), static_cast<int>(body.size()));
    }
    const int content_length = static_cast<int>(esp_http_client_fetch_headers(client));
    status = esp_http_client_get_status_code(client);
    response.clear();
    char chunk[512];
    int remaining = content_length > 0 ? content_length : static_cast<int>(cap);
    while (remaining > 0 && response.size() < cap) {
        const int want = remaining > static_cast<int>(sizeof(chunk)) ? static_cast<int>(sizeof(chunk)) : remaining;
        const int got = esp_http_client_read(client, chunk, want);
        if (got <= 0) {
            break;
        }
        response.append(chunk, static_cast<size_t>(got));
        if (content_length > 0) {
            remaining -= got;
        } else if (got < want) {
            break;
        }
    }
    esp_http_client_close(client);
    esp_http_client_cleanup(client);
    ESP_LOGI(TAG, "http %s %s -> %d (%u B)", method, path.c_str(), status, static_cast<unsigned>(response.size()));
    return true;
}

bool kitty_net_bootstrap(const std::string &token, std::string &scope, std::string &title, std::string &diagram_type)
{
    int status = 0;
    std::string response;
    if (!kitty_net_http_json("GET", "/api/kitty/mobile_open_bootstrap", "", token, status, response)) {
        return false;
    }
    if (status == 401) {
        return false;
    }
    if (status != 200) {
        return false;
    }
    boost::system::error_code parse_err;
    const auto root = boost::json::parse(response, parse_err);
    if (parse_err || !root.is_object()) {
        return false;
    }
    const auto &obj = root.as_object();
    scope.clear();
    title.clear();
    diagram_type = "circle_map";
    if (const auto *focus = obj.if_contains("desktop_focus"); focus != nullptr && focus->is_object()) {
        const auto *lib = focus->as_object().if_contains("diagram_library_id");
        if (lib != nullptr && lib->is_string()) {
            scope = std::string(lib->as_string().c_str());
        }
    }
    if (scope.empty()) {
        json_string_field(root, "recommended_scope", scope);
    }
    json_string_field(root, "diagram_type", diagram_type);
    if (const auto *ctx = obj.if_contains("context"); ctx != nullptr && ctx->is_object()) {
        const auto &ctx_obj = ctx->as_object();
        if (const auto *name = ctx_obj.if_contains("diagram_title"); name != nullptr && name->is_string()) {
            title = std::string(name->as_string().c_str());
        } else if (const auto *alt = ctx_obj.if_contains("title"); alt != nullptr && alt->is_string()) {
            title = std::string(alt->as_string().c_str());
        }
    }
    if (scope.empty()) {
        scope = "watch";
    }
    if (title.size() > 24) {
        title.resize(23);
        title += "…";
    }
    return true;
}

bool kitty_net_list_diagrams(const std::string &token, std::vector<KittyDiagramItem> &items)
{
    int status = 0;
    std::string response;
    items.clear();
    if (!kitty_net_http_json("GET", "/api/diagrams?page=1&page_size=12", "", token, status, response, 48 * 1024)) {
        return false;
    }
    if (status != 200) {
        return false;
    }
    boost::system::error_code parse_err;
    const auto root = boost::json::parse(response, parse_err);
    if (parse_err || !root.is_object()) {
        return false;
    }
    const auto *list = root.as_object().if_contains("diagrams");
    if (list == nullptr || !list->is_array()) {
        return false;
    }
    for (const auto &entry : list->as_array()) {
        if (!entry.is_object()) {
            continue;
        }
        KittyDiagramItem item;
        if (!json_string_field(entry, "id", item.id)) {
            continue;
        }
        json_string_field(entry, "title", item.title);
        if (item.title.empty()) {
            item.title = "未命名";
        }
        json_string_field(entry, "diagram_type", item.type);
        if (item.type.empty()) {
            item.type = "circle_map";
        }
        items.push_back(std::move(item));
        if (items.size() >= 12) {
            break;
        }
    }
    return true;
}

const char *kitty_net_type_label(const std::string &type)
{
    if (type == "circle_map") {
        return "圆圈图";
    }
    if (type == "bubble_map") {
        return "气泡图";
    }
    if (type == "double_bubble_map") {
        return "双气泡图";
    }
    if (type == "tree_map") {
        return "树形图";
    }
    if (type == "brace_map") {
        return "括号图";
    }
    if (type == "flow_map") {
        return "流程图";
    }
    if (type == "multi_flow_map") {
        return "复流程图";
    }
    if (type == "bridge_map") {
        return "桥形图";
    }
    if (type == "mindmap" || type == "mind_map") {
        return "思维导图";
    }
    if (type == "concept_map") {
        return "概念图";
    }
    if (type.empty()) {
        return "图";
    }
    return type.c_str();
}

std::string kitty_net_diagram_caption(const std::string &title, const std::string &type)
{
    if (title.empty()) {
        return "图库";
    }
    return title + " · " + kitty_net_type_label(type);
}

bool kitty_net_enqueue_open_library(
    const std::string &token,
    const std::string &diagram_id,
    const std::string &title
)
{
    if (diagram_id.empty()) {
        return false;
    }
    boost::json::object body;
    body["kind"] = "open_library_diagram";
    body["diagram_library_id"] = diagram_id;
    if (!title.empty()) {
        body["title"] = title;
    }
    int status = 0;
    std::string response;
    if (!kitty_net_http_json(
            "POST",
            "/api/kitty/desktop_action/enqueue",
            boost::json::serialize(body),
            token,
            status,
            response
        )) {
        return false;
    }
    if (status != 200) {
        ESP_LOGW(TAG, "desktop enqueue status=%d", status);
        return false;
    }
    boost::system::error_code parse_err;
    const auto root = boost::json::parse(response, parse_err);
    if (parse_err || !root.is_object()) {
        return false;
    }
    const auto *ok = root.as_object().if_contains("ok");
    return ok != nullptr && ok->is_bool() && ok->as_bool();
}

namespace {

boost::json::object blank_mindmap_spec()
{
    boost::json::array children;
    for (int branch = 1; branch <= 4; ++branch) {
        boost::json::object node;
        const std::string label = "分支" + std::to_string(branch);
        node["label"] = label;
        node["text"] = label;
        boost::json::array kids;
        for (int child = 1; child <= 2; ++child) {
            boost::json::object leaf;
            const std::string child_label =
                "子项" + std::to_string(branch) + "." + std::to_string(child);
            leaf["label"] = child_label;
            leaf["text"] = child_label;
            leaf["children"] = boost::json::array();
            kids.push_back(std::move(leaf));
        }
        node["children"] = std::move(kids);
        children.push_back(std::move(node));
    }
    boost::json::object spec;
    spec["topic"] = "中心主题";
    spec["children"] = std::move(children);
    spec["_mindmap_theme"] = "rainbow";
    spec["_mindmap_diagram_style"] = "classic";
    return spec;
}

void report_ui_create(const std::string &token, const std::string &diagram_id, const std::string &title)
{
    boost::json::object body;
    body["request_id"] = "w" + std::to_string(static_cast<long long>(std::time(nullptr)));
    body["ingress_source"] = "ui_create";
    body["text"] = title;
    body["lane"] = "mobile";
    int status = 0;
    std::string response;
    kitty_net_http_json(
        "POST",
        "/api/kitty/session/" + diagram_id + "/ingress",
        boost::json::serialize(body),
        token,
        status,
        response
    );
}

} // namespace

bool kitty_net_create_mindmap(const std::string &token, KittyDiagramItem &item)
{
    item = {};
    boost::json::object body;
    body["title"] = "新建思维导图";
    body["diagram_type"] = "mindmap";
    body["spec"] = blank_mindmap_spec();
    body["language"] = "zh";
    int status = 0;
    std::string response;
    if (!kitty_net_http_json("POST", "/api/diagrams", boost::json::serialize(body), token, status, response)) {
        return false;
    }
    if (status != 200 && status != 201) {
        ESP_LOGW(TAG, "create mindmap status=%d", status);
        return false;
    }
    boost::system::error_code parse_err;
    const auto root = boost::json::parse(response, parse_err);
    if (parse_err || !json_string_field(root, "id", item.id)) {
        return false;
    }
    json_string_field(root, "title", item.title);
    if (item.title.empty()) {
        item.title = "新建思维导图";
    }
    json_string_field(root, "diagram_type", item.type);
    if (item.type.empty()) {
        item.type = "mindmap";
    }
    report_ui_create(token, item.id, item.title);
    ESP_LOGI(TAG, "created library mindmap id=%s", item.id.c_str());
    return true;
}
