#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include <string>
#include <cstring>
#include <sys/param.h>
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "button_handler.h"
#include "ui_manager.h"
#include "battery_manager.h"
#include "rtc_manager.h"
#include "motion_sensor.h"
#include "wifi_manager.h"
#include "i2c_bus_manager.h"
#include "websocket_client.h"
#include "config_manager.h"
#include "loading_screen.h"
#include "standby_screen.h"
#include "launcher.h"
#include "state_coordinator.h"
#include "apps/smart_response_app.h"
#include "apps/dify_app.h"
#include "font_manager.h"
#include "audio_handler.h"
#include "sd_storage.h"
#include "usb_msc.h"
#include "display_utils.h"
#include "lvgl.h"
#include "driver/uart.h"
#include <cstdio>
#include <cstring>


static const char* TAG = "MAIN";

ButtonHandler buttonHandler;
BatteryManager batteryManager;
RTCManager rtcManager;
MotionSensor motionSensor;
SDStorage sdStorage;
static bool system_initialized = false;

static void pwr_button_callback() {
    ESP_LOGI(TAG, "PWR Button pressed");
    if (standby_screen_is_visible()) {
        launcher_show();
    } else if (launcher_is_visible()) {
        launcher_hide();
    } else {
        launcher_show();
    }
}

static void boot_button_callback() {
    ESP_LOGI(TAG, "BOOT Button pressed");
    if (launcher_is_visible()) {
        launcher_hide();
    } else if (standby_screen_is_visible()) {
        launcher_show();
    }
}

static void app_launch_callback(AppType app_type) {
    ESP_LOGI(TAG, "Launching app: %d", app_type);
    switch (app_type) {
        case APP_SMART_RESPONSE:
            smart_response_app_show();
            break;
        case APP_DIFY_XIAOZHI:
            dify_app_show();
            break;
        default:
            break;
    }
}

static void serial_command_task(void* pvParameters);

// NOTE: LVGL task is now handled by BSP (bsp_display_start() creates it automatically)
// No need for custom lvgl_task anymore

static void main_task(void* pvParameters) {
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "=== BOOT START ===");
    ESP_LOGI(TAG, "=== ESP32 Smart Response (ZhiHui) ===");
    ESP_LOGI(TAG, "Initializing...");
    
    // NOTE: Power management is now initialized in app_main() before tasks start
    // This prevents watchdog timeout during I2C operations
    vTaskDelay(pdMS_TO_TICKS(100)); // Let power stabilize
    
    // 2. Font manager
    ESP_LOGI(TAG, "Initializing font manager...");
    font_manager_init();
    ESP_LOGI(TAG, "Font manager initialized");
    
    // Set default font for display (LVGL v9)
    lv_display_t* disp = lv_display_get_default();
    if (disp != nullptr) {
        const lv_font_t* default_font = font_manager_get_font(16, true);
        if (default_font != nullptr) {
            // Note: LVGL v9 doesn't have lv_display_set_default_font, fonts are set per object
            ESP_LOGI(TAG, "Chinese font available for use as default");
        }
    }
    
    // NOTE: Display/BSP initialization is now done in app_main() before tasks start
    // This ensures proper initialization order and matches factory example pattern
    
    // 4. Wait for LVGL to be ready before creating UI components
    vTaskDelay(pdMS_TO_TICKS(200));
    
    // 5. NOW create UI components (after display is fully initialized)
    ESP_LOGI(TAG, "Initializing loading screen...");
    loading_screen_init();
    // standby_screen_init() will be called later after state coordinator is initialized
    ESP_LOGI(TAG, "Loading screen initialized");
    
    // Show loading screen - function manages its own display locking
    ESP_LOGI(TAG, "Showing loading screen...");
    loading_screen_show();
    ESP_LOGI(TAG, "Loading screen shown");
    
    // 6. Give LVGL task time to render initial screen (after UI is created)
    vTaskDelay(pdMS_TO_TICKS(100));
    
    // Loading screen functions now manage their own locking internally
    // No need for outer bsp_display_lock/unlock around these calls
    loading_screen_set_message("初始化硬件...");
    loading_screen_set_progress(10);
    
    buttonHandler.init();
    buttonHandler.setPWRCallback(pwr_button_callback);
    buttonHandler.setBOOTCallback(boot_button_callback);
    loading_screen_set_progress(20);
    
    loading_screen_set_progress(30);
    
    // Initialize I2C bus and scan for devices
    ESP_LOGI(TAG, "Initializing I2C bus...");
    get_i2c_bus_handle();
    scan_i2c_devices();
    
    if (!rtcManager.init()) {
        ESP_LOGW(TAG, "RTC initialization failed");
    }
    loading_screen_set_progress(40);
    
    if (!motionSensor.init()) {
        ESP_LOGW(TAG, "Motion sensor initialization failed");
    }
    loading_screen_set_progress(50);
    
    loading_screen_set_message("初始化SD卡...");
    if (!sdStorage.init()) {
        ESP_LOGW(TAG, "SD card initialization failed");
    }
    // USB Mass Storage disabled for now
    // if (usb_msc_init()) {
    //     ESP_LOGI(TAG, "USB Mass Storage initialized");
    // }
    loading_screen_set_progress(55);
    
    loading_screen_set_message("初始化音频...");
    if (!audio_init()) {
        ESP_LOGW(TAG, "Audio initialization failed");
    }
    loading_screen_set_progress(60);
    
    loading_screen_set_message("初始化状态管理...");
    state_coordinator_init();
    
    // Initialize standby screen after state coordinator is ready
    standby_screen_init();
    
    loading_screen_set_message("加载配置...");
    config_init();
    loading_screen_set_progress(70);
    
    loading_screen_set_message("初始化WiFi...");
    wifi_init();
    loading_screen_set_progress(80);
    
    loading_screen_set_message("连接中...");
    std::string ssid = config_get("wifi_ssid", "");
    std::string password = config_get("wifi_password", "");
    
    if (ssid.length() > 0) {
        // Use configured WiFi from NVS
        ESP_LOGI(TAG, "Connecting to configured WiFi: %s", ssid.c_str());
        wifi_connect(ssid.c_str(), password.c_str());
    } else {
        // No config found - try default WiFi (baked into firmware)
        ESP_LOGI(TAG, "No WiFi config found, trying default WiFi: BE3600");
        if (wifi_connect("BE3600", "19930101")) {
            ESP_LOGI(TAG, "Connected to default WiFi: BE3600");
            // Save default WiFi to config for future use
            config_save("wifi_ssid", "BE3600");
            config_save("wifi_password", "19930101");
        } else {
            // Default WiFi failed - start SoftAP mode
            ESP_LOGW(TAG, "Default WiFi connection failed, starting SoftAP mode");
            wifi_start_softap();
            ESP_LOGI(TAG, "Started SoftAP mode - connect to 'ESP32-ZhiHui' to configure");
        }
    }
    loading_screen_set_progress(90);
    
    launcher_set_app_launch_callback(app_launch_callback);
    ESP_LOGI(TAG, "[DEBUG] === Starting screen transition: loading -> standby ===");
    
    loading_screen_set_progress(100);
    loading_screen_set_message("就绪！");
    
    ESP_LOGI(TAG, "[DEBUG] Waiting 500ms before transition...");
    vTaskDelay(pdMS_TO_TICKS(500));
    
    // HYBRID SCREEN MANAGEMENT:
    //
    // Industry standard approach for embedded UI:
    // - Loading screen: Create at boot, DESTROY after use (never needed again)
    // - Standby screen: Keep persistent (main screen, always available)
    // - Launcher screen: Keep persistent (frequently accessed)
    //
    // Benefits of destroying loading screen:
    // 1. GUARANTEES no loading screen artifacts (objects don't exist anymore)
    // 2. Frees ~5KB RAM (LVGL objects are never used again)
    // 3. Eliminates any dangling pointer risks
    
    ESP_LOGI(TAG, "[DEBUG] Calling loading_screen_hide()...");
    loading_screen_hide();
    ESP_LOGI(TAG, "[DEBUG] loading_screen_hide() completed");
    
    ESP_LOGI(TAG, "[DEBUG] Calling standby_screen_show()...");
    standby_screen_show();
    ESP_LOGI(TAG, "[DEBUG] standby_screen_show() completed");
    
    // DESTROY loading screen after successful transition
    // This guarantees no leftover artifacts and frees memory
    ESP_LOGI(TAG, "[DEBUG] Destroying loading screen (no longer needed)...");
    loading_screen_destroy();
    ESP_LOGI(TAG, "[DEBUG] Loading screen destroyed - memory freed");
    
    ESP_LOGI(TAG, "[DEBUG] === Screen transition finished ===");
    
    ESP_LOGI(TAG, "Initialization complete!");
    ESP_LOGI(TAG, "System ready.");
    
    system_initialized = true;
    
    // CRITICAL FIX: FreeRTOS tasks must NEVER return - they must run in an infinite loop
    // If a task returns, FreeRTOS aborts with "Task should not return"
    // Keep task running - loop_task handles main loop, but this task must stay alive
    ESP_LOGI(TAG, "main_task entering infinite loop...");
    
    // Create serial command handler task
    xTaskCreate(serial_command_task, "serial_cmd", 4096, nullptr, 5, nullptr);
    
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));  // Sleep for 1 second
        // Task stays alive but doesn't do anything - loop_task handles the work
    }
}

static void serial_command_task(void* pvParameters) {
    (void) pvParameters;
    char cmd_buffer[64];
    int cmd_index = 0;
    
    ESP_LOGI(TAG, "Serial command handler started. Type 'format_sd' to format SD card.");
    
    while (1) {
        // Read from UART (USB Serial)
        int c = getchar();
        if (c >= 0 && c != '\n' && c != '\r') {
            if (cmd_index < sizeof(cmd_buffer) - 1) {
                cmd_buffer[cmd_index++] = (char)c;
            }
        } else if (c == '\n' || c == '\r') {
            if (cmd_index > 0) {
                cmd_buffer[cmd_index] = '\0';
                ESP_LOGI(TAG, "Received command: %s", cmd_buffer);
                
                if (strcmp(cmd_buffer, "format_sd") == 0) {
                    ESP_LOGW(TAG, "Formatting SD card...");
                    if (sdStorage.format()) {
                        ESP_LOGI(TAG, "SD card formatted successfully!");
                    } else {
                        ESP_LOGE(TAG, "SD card format failed!");
                    }
                } else {
                    ESP_LOGI(TAG, "Unknown command. Available: format_sd");
                }
                
                cmd_index = 0;
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void loop_task(void* pvParameters) {
    ESP_LOGI(TAG, "loop_task started, waiting for initialization...");
    static bool initialization_logged = false;
    
    while (1) {
        // Wait for system initialization to complete - do NOTHING until then
        if (!system_initialized) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
        
        // CRITICAL FIX: Only log initialization message once, not every loop iteration
        if (!initialization_logged) {
            ESP_LOGI(TAG, "loop_task: System initialized, starting main loop");
            initialization_logged = true;
        }
        
        buttonHandler.handleButtons();
        
        // NOTE: LVGL timer handler is now called by dedicated lvgl_task
        // No need to call display_update() here anymore
        
        batteryManager.update();
        
        wifi_handle();
        websocket_handle();
        
        audio_process();
        
        standby_screen_update();
        
        if (smart_response_app_is_running()) {
            smart_response_app_update();
        }
        if (dify_app_is_running()) {
            dify_app_update();
        }
        
        // UI update functions may need mutex protection if they modify LVGL objects
        // But they should not call lv_timer_handler() - that's handled by lvgl_task
        
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "app_main() entered");
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_LOGI(TAG, "NVS flash initialized");
    
    // CRITICAL FIX: Initialize power management in app_main() BEFORE creating tasks
    // This matches factory example pattern and prevents watchdog timeout during I2C operations
    // Factory examples do hardware init synchronously in app_main() before tasks start
    ESP_LOGI(TAG, "Initializing power management in app_main()...");
    if (!batteryManager.init()) {
        ESP_LOGW(TAG, "Battery manager initialization failed - continuing anyway");
    }
    ESP_LOGI(TAG, "Power management initialized");
    
    // CRITICAL: Initialize BSP display in app_main() synchronously (matches factory example)
    // BSP handles: LVGL init, tick timer, LVGL task, mutex, display hardware, touch
    // This must be done BEFORE creating other tasks to ensure proper initialization order
    ESP_LOGI(TAG, "Initializing display with BSP in app_main()...");
    lv_display_t* disp = bsp_display_start();
    if (disp == nullptr) {
        ESP_LOGE(TAG, "BSP display initialization failed!");
        ESP_LOGE(TAG, "Device may not boot properly - check hardware connections");
        // Continue anyway - tasks might still work
    } else {
        ESP_LOGI(TAG, "BSP display initialized successfully");
    }
    
    // NOTE: BSP will initialize LVGL mutexes and create LVGL task automatically
    // No need for custom lvgl_mutex_init() or lvgl_task creation
    
    ESP_LOGI(TAG, "Creating main_task...");
    BaseType_t main_task_result = xTaskCreate(main_task, "main_task", 8192, NULL, 5, NULL);
    if (main_task_result != pdPASS) {
        ESP_LOGE(TAG, "Failed to create main_task!");
        return;
    }
    ESP_LOGI(TAG, "main_task created successfully");
    
    ESP_LOGI(TAG, "Creating loop_task...");
    BaseType_t loop_task_result = xTaskCreate(loop_task, "loop_task", 8192, NULL, 5, NULL);
    if (loop_task_result != pdPASS) {
        ESP_LOGE(TAG, "Failed to create loop_task!");
        return;
    }
    ESP_LOGI(TAG, "loop_task created successfully");
    ESP_LOGI(TAG, "app_main() returning - tasks should be running");
}
