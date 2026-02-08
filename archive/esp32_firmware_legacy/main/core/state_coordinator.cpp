#include "state_coordinator.h"
#include "app_state.h"
#include "wifi_manager.h"
#include "ntp_sync.h"
#include "weather_api.h"
#include "battery_manager.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

static const char* TAG = "STATE_COORD";

static TaskHandle_t coordinator_task_handle = nullptr;
static bool coordinator_running = false;

// State change callback - reacts to WiFi connection
static void on_state_change(uint32_t events) {
    if ((events & STATE_EVENT_WIFI_CONNECTED) != 0) {
        AppState state = app_state_get();
        ESP_LOGI(TAG, "WiFi connected! IP: %s", state.wifi_ip);
        
        // Trigger NTP sync when WiFi connects
        ESP_LOGI(TAG, "Triggering NTP sync...");
        ntp_sync_start();
        
        // Trigger weather fetch when WiFi connects
        ESP_LOGI(TAG, "Triggering weather fetch...");
        weather_api_fetch();
        
    } else if ((events & STATE_EVENT_WIFI_DISCONNECTED) != 0) {
        ESP_LOGI(TAG, "WiFi disconnected");
        // Stop NTP sync when WiFi disconnects
        ntp_sync_stop();
    } else if ((events & STATE_EVENT_TIME_SYNCED) != 0) {
        ESP_LOGI(TAG, "Time synced successfully");
    } else if ((events & STATE_EVENT_WEATHER_UPDATED) != 0) {
        AppState state = app_state_get();
        ESP_LOGI(TAG, "Weather updated: %.1f°C", state.weather_temperature);
    }
}

// Coordinator task - monitors state and coordinates updates
static void coordinator_task(void* pvParameters) {
    EventGroupHandle_t event_group = (EventGroupHandle_t)app_state_get_event_group();
    if (event_group == nullptr) {
        ESP_LOGE(TAG, "Failed to get event group");
        vTaskDelete(nullptr);
        return;
    }
    
    ESP_LOGI(TAG, "State coordinator task started");
    
    while (coordinator_running) {
        // Wait for state change events
        EventBits_t bits = xEventGroupWaitBits(
            event_group,
            STATE_EVENT_WIFI_CONNECTED | STATE_EVENT_WIFI_DISCONNECTED |
            STATE_EVENT_TIME_SYNCED | STATE_EVENT_WEATHER_UPDATED |
            STATE_EVENT_BATTERY_CHANGED | STATE_EVENT_SYSTEM_READY,
            pdTRUE,  // Clear bits on exit
            pdFALSE, // Wait for any bit
            portMAX_DELAY
        );
        
        // Handle events
        on_state_change(bits);
    }
    
    vTaskDelete(nullptr);
}

bool state_coordinator_init() {
    if (coordinator_running) {
        return true;
    }
    
    // Initialize app state manager
    if (!app_state_init()) {
        ESP_LOGE(TAG, "Failed to initialize app state");
        return false;
    }
    
    // Register state change callback
    app_state_register_callback(on_state_change);
    
    // Start coordinator task
    coordinator_running = true;
    BaseType_t ret = xTaskCreate(
        coordinator_task,
        "state_coord",
        4096,
        nullptr,
        5,  // Priority
        &coordinator_task_handle
    );
    
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create coordinator task");
        coordinator_running = false;
        return false;
    }
    
    ESP_LOGI(TAG, "State coordinator initialized");
    return true;
}

void state_coordinator_deinit() {
    coordinator_running = false;
    
    if (coordinator_task_handle != nullptr) {
        vTaskDelete(coordinator_task_handle);
        coordinator_task_handle = nullptr;
    }
    
    app_state_unregister_callback(on_state_change);
    app_state_deinit();
    
    ESP_LOGI(TAG, "State coordinator deinitialized");
}
