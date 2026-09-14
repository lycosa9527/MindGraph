/*
 * SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: CC0-1.0
 */
#include "sdkconfig.h"
#include "brookesia/hal_interface.hpp"
#include "brookesia/hal_adaptor.hpp"
#include "brookesia/service_helper/media/audio.hpp"
#include "brookesia/service_manager/service/manager.hpp"
#include "private/utils.hpp"
#include "general_services.hpp"

using namespace esp_brookesia;

using AudioPlaybackHelper = esp_brookesia::service::helper::AudioPlayback;

bool GeneralServices::init()
{
    auto &service_manager = service::ServiceManager::get_instance();
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.init(), false, "Failed to initialize service manager");

    BROOKESIA_CHECK_FALSE_RETURN(init_audio(), false, "Failed to initialize audio");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.start(), false, "Failed to start service manager");

    BROOKESIA_LOGI("Service manager started successfully");

    return true;
}

bool GeneralServices::init_audio()
{
#if CONFIG_BROOKESIA_HAL_ADAPTOR_AUDIO_ENABLE_PROCESSOR_IMPL
    hal::AudioProcessorConfig processor_config {
        .playback = {
            .player_task = {
                .core_id = 0,
                .priority = 5,
                .stack_size = 4 * 1024,
#if CONFIG_SPIRAM_XIP_FROM_PSRAM
                .stack_in_ext = true,
#else
                .stack_in_ext = false,
#endif
            },
        },
        .encoder = {},
        .decoder = {},
        .afe = {
            .vad = hal::AudioProcessorAFE_VAD_Config{},
        },
    };
    BROOKESIA_CHECK_FALSE_RETURN(
        hal::AudioDevice::get_instance().set_processor_config(std::move(processor_config)),
        false,
        "Failed to configure audio processor"
    );
    BROOKESIA_LOGI("Audio processor AFE configured for PTT (AEC/NS/AGC, WakeNet off)");
#endif

    return true;
}

bool GeneralServices::start_audio_services()
{
#if !CONFIG_BROOKESIA_HAL_ADAPTOR_ENABLE_AUDIO_DEVICE
    BROOKESIA_LOGW("Audio HAL is disabled, skip audio services");
    return true;
#else
    if (!AudioPlaybackHelper::is_available()) {
        BROOKESIA_LOGW("Audio playback service is not available");
        return true;
    }

    auto &service_manager = service::ServiceManager::get_instance();
    static auto playback_binding = service_manager.bind(AudioPlaybackHelper::get_name().data());
    if (!playback_binding.is_valid()) {
        BROOKESIA_LOGW("Audio playback bind failed, continue without audio");
        return true;
    }

    return true;
#endif
}
