#pragma once

#include <string>
#include <vector>

struct SlidesDiagramItem {
    std::string id;
    std::string title;
    std::string type;
};

enum class SlidesUiPhase {
    wait,
    live,
    error,
};

enum class SlidesUiAction {
    none,
    prev,
    next,
    autoplay,
    first_level,
    deep,
    host,
    toggle_library,
    pick_diagram,
};

bool slides_ui_start();
void slides_ui_show();
void slides_ui_hide();
bool slides_ui_is_hidden();
void slides_ui_set_phase(SlidesUiPhase phase);
void slides_ui_set_status(const std::string &text);
void slides_ui_set_step(int index, int count);
void slides_ui_set_can_prev(bool enabled);
void slides_ui_set_can_next(bool enabled);
void slides_ui_set_autoplay(bool on);
void slides_ui_set_deep(bool deep);
void slides_ui_set_pad_enabled(bool enabled);
void slides_ui_set_busy(bool busy);
void slides_ui_set_library(const std::string &text);
void slides_ui_set_picker_status(const std::string &text);
void slides_ui_set_diagrams(const std::vector<SlidesDiagramItem> &items);
bool slides_ui_picker_needs_list();
SlidesUiAction slides_ui_take_action();
int slides_ui_take_diagram_index();
