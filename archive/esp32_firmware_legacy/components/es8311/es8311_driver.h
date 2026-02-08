#ifndef ES8311_DRIVER_H
#define ES8311_DRIVER_H

#include <stdint.h>
#include <stddef.h>

#define ES8311_I2C_ADDR 0x18

bool es8311_init();
bool es8311_start();
bool es8311_stop();
bool es8311_write_audio(int16_t* pcm_data, size_t samples);
void es8311_set_volume(uint8_t volume);
void es8311_set_sample_rate(uint32_t sample_rate);

#endif