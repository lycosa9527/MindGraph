#pragma once

#include <cstdint>
#include <functional>
#include <string>

enum class KittyWsOwner : uint8_t {
    none = 0,
    kitty,
    slides,
    recorder,
    training,
    super_kitty,
};

bool kitty_ws_connect(const std::string &url, const std::string &bearer, KittyWsOwner owner);
void kitty_ws_close();
void kitty_ws_close_owned(KittyWsOwner owner);
bool kitty_ws_is_open();
bool kitty_ws_is_connecting();
bool kitty_ws_owned_by(KittyWsOwner owner);
bool kitty_ws_send_json(const std::string &json);
void kitty_ws_set_handler(std::function<void(const std::string &)> handler);
