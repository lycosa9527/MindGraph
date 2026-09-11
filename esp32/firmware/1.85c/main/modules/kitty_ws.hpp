#pragma once

#include <functional>
#include <string>

bool kitty_ws_connect(const std::string &url, const std::string &bearer);
void kitty_ws_close();
bool kitty_ws_is_open();
bool kitty_ws_send_json(const std::string &json);
void kitty_ws_set_handler(std::function<void(const std::string &)> handler);
