/*
 * SPDX-FileCopyrightText: 2026 北京思源智教科技有限公司
 *
 * SPDX-License-Identifier: CC0-1.0
 */
#include "round_shell.hpp"

#include <cstring>

#include "pinyin_t9.hpp"
#include "private/utils.hpp"
#include "lvgl.h"

namespace {

constexpr uint32_t k_timer_ms = 80;
constexpr uint32_t k_multitap_ms = 750;
constexpr size_t k_max_digits = 7;
constexpr size_t k_max_candidates = 4;
constexpr size_t k_glyph_bytes = 8;
constexpr int32_t k_panel_x = 56;
constexpr int32_t k_panel_y = 86;
constexpr int32_t k_panel_w = 248;
constexpr int32_t k_panel_h = 28;
constexpr int32_t k_cand_gap = 4;

struct ImeState {
    lv_obj_t *bar = nullptr;
    lv_obj_t *buttons[k_max_candidates] = {};
    char digits[k_max_digits + 1] = {};
    char glyphs[k_max_candidates][k_glyph_bytes] = {};
    size_t glyph_count = 0;
    uint32_t last_text_len = 0;
    uint32_t last_change_tick = 0;
    bool chinese = true;
};

ImeState g_ime;

bool ancestor_hidden(const lv_obj_t *object)
{
    for (const lv_obj_t *cursor = object; cursor != nullptr; cursor = lv_obj_get_parent(cursor)) {
        if (lv_obj_has_flag(cursor, LV_OBJ_FLAG_HIDDEN)) {
            return true;
        }
    }
    return false;
}

void visit_objects(lv_obj_t *root, lv_obj_t **keyboard, lv_obj_t **textarea)
{
    if (root == nullptr) {
        return;
    }
    if (*keyboard == nullptr && lv_obj_check_type(root, &lv_keyboard_class) && !ancestor_hidden(root)) {
        *keyboard = root;
    }
    if (*textarea == nullptr && lv_obj_check_type(root, &lv_textarea_class) && !ancestor_hidden(root)) {
        *textarea = root;
    }
    const uint32_t count = lv_obj_get_child_count(root);
    for (uint32_t index = 0; index < count; ++index) {
        visit_objects(lv_obj_get_child(root, index), keyboard, textarea);
    }
}

bool map_has_label(lv_obj_t *keyboard, const char *label)
{
    const char *const *map = lv_buttonmatrix_get_map(keyboard);
    if (map == nullptr || label == nullptr) {
        return false;
    }
    for (size_t index = 0; map[index] != nullptr && map[index][0] != '\0'; ++index) {
        if (std::strcmp(map[index], label) == 0) {
            return true;
        }
    }
    return false;
}

const char *utf8_next(const char *text)
{
    const auto lead = static_cast<unsigned char>(*text);
    if (lead < 0x80U) {
        return text + 1;
    }
    if ((lead & 0xE0U) == 0xC0U) {
        return text + 2;
    }
    if ((lead & 0xF0U) == 0xE0U) {
        return text + 3;
    }
    return text + 1;
}

size_t trailing_t9_digits(const char *text, char *digits, size_t digits_size)
{
    const size_t length = std::strlen(text);
    size_t start = length;
    while (start > 0) {
        const char value = text[start - 1];
        if (value < '2' || value > '9') {
            break;
        }
        --start;
    }
    const size_t count = length - start;
    if (count == 0 || count >= digits_size) {
        digits[0] = '\0';
        return 0;
    }
    std::memcpy(digits, text + start, count);
    digits[count] = '\0';
    return count;
}

void replace_suffix(lv_obj_t *textarea, size_t suffix_len, const char *replacement)
{
    for (size_t index = 0; index < suffix_len; ++index) {
        lv_textarea_delete_char(textarea);
    }
    if (replacement != nullptr && replacement[0] != '\0') {
        lv_textarea_add_text(textarea, replacement);
    }
}

void hide_candidates()
{
    if (g_ime.bar != nullptr) {
        lv_obj_add_flag(g_ime.bar, LV_OBJ_FLAG_HIDDEN);
    }
    g_ime.glyph_count = 0;
    g_ime.digits[0] = '\0';
}

void apply_round_clip()
{
    lv_obj_t *screen = lv_screen_active();
    if (screen == nullptr) {
        return;
    }
    lv_obj_set_style_radius(screen, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_clip_corner(screen, true, 0);
}

void on_candidate_clicked(lv_event_t *event)
{
    lv_obj_t *button = lv_event_get_target_obj(event);
    if (button == nullptr) {
        return;
    }
    size_t chosen = k_max_candidates;
    for (size_t index = 0; index < k_max_candidates; ++index) {
        if (g_ime.buttons[index] == button) {
            chosen = index;
            break;
        }
    }
    if (chosen >= g_ime.glyph_count) {
        return;
    }
    lv_obj_t *keyboard = nullptr;
    lv_obj_t *textarea = nullptr;
    visit_objects(lv_screen_active(), &keyboard, &textarea);
    if (textarea == nullptr) {
        return;
    }
    const size_t suffix = std::strlen(g_ime.digits);
    replace_suffix(textarea, suffix, g_ime.glyphs[chosen]);
    hide_candidates();
}

void ensure_candidate_bar()
{
    if (g_ime.bar != nullptr) {
        return;
    }
    g_ime.bar = lv_obj_create(lv_layer_top());
    lv_obj_set_pos(g_ime.bar, k_panel_x, k_panel_y);
    lv_obj_set_size(g_ime.bar, k_panel_w, k_panel_h);
    lv_obj_set_style_pad_all(g_ime.bar, 0, 0);
    lv_obj_set_style_border_width(g_ime.bar, 0, 0);
    lv_obj_set_style_bg_opa(g_ime.bar, LV_OPA_TRANSP, 0);
    lv_obj_set_flex_flow(g_ime.bar, LV_FLEX_FLOW_ROW);
    lv_obj_set_style_pad_column(g_ime.bar, k_cand_gap, 0);
    const int32_t button_width = (k_panel_w - (k_cand_gap * 3)) / static_cast<int32_t>(k_max_candidates);
    for (size_t index = 0; index < k_max_candidates; ++index) {
        lv_obj_t *button = lv_button_create(g_ime.bar);
        lv_obj_set_size(button, button_width, k_panel_h);
        lv_obj_set_style_radius(button, 8, 0);
        lv_obj_add_event_cb(button, on_candidate_clicked, LV_EVENT_CLICKED, nullptr);
        lv_obj_t *label = lv_label_create(button);
        lv_label_set_text(label, "");
        lv_obj_center(label);
        g_ime.buttons[index] = button;
    }
    hide_candidates();
}

void show_candidates(const char *packed_chars, size_t count)
{
    ensure_candidate_bar();
    g_ime.glyph_count = 0;
    const char *cursor = packed_chars;
    for (size_t index = 0; index < count && index < k_max_candidates && *cursor != '\0'; ++index) {
        const char *next = utf8_next(cursor);
        const size_t glyph_len = static_cast<size_t>(next - cursor);
        if (glyph_len >= k_glyph_bytes) {
            break;
        }
        std::memcpy(g_ime.glyphs[index], cursor, glyph_len);
        g_ime.glyphs[index][glyph_len] = '\0';
        lv_obj_t *label = lv_obj_get_child(g_ime.buttons[index], 0);
        lv_label_set_text(label, g_ime.glyphs[index]);
        lv_obj_remove_flag(g_ime.buttons[index], LV_OBJ_FLAG_HIDDEN);
        ++g_ime.glyph_count;
        cursor = next;
    }
    for (size_t index = g_ime.glyph_count; index < k_max_candidates; ++index) {
        lv_obj_add_flag(g_ime.buttons[index], LV_OBJ_FLAG_HIDDEN);
    }
    if (g_ime.glyph_count == 0) {
        hide_candidates();
        return;
    }
    lv_obj_remove_flag(g_ime.bar, LV_OBJ_FLAG_HIDDEN);
}

void commit_english_multitap(lv_obj_t *textarea, const char *text)
{
    const size_t length = std::strlen(text);
    if (length == 0) {
        return;
    }
    const char digit = text[length - 1];
    if (digit < '2' || digit > '9') {
        return;
    }
    size_t start = length;
    while (start > 0 && text[start - 1] == digit) {
        --start;
    }
    const unsigned taps = static_cast<unsigned>(length - start);
    const char letter = t9_multitap_letter(digit, taps, true);
    if (letter == '\0') {
        return;
    }
    const char replacement[2] = {letter, '\0'};
    replace_suffix(textarea, taps, replacement);
}

void refresh_chinese(lv_obj_t *textarea, const char *text)
{
    char digits[k_max_digits + 1] = {};
    const size_t count = trailing_t9_digits(text, digits, sizeof(digits));
    if (count == 0) {
        hide_candidates();
        return;
    }
    std::memcpy(g_ime.digits, digits, count + 1);
    char packed[k_max_candidates * k_glyph_bytes] = {};
    const size_t glyphs = t9_collect_chars(digits, packed, sizeof(packed), k_max_candidates);
    show_candidates(packed, glyphs);
}

void on_shell_tick(lv_timer_t * /*timer*/)
{
    apply_round_clip();
    lv_obj_t *keyboard = nullptr;
    lv_obj_t *textarea = nullptr;
    visit_objects(lv_screen_active(), &keyboard, &textarea);
    if (keyboard == nullptr || textarea == nullptr) {
        hide_candidates();
        return;
    }
    g_ime.chinese = map_has_label(keyboard, "EN");
    const char *text = lv_textarea_get_text(textarea);
    if (text == nullptr) {
        hide_candidates();
        return;
    }
    const uint32_t length = static_cast<uint32_t>(std::strlen(text));
    const uint32_t now = lv_tick_get();
    if (length != g_ime.last_text_len) {
        g_ime.last_text_len = length;
        g_ime.last_change_tick = now;
    }
    if (g_ime.chinese) {
        refresh_chinese(textarea, text);
        return;
    }
    hide_candidates();
    if (length > 0 && now - g_ime.last_change_tick >= k_multitap_ms) {
        commit_english_multitap(textarea, text);
        g_ime.last_text_len = static_cast<uint32_t>(std::strlen(lv_textarea_get_text(textarea)));
        g_ime.last_change_tick = now;
    }
}

} // namespace

bool RoundShell::start()
{
    lv_timer_create(on_shell_tick, k_timer_ms, nullptr);
    BROOKESIA_LOGI("Round shell clip and 九宫格 IME started");
    return true;
}
