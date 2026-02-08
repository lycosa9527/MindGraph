#ifndef ES7210_DRIVER_H
#define ES7210_DRIVER_H

#include <stdint.h>
#include <stddef.h>

#define ES7210_I2C_ADDR 0x40
#define ES7210_PDM_CHANNELS 2

bool es7210_init();
bool es7210_start();
bool es7210_stop();
bool es7210_read_pdm(int16_t* mic1_data, int16_t* mic2_data, size_t samples);
void es7210_set_sample_rate(uint32_t sample_rate);
void es7210_set_gain(uint8_t channel, uint8_t gain);

#endif