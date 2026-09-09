/*
 * SPDX-FileCopyrightText: 2026 北京思源智教科技有限公司
 *
 * SPDX-License-Identifier: CC0-1.0
 */
#pragma once

#include <cstddef>
#include <cstdint>

struct PinyinEntry {
    const char *pinyin;
    const char *chars;
};

char t9_digit_for_letter(char letter);
const char *t9_letters_for_digit(char digit);
char t9_multitap_letter(char digit, unsigned taps, bool uppercase);
bool t9_pinyin_matches(const char *pinyin, const char *digits);
size_t t9_collect_chars(const char *digits, char *out, size_t out_bytes, size_t max_chars);
