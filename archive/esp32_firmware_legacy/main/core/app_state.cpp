#include "app_state.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include <string.h>

static const char* TAG = "APP_STATE";

// Global state instance
static AppState g_state;

// Mutex for thread-safe access
static SemaphoreHandle_t g_state_mutex = nullptr;

// Event group for state change notifications
static EventGroupHandle_t g_state_events = nullptr;

// Callback list (simple single callback for now, can be extended to list)
static StateChangeCallback g_state_callback = nullptr;

// Helper to notify state change
static void notify_state_change(uint32_t events) {
    if (g_state_events != nullptr) {
        xEventGroupSetBits(g_state_events, events);
    }
    
    if (g_state_callback != nullptr) {
        g_state_callback(events);
    }
}

bool app_state_init() {
    if (g_state_mutex != nullptr) {
        return true; // Already initialized
    }
    
    // Initialize state structure - explicit initialization to avoid padding issues
    g_state.wifi_connected = false;
    memset(g_state.wifi_ip, 0, APP_STATE_IP_SIZE);
    memset(g_state.wifi_ssid, 0, APP_STATE_SSID_SIZE);
    g_state.wifi_rssi = 0;
    g_state.time_synced = false;
    g_state.last_time_sync = 0;
    g_state.weather_available = false;
    g_state.weather_temperature = 0.0F;
    g_state.weather_humidity = 0;
    memset(g_state.weather_condition, 0, APP_STATE_CONDITION_SIZE);
    g_state.last_weather_update = 0;
    g_state.battery_level = 0;
    g_state.battery_charging = false;
    g_state.system_ready = false;
    
    // Create mutex
    g_state_mutex = xSemaphoreCreateMutex();
    if (g_state_mutex == nullptr) {
        ESP_LOGE(TAG, "Failed to create state mutex");
        return false;
    }
    
    // Create event group
    g_state_events = xEventGroupCreate();
    if (g_state_events == nullptr) {
        ESP_LOGE(TAG, "Failed to create state event group");
        vSemaphoreDelete(g_state_mutex);
        g_state_mutex = nullptr;
        return false;
    }
    
    ESP_LOGI(TAG, "App state manager initialized");
    return true;
}

AppState app_state_get() {
    AppState state_copy;
    
    if (g_state_mutex != nullptr && xSemaphoreTake(g_state_mutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        // Copy struct members individually to avoid potential padding/alignment issues
        // that could corrupt adjacent memory (display buffer)
        state_copy.wifi_connected = g_state.wifi_connected;
        memcpy(state_copy.wifi_ip, g_state.wifi_ip, APP_STATE_IP_SIZE);
        memcpy(state_copy.wifi_ssid, g_state.wifi_ssid, APP_STATE_SSID_SIZE);
        state_copy.wifi_rssi = g_state.wifi_rssi;
        state_copy.time_synced = g_state.time_synced;
        state_copy.last_time_sync = g_state.last_time_sync;
        state_copy.weather_available = g_state.weather_available;
        state_copy.weather_temperature = g_state.weather_temperature;
        state_copy.weather_humidity = g_state.weather_humidity;
        memcpy(state_copy.weather_condition, g_state.weather_condition, APP_STATE_CONDITION_SIZE);
        state_copy.last_weather_update = g_state.last_weather_update;
        state_copy.battery_level = g_state.battery_level;
        state_copy.battery_charging = g_state.battery_charging;
        state_copy.system_ready = g_state.system_ready;
        xSemaphoreGive(g_state_mutex);
    } else {
        // Fallback: copy without lock
        state_copy.wifi_connected = g_state.wifi_connected;
        memcpy(state_copy.wifi_ip, g_state.wifi_ip, APP_STATE_IP_SIZE);
        memcpy(state_copy.wifi_ssid, g_state.wifi_ssid, APP_STATE_SSID_SIZE);
        state_copy.wifi_rssi = g_state.wifi_rssi;
        state_copy.time_synced = g_state.time_synced;
        state_copy.last_time_sync = g_state.last_time_sync;
        state_copy.weather_available = g_state.weather_available;
        state_copy.weather_temperature = g_state.weather_temperature;
        state_copy.weather_humidity = g_state.weather_humidity;
        memcpy(state_copy.weather_condition, g_state.weather_condition, APP_STATE_CONDITION_SIZE);
        state_copy.last_weather_update = g_state.last_weather_update;
        state_copy.battery_level = g_state.battery_level;
        state_copy.battery_charging = g_state.battery_charging;
        state_copy.system_ready = g_state.system_ready;
    }
    
    return state_copy;
}

void app_state_set_wifi(bool connected, const char* ip, const char* ssid, int rssi) {
    if (g_state_mutex == nullptr) {
        return;
    }
    
    if (xSemaphoreTake(g_state_mutex, portMAX_DELAY) == pdTRUE) {
        bool state_changed = (g_state.wifi_connected != connected);
        
        g_state.wifi_connected = connected;
        
        if (ip != nullptr) {
            strncpy(g_state.wifi_ip, ip, APP_STATE_IP_SIZE - 1);
            g_state.wifi_ip[APP_STATE_IP_SIZE - 1] = '\0';
        } else if (!connected) {
            g_state.wifi_ip[0] = '\0';
        }
        
        if (ssid != nullptr) {
            strncpy(g_state.wifi_ssid, ssid, APP_STATE_SSID_SIZE - 1);
            g_state.wifi_ssid[APP_STATE_SSID_SIZE - 1] = '\0';
        } else if (!connected) {
            g_state.wifi_ssid[0] = '\0';
        }
        
        g_state.wifi_rssi = rssi;
        
        xSemaphoreGive(g_state_mutex);
        
        if (state_changed) {
            uint32_t events = connected ? STATE_EVENT_WIFI_CONNECTED : STATE_EVENT_WIFI_DISCONNECTED;
            notify_state_change(events);
            ESP_LOGI(TAG, "WiFi state changed: %s", connected ? "CONNECTED" : "DISCONNECTED");
        }
    }
}

void app_state_set_time_synced(bool synced) {
    if (g_state_mutex == nullptr) {
        return;
    }
    
    if (xSemaphoreTake(g_state_mutex, portMAX_DELAY) == pdTRUE) {
        bool state_changed = (g_state.time_synced != synced);
        g_state.time_synced = synced;
        
        if (synced) {
            g_state.last_time_sync = esp_timer_get_time() / 1000; // milliseconds
        }
        
        xSemaphoreGive(g_state_mutex);
        
        if (state_changed && synced) {
            notify_state_change(STATE_EVENT_TIME_SYNCED);
            ESP_LOGI(TAG, "Time sync state changed: SYNCED");
        }
    }
}

void app_state_set_weather(float temp, int humidity, const char* condition) {
    if (g_state_mutex == nullptr) {
        return;
    }
    
    if (xSemaphoreTake(g_state_mutex, portMAX_DELAY) == pdTRUE) {
        g_state.weather_available = true;
        g_state.weather_temperature = temp;
        g_state.weather_humidity = humidity;
        
        if (condition != nullptr) {
            strncpy(g_state.weather_condition, condition, APP_STATE_CONDITION_SIZE - 1);
            g_state.weather_condition[APP_STATE_CONDITION_SIZE - 1] = '\0';
        } else {
            g_state.weather_condition[0] = '\0';
        }
        
        g_state.last_weather_update = esp_timer_get_time() / 1000; // milliseconds
        
        xSemaphoreGive(g_state_mutex);
        
        notify_state_change(STATE_EVENT_WEATHER_UPDATED);
        ESP_LOGI(TAG, "Weather updated: %.1f°C, %d%%, %s", temp, humidity, condition ? condition : "");
    }
}

void app_state_set_battery(int level, bool charging) {
    if (g_state_mutex == nullptr) {
        return;
    }
    
    if (xSemaphoreTake(g_state_mutex, portMAX_DELAY) == pdTRUE) {
        bool state_changed = (g_state.battery_level != level || g_state.battery_charging != charging);
        
        g_state.battery_level = level;
        g_state.battery_charging = charging;
        
        xSemaphoreGive(g_state_mutex);
        
        if (state_changed) {
            notify_state_change(STATE_EVENT_BATTERY_CHANGED);
        }
    }
}

void app_state_set_system_ready(bool ready) {
    if (g_state_mutex == nullptr) {
        return;
    }
    
    if (xSemaphoreTake(g_state_mutex, portMAX_DELAY) == pdTRUE) {
        bool state_changed = (g_state.system_ready != ready);
        g_state.system_ready = ready;
        xSemaphoreGive(g_state_mutex);
        
        if (state_changed && ready) {
            notify_state_change(STATE_EVENT_SYSTEM_READY);
            ESP_LOGI(TAG, "System ready");
        }
    }
}

void app_state_register_callback(StateChangeCallback callback) {
    g_state_callback = callback;
    ESP_LOGI(TAG, "State change callback registered");
}

void app_state_unregister_callback(StateChangeCallback callback) {
    if (g_state_callback == callback) {
        g_state_callback = nullptr;
        ESP_LOGI(TAG, "State change callback unregistered");
    }
}

void* app_state_get_event_group() {
    return (void*)g_state_events;
}

void app_state_deinit() {
    if (g_state_mutex != nullptr) {
        vSemaphoreDelete(g_state_mutex);
        g_state_mutex = nullptr;
    }
    
    if (g_state_events != nullptr) {
        vEventGroupDelete(g_state_events);
        g_state_events = nullptr;
    }
    
    g_state_callback = nullptr;
    ESP_LOGI(TAG, "App state manager deinitialized");
}
