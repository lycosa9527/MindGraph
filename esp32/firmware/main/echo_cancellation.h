#ifndef ECHO_CANCELLATION_H
#define ECHO_CANCELLATION_H

#include <stdint.h>
#include <stddef.h>

void echo_cancellation_init();
void echo_cancellation_process(
    int16_t* mic1_data,
    int16_t* mic2_data,
    int16_t* speaker_out,
    int16_t* output,
    size_t samples
);
void echo_cancellation_reset();

#endif