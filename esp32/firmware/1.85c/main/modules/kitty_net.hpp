#pragma once

#include <string>
#include <vector>

struct KittyDiagramItem {
    std::string id;
    std::string title;
    std::string type;
};

bool kitty_net_server_configured();
std::string kitty_net_origin();
std::string kitty_net_account();
std::string kitty_net_ws_url(const std::string &scope);
bool kitty_net_load_token(std::string &token);
bool kitty_net_http_json(
    const char *method,
    const std::string &path,
    const std::string &body,
    const std::string &bearer,
    int &status,
    std::string &response,
    size_t max_bytes = 8192
);
bool kitty_net_bootstrap(const std::string &token, std::string &scope, std::string &title, std::string &diagram_type);
bool kitty_net_list_diagrams(const std::string &token, std::vector<KittyDiagramItem> &items);
const char *kitty_net_type_label(const std::string &type);
std::string kitty_net_diagram_caption(const std::string &title, const std::string &type);
bool kitty_net_enqueue_open_library(
    const std::string &token,
    const std::string &diagram_id,
    const std::string &title
);
bool kitty_net_create_mindmap(const std::string &token, KittyDiagramItem &item);
