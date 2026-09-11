#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

bool kitty_opus_open();
void kitty_opus_close();
bool kitty_opus_encode(const int16_t *samples, size_t count, std::vector<uint8_t> &out);
