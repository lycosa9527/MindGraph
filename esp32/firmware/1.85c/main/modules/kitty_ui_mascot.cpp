#include "kitty_ui_mascot.hpp"

extern const uint8_t kitty_mascot_png_start[] asm("_binary_kitty_mascot_png_start");
extern const uint8_t kitty_mascot_png_end[] asm("_binary_kitty_mascot_png_end");
extern const uint8_t kitty_mic_png_start[] asm("_binary_kitty_mic_png_start");
extern const uint8_t kitty_mic_png_end[] asm("_binary_kitty_mic_png_end");

namespace {

constexpr int32_t k_scale_hold = 320;
constexpr uint32_t k_wave = 0xA78BFA;

lv_image_dsc_t g_mascot_png;
lv_image_dsc_t g_mic_png;

void load_png(lv_image_dsc_t &dsc, const uint8_t *start, const uint8_t *end)
{
    dsc.data = start;
    dsc.data_size = static_cast<uint32_t>(end - start);
}

} // namespace

void kitty_ui_mascot_build(lv_obj_t *host)
{
    if (host == nullptr) {
        return;
    }
    lv_obj_clear_flag(host, LV_OBJ_FLAG_CLICKABLE);
    load_png(g_mascot_png, kitty_mascot_png_start, kitty_mascot_png_end);
    lv_obj_t *image = lv_image_create(host);
    lv_image_set_src(image, &g_mascot_png);
    lv_obj_center(image);
    lv_obj_clear_flag(image, LV_OBJ_FLAG_CLICKABLE);
}

void kitty_ui_mic_draw(lv_obj_t *mic)
{
    if (mic == nullptr) {
        return;
    }
    load_png(g_mic_png, kitty_mic_png_start, kitty_mic_png_end);
    lv_obj_t *image = lv_image_create(mic);
    lv_image_set_src(image, &g_mic_png);
    lv_image_set_scale(image, 56);
    lv_obj_center(image);
    lv_obj_clear_flag(image, LV_OBJ_FLAG_CLICKABLE);
}

void kitty_ui_mic_paint(lv_obj_t *mic, lv_obj_t *ring_a, lv_obj_t *ring_b, bool hold, uint8_t level)
{
    if (mic == nullptr) {
        return;
    }
    static lv_obj_t *last_mic = nullptr;
    static bool last_hold = false;
    static uint8_t last_level = 0;
    if (last_mic == mic && hold == last_hold && (!hold || level == last_level)) {
        return;
    }
    last_mic = mic;
    last_hold = hold;
    last_level = level;
    lv_obj_set_style_bg_color(mic, lv_color_hex(hold ? 0x4F46E5 : 0x7C3AED), 0);
    if (!hold) {
        lv_obj_remove_local_style_prop(mic, LV_STYLE_TRANSFORM_SCALE_X, 0);
        lv_obj_remove_local_style_prop(mic, LV_STYLE_TRANSFORM_SCALE_Y, 0);
        lv_obj_remove_local_style_prop(mic, LV_STYLE_TRANSFORM_PIVOT_X, 0);
        lv_obj_remove_local_style_prop(mic, LV_STYLE_TRANSFORM_PIVOT_Y, 0);
        if (ring_a != nullptr) {
            lv_obj_add_flag(ring_a, LV_OBJ_FLAG_HIDDEN);
        }
        if (ring_b != nullptr) {
            lv_obj_add_flag(ring_b, LV_OBJ_FLAG_HIDDEN);
        }
        return;
    }
    lv_obj_set_style_transform_pivot_x(mic, 32, 0);
    lv_obj_set_style_transform_pivot_y(mic, 32, 0);
    lv_obj_set_style_transform_scale_x(mic, k_scale_hold, 0);
    lv_obj_set_style_transform_scale_y(mic, k_scale_hold, 0);
    const uint8_t pulse = static_cast<uint8_t>(40 + (level > 200 ? 200 : level) / 2);
    if (ring_a != nullptr) {
        lv_obj_remove_flag(ring_a, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_style_border_opa(ring_a, static_cast<lv_opa_t>(80 + pulse / 3), 0);
        lv_obj_set_style_border_color(ring_a, lv_color_hex(k_wave), 0);
    }
    if (ring_b != nullptr) {
        lv_obj_remove_flag(ring_b, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_style_border_opa(ring_b, static_cast<lv_opa_t>(40 + pulse / 4), 0);
        lv_obj_set_style_border_color(ring_b, lv_color_hex(k_wave), 0);
    }
}

void kitty_ui_mascot_tick(KittyUiState state)
{
    (void)state;
}
