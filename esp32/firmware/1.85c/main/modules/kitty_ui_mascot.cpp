#include "kitty_ui_mascot.hpp"

extern const uint8_t kitty_mascot_png_start[] asm("_binary_kitty_mascot_png_start");
extern const uint8_t kitty_mascot_png_end[] asm("_binary_kitty_mascot_png_end");
extern const uint8_t kitty_mic_png_start[] asm("_binary_kitty_mic_png_start");
extern const uint8_t kitty_mic_png_end[] asm("_binary_kitty_mic_png_end");

namespace {

constexpr int32_t k_scale_one = 256;
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
    const int32_t scale = hold ? k_scale_hold : k_scale_one;
    lv_obj_set_style_transform_pivot_x(mic, 32, 0);
    lv_obj_set_style_transform_pivot_y(mic, 32, 0);
    lv_obj_set_style_transform_scale_x(mic, scale, 0);
    lv_obj_set_style_transform_scale_y(mic, scale, 0);
    const uint8_t pulse = hold ? static_cast<uint8_t>(40 + (level > 200 ? 200 : level) / 2) : 0;
    if (ring_a != nullptr) {
        if (hold) {
            lv_obj_remove_flag(ring_a, LV_OBJ_FLAG_HIDDEN);
            lv_obj_set_style_border_opa(ring_a, static_cast<lv_opa_t>(80 + pulse / 3), 0);
            lv_obj_set_style_border_color(ring_a, lv_color_hex(k_wave), 0);
        } else {
            lv_obj_add_flag(ring_a, LV_OBJ_FLAG_HIDDEN);
        }
    }
    if (ring_b != nullptr) {
        if (hold) {
            lv_obj_remove_flag(ring_b, LV_OBJ_FLAG_HIDDEN);
            lv_obj_set_style_border_opa(ring_b, static_cast<lv_opa_t>(40 + pulse / 4), 0);
            lv_obj_set_style_border_color(ring_b, lv_color_hex(k_wave), 0);
        } else {
            lv_obj_add_flag(ring_b, LV_OBJ_FLAG_HIDDEN);
        }
    }
}

void kitty_ui_mascot_tick(KittyUiState state)
{
    (void)state;
}
