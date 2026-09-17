#pragma once

#include <cstddef>
#include <cstdint>

bool super_kitty_audio_init();
bool super_kitty_audio_start();
void super_kitty_audio_stop();
bool super_kitty_audio_read(int16_t *samples, size_t count);
uint8_t super_kitty_audio_level();
void super_kitty_audio_clear();
bool super_kitty_audio_using_afe();
