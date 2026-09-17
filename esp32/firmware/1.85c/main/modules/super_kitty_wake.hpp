#pragma once

#include <cstddef>
#include <cstdint>

bool super_kitty_wake_start();
void super_kitty_wake_stop();
void super_kitty_wake_feed(const int16_t *samples, size_t count);
void super_kitty_wake_poll();
bool super_kitty_wake_take_address();
void super_kitty_wake_ignore(bool ignore);
bool super_kitty_wake_multinet_ready();
bool super_kitty_wake_create_finished();
