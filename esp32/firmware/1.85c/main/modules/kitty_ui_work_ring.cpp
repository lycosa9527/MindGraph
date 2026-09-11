#include "kitty_ui_work_ring.hpp"

namespace {

constexpr int32_t k_face = 360;
constexpr int32_t k_inset = 6;
constexpr uint32_t k_period_ms = 2500;
constexpr uint32_t k_head = 0x22C55E;
constexpr uint32_t k_mid = 0x4ADE80;
constexpr uint32_t k_tail = 0x86EFAC;

lv_obj_t *make_sweep(lv_obj_t *parent, int32_t start, int32_t end, uint32_t color, int32_t width, lv_opa_t opa)
{
    lv_obj_t *arc = lv_arc_create(parent);
    lv_obj_set_size(arc, k_face - k_inset * 2, k_face - k_inset * 2);
    lv_obj_center(arc);
    lv_arc_set_bg_angles(arc, 0, 360);
    lv_arc_set_angles(arc, start, end);
    lv_obj_set_style_arc_width(arc, width, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(arc, lv_color_hex(color), LV_PART_INDICATOR);
    lv_obj_set_style_arc_opa(arc, opa, LV_PART_INDICATOR);
    lv_obj_set_style_arc_rounded(arc, true, LV_PART_INDICATOR);
    lv_obj_set_style_arc_opa(arc, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_opa(arc, LV_OPA_TRANSP, LV_PART_KNOB);
    lv_obj_set_style_pad_all(arc, 0, LV_PART_KNOB);
    lv_obj_clear_flag(arc, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(arc, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(arc, LV_OBJ_FLAG_GESTURE_BUBBLE);
    return arc;
}

bool is_working(KittyUiState state)
{
    return state == KittyUiState::thinking || state == KittyUiState::speaking;
}

} // namespace

lv_obj_t *kitty_ui_work_ring_build(lv_obj_t *parent)
{
    lv_obj_t *ring = lv_obj_create(parent);
    lv_obj_remove_style_all(ring);
    lv_obj_set_size(ring, k_face, k_face);
    lv_obj_set_pos(ring, 0, 0);
    lv_obj_set_style_bg_opa(ring, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(ring, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(ring, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(ring, LV_OBJ_FLAG_HIDDEN);
    make_sweep(ring, 40, 92, k_tail, 2, LV_OPA_20);
    make_sweep(ring, 16, 44, k_mid, 2, LV_OPA_40);
    make_sweep(ring, 0, 20, k_head, 3, LV_OPA_70);
    return ring;
}

void kitty_ui_work_ring_paint(lv_obj_t *ring, KittyUiState state)
{
    if (ring == nullptr) {
        return;
    }
    if (!is_working(state)) {
        lv_obj_add_flag(ring, LV_OBJ_FLAG_HIDDEN);
        return;
    }
    lv_obj_remove_flag(ring, LV_OBJ_FLAG_HIDDEN);
    const int32_t rotation = static_cast<int32_t>((lv_tick_get() % k_period_ms) * 360 / k_period_ms);
    const uint32_t count = lv_obj_get_child_count(ring);
    for (uint32_t i = 0; i < count; ++i) {
        lv_arc_set_rotation(lv_obj_get_child(ring, i), rotation);
    }
}
