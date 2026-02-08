/*
 * SPDX-FileCopyrightText: 2024-2025 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include <mutex>
#include <chrono>
#include "esp_brookesia_systems_internal.h"
#if !ESP_BROOKESIA_SPEAKER_DISPLAY_ENABLE_DEBUG_LOG
#   define ESP_BROOKESIA_UTILS_DISABLE_DEBUG_LOG
#endif
#include "private/esp_brookesia_speaker_utils.hpp"
#include "esp_brookesia_speaker_app.hpp"
#include "esp_brookesia_speaker_display.hpp"

using namespace std;

namespace esp_brookesia::systems::speaker {

Display::OnDummyDrawSignal Display::on_dummy_draw_signal;

Display::Display(base::Context &core, const Data &data):
    base::Display(core, core.getData().display),
    _data(data),
    _app_launcher(core, data.app_launcher.data),
    _quick_settings(core, data.quick_settings.data),
    _keyboard(core, data.keyboard.data)
{
}

Display::~Display()
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    if (!del()) {
        ESP_UTILS_LOGE("Failed to delete");
    }

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
}

bool Display::begin(void)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    ESP_UTILS_CHECK_FALSE_RETURN(!checkInitialized(), false, "Already initialized");

    const auto main_screen_obj = _system_context.getDisplay().getMainScreenObjectPtr();
    ESP_UTILS_CHECK_FALSE_RETURN(
        _app_launcher.begin(main_screen_obj->getNativeHandle()), false, "Begin app launcher failed"
    );

    const auto system_screen_obj = _system_context.getDisplay().getSystemScreenObjectPtr();
    ESP_UTILS_CHECK_FALSE_RETURN(
        _keyboard.begin(system_screen_obj), false, "Begin keyboard failed"
    );
    ESP_UTILS_CHECK_FALSE_RETURN(
        _keyboard.setVisible(false), false, "Set keyboard visible failed"
    );

    ESP_UTILS_CHECK_FALSE_RETURN(
        _quick_settings.begin(*system_screen_obj), false, "Begin quick settings failed"
    );
    ESP_UTILS_CHECK_FALSE_RETURN(
        _quick_settings.setVisible(false), false, "Set quick settings visible failed"
    );

    _dummy_draw_mask = std::make_unique<gui::LvContainer>(_system_context.getDisplay().getSystemScreenObjectPtr());
    ESP_UTILS_CHECK_NULL_RETURN(_dummy_draw_mask, false, "Create dummy draw mask failed");
    _dummy_draw_mask->moveForeground();
    _dummy_draw_mask->setStyleAttribute(gui::StyleFlag::STYLE_FLAG_HIDDEN | gui::StyleFlag::STYLE_FLAG_CLICKABLE, true);

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();

    return true;
}

bool Display::del(void)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    if (!checkInitialized()) {
        return true;
    }

    if (!_app_launcher.del()) {
        ESP_UTILS_LOGE("Delete app launcher failed");
    }

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

bool Display::processAppInstall(base::App *app)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    App *speaker_app = static_cast<App *>(app);
    AppLauncherIconInfo_t icon_info = {};

    ESP_UTILS_CHECK_NULL_RETURN(speaker_app, false, "Invalid speaker app");
    ESP_UTILS_CHECK_FALSE_RETURN(checkInitialized(), false, "Not initialized");
    ESP_UTILS_LOGD("Param: app_id(%d)", speaker_app->getId());

    // Process app launcher
    icon_info = (AppLauncherIconInfo_t) {
        speaker_app->getName(), speaker_app->getLauncherIcon(), speaker_app->getId()
    };
    if (speaker_app->getLauncherIcon().resource == nullptr) {
        ESP_UTILS_LOGW("No launcher icon provided, use default icon");
        icon_info.image = _data.app_launcher.default_image;
        speaker_app->setLauncherIconImage(icon_info.image);
    }
    ESP_UTILS_CHECK_FALSE_RETURN(_app_launcher.addIcon(speaker_app->getActiveConfig().app_launcher_page_index, icon_info),
                                 false, "Add launcher icon failed");

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

bool Display::processAppUninstall(base::App *app)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    App *speaker_app = static_cast<App *>(app);

    ESP_UTILS_CHECK_NULL_RETURN(speaker_app, false, "Invalid speaker app");
    ESP_UTILS_CHECK_FALSE_RETURN(checkInitialized(), false, "Not initialized");
    ESP_UTILS_LOGD("Param: app_id(%d)", speaker_app->getId());

    // Process app launcher
    ESP_UTILS_CHECK_FALSE_RETURN(_app_launcher.removeIcon(speaker_app->getId()), false, "Remove launcher icon failed");

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

bool Display::processAppRun(base::App *app)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    App *speaker_app = static_cast<App *>(app);

    ESP_UTILS_CHECK_NULL_RETURN(speaker_app, false, "Invalid speaker app");
    ESP_UTILS_CHECK_FALSE_RETURN(checkInitialized(), false, "Not initialized");
    ESP_UTILS_LOGD("Param: app_id(%d)", speaker_app->getId());

    // const App::Config &app_data = speaker_app->getActiveConfig();

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

bool Display::processAppResume(base::App *app)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    App *speaker_app = static_cast<App *>(app);

    ESP_UTILS_CHECK_NULL_RETURN(speaker_app, false, "Invalid speaker app");
    ESP_UTILS_CHECK_FALSE_RETURN(checkInitialized(), false, "Not initialized");
    ESP_UTILS_LOGD("Param: app_id(%d)", speaker_app->getId());

    // const App::Config &app_data = speaker_app->getActiveConfig();

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

bool Display::processAppClose(base::App *app)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    App *speaker_app = static_cast<App *>(app);

    ESP_UTILS_CHECK_NULL_RETURN(speaker_app, false, "Invalid speaker app");
    ESP_UTILS_CHECK_FALSE_RETURN(checkInitialized(), false, "Not initialized");
    ESP_UTILS_LOGD("Param: app_id(%d)", speaker_app->getId());

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

bool Display::processMainScreenLoad(void)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    ESP_UTILS_CHECK_FALSE_RETURN(checkInitialized(), false, "Not initialized");

    lv_obj_t *main_screen = _system_context.getDisplay().getMainScreen();
    ESP_UTILS_CHECK_FALSE_RETURN(lv_obj_is_valid(main_screen), false, "Invalid main screen");
    lv_scr_load(main_screen);

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

bool Display::getAppVisualArea(base::App *app, lv_area_t &app_visual_area) const
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    App *speaker_app = static_cast<App *>(app);

    ESP_UTILS_CHECK_NULL_RETURN(speaker_app, false, "Invalid speaker app");
    ESP_UTILS_LOGD("Param: app_id(%d)", speaker_app->getId());

    lv_area_t visual_area = {
        .x1 = 0,
        .y1 = 0,
        .x2 = (lv_coord_t)(_system_context.getData().screen_size.width - 1),
        .y2 = (lv_coord_t)(_system_context.getData().screen_size.height - 1),
    };

    app_visual_area = visual_area;

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

bool Display::processDummyDraw(bool enable)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    ESP_UTILS_CHECK_FALSE_RETURN(checkInitialized(), false, "Not initialized");
    ESP_UTILS_LOGD("Param: enable(%d)", enable);

    _dummy_draw_mask->setStyleAttribute(gui::StyleFlag::STYLE_FLAG_HIDDEN, !enable);
    on_dummy_draw_signal(enable);

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

bool Display::startBootAnimation(void)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

#if !ESP_BROOKESIA_GUI_ENABLE_ANIM_PLAYER
    // Animation player is disabled - skip boot animation (like Waveshare's approach)
    ESP_UTILS_LOGD("Boot animation disabled (AnimPlayer not enabled), skipping");
    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return false;
#else
    // Early check: If partition label is empty or max_files is 0, skip boot animation entirely
    // This aligns with official recommendation to avoid animations when not needed
    if (std::holds_alternative<gui::AnimPlayerPartitionConfig>(_data.boot_animation.data.source)) {
        const auto &partition_config = std::get<gui::AnimPlayerPartitionConfig>(_data.boot_animation.data.source);
        if (partition_config.partition_label == nullptr || 
            partition_config.partition_label[0] == '\0' ||
            partition_config.max_files == 0) {
            ESP_UTILS_LOGD("Boot animation disabled (empty partition config), skipping");
            ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
            return false;
        }
    }

    try {
        _boot_animation = std::make_unique<gui::AnimPlayer>();
        if (!_boot_animation->begin(_data.boot_animation.data)) {
            ESP_UTILS_LOGW("Begin boot animation failed - animation partition may be missing or corrupted");
            ESP_UTILS_LOGW("This is normal if boot animation is not configured (per official recommendation)");
            _boot_animation.reset();
            ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
            return false;
        }
        
        // Connect flush callback to notify completion - critical for animation to continue
        _boot_animation_flush_connection = gui::AnimPlayer::flush_ready_signal.connect([this](int x_start, int y_start, int x_end, int y_end, const void *data, gui::AnimPlayer *player) {
            ESP_UTILS_LOG_TRACE_GUARD();
            
            // For boot animation, we need to notify flush finished to continue playing frames
            // The actual rendering is handled by the underlying animation player
            if (player != nullptr) {
                player->notifyFlushFinished();
            }
        });
        
        if (!_boot_animation->sendEvent({
            0, gui::AnimPlayer::Operation::PlayOncePause, {true, true}
        }, true, &_boot_animation_future)) {
            ESP_UTILS_LOGW("Send boot animation event failed");
            _boot_animation_flush_connection.disconnect();
            _boot_animation.reset();
            ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
            return false;
        }
    } catch (const std::exception &e) {
        ESP_UTILS_LOGE("Exception in startBootAnimation: %s", e.what());
        if (_boot_animation != nullptr) {
            _boot_animation.reset();
        }
        ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
        return false;
    } catch (...) {
        ESP_UTILS_LOGE("Unknown exception in startBootAnimation");
        if (_boot_animation != nullptr) {
            _boot_animation.reset();
        }
        ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
        return false;
    }

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
#endif
}

bool Display::waitBootAnimationStop(void)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

#if !ESP_BROOKESIA_GUI_ENABLE_ANIM_PLAYER
    // Animation player is disabled - no animation to wait for
    ESP_UTILS_LOGD("Boot animation disabled (AnimPlayer not enabled), skipping wait");
    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
#else
    // If boot animation was not started (startBootAnimation failed), just return success
    if (_boot_animation == nullptr) {
        ESP_UTILS_LOGD("Boot animation not started, skipping wait");
        ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
        return true;
    }

    // CRITICAL FIX: Add timeout to prevent infinite hang if animation crashes
    // Boot animation should complete within 30 seconds, otherwise skip it
    constexpr auto BOOT_ANIMATION_TIMEOUT_MS = 30000;
    auto status = _boot_animation_future.wait_for(std::chrono::milliseconds(BOOT_ANIMATION_TIMEOUT_MS));
    
    if (status == std::future_status::timeout) {
        ESP_UTILS_LOGW("Boot animation timeout, skipping wait");
        // Try to stop the animation if it's still running
        if (_boot_animation != nullptr) {
            _boot_animation->sendEvent({0, gui::AnimPlayer::Operation::Stop, {true, true}}, true, nullptr);
        }
    } else {
        // Wait completed normally
        try {
            _boot_animation_future.wait();
        } catch (const std::exception &e) {
            ESP_UTILS_LOGW("Exception waiting for boot animation: %s", e.what());
        } catch (...) {
            ESP_UTILS_LOGW("Unknown exception waiting for boot animation");
        }
    }
    
    // Disconnect flush callback
    if (_boot_animation_flush_connection.connected()) {
        _boot_animation_flush_connection.disconnect();
    }
    
    _boot_animation.reset();

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
#endif
}

bool Display::calibrateData(const gui::StyleSize &screen_size, Data &data)
{
    ESP_UTILS_LOG_TRACE_ENTER_WITH_THIS();

    // Initialize the size of flex widgets
    if (data.flags.enable_app_launcher_flex_size) {
        data.app_launcher.data.main.y_start = 0;
        data.app_launcher.data.main.size.flags.enable_height_percent = 0;
        data.app_launcher.data.main.size.height = screen_size.height;
    }

    // App table
    ESP_UTILS_CHECK_FALSE_RETURN(
        AppLauncher::calibrateData(screen_size, *this, data.app_launcher.data), false,
        "Calibrate app launcher data failed"
    );
    // Quick settings
    ESP_UTILS_CHECK_FALSE_RETURN(
        QuickSettings::calibrateData(screen_size, *this, data.quick_settings.data), false,
        "Calibrate quick settings data failed"
    );
    // Keyboard
    ESP_UTILS_CHECK_FALSE_RETURN(
        Keyboard::calibrateData(screen_size, *this, data.keyboard.data), false,
        "Calibrate keyboard data failed"
    );

    ESP_UTILS_LOG_TRACE_EXIT_WITH_THIS();
    return true;
}

} // namespace esp_brookesia::systems::speaker
