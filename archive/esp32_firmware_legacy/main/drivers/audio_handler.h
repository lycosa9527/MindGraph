#ifndef AUDIO_HANDLER_H
#define AUDIO_HANDLER_H

#include <stdint.h>
#include <stddef.h>

#define AUDIO_SAMPLE_RATE 16000
#define AUDIO_BITS_PER_SAMPLE 16
#define AUDIO_CHANNELS 1
#define AUDIO_BUFFER_SIZE 1024

bool audio_init();
void audio_start_capture();
void audio_stop_capture();
void audio_start_playback();
void audio_stop_playback();
bool audio_is_capturing();
bool audio_is_playing();
void audio_process();
int16_t* audio_get_capture_buffer(size_t* samples);
void audio_play_buffer(int16_t* data, size_t samples);

#endif