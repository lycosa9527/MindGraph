#pragma once

#include <cstddef>
#include <cstdint>

bool kitty_audio_init();
void kitty_audio_run_smoke();
bool kitty_audio_mic_open();
void kitty_audio_mic_close();
bool kitty_audio_mic_read(int16_t *samples, size_t count);
void kitty_audio_boost_pcm(int16_t *samples, size_t count);
bool kitty_audio_spk_open();
void kitty_audio_spk_close();
bool kitty_audio_spk_write(const int16_t *samples, size_t count);
void kitty_audio_spk_stop();
void kitty_audio_play_click();
