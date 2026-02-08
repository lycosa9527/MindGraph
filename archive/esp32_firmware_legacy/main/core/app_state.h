#ifndef APP_STATE_H
#define APP_STATE_H

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

// Fixed-size buffers for embedded systems (avoids heap fragmentation)
#define APP_STATE_IP_SIZE 16      // IPv4 address: "192.168.1.100\0"
#define APP_STATE_SSID_SIZE 33    // WiFi SSID max: 32 chars + null
#define APP_STATE_CONDITION_SIZE 32  // Weather condition text

// Application state structure (using fixed-size buffers - embedded best practice)
struct AppState {
    // WiFi state
    bool wifi_connected;
    char wifi_ip[APP_STATE_IP_SIZE];
    char wifi_ssid[APP_STATE_SSID_SIZE];
    int wifi_rssi;
    
    // Time sync state
    bool time_synced;
    int64_t last_time_sync;
    
    // Weather state
    bool weather_available;
    float weather_temperature;
    int weather_humidity;
    char weather_condition[APP_STATE_CONDITION_SIZE];
    int64_t last_weather_update;
    
    // Battery state
    int battery_level;
    bool battery_charging;
    
    // System state
    bool system_ready;
};

// State change events (bit flags for FreeRTOS Event Group)
#define STATE_EVENT_WIFI_CONNECTED     BIT0
#define STATE_EVENT_WIFI_DISCONNECTED   BIT1
#define STATE_EVENT_TIME_SYNCED        BIT2
#define STATE_EVENT_WEATHER_UPDATED    BIT3
#define STATE_EVENT_BATTERY_CHANGED    BIT4
#define STATE_EVENT_SYSTEM_READY       BIT5

// Callback function types
typedef void (*StateChangeCallback)(uint32_t events);

// Initialize state manager
bool app_state_init();

// Get current state (thread-safe)
AppState app_state_get();

// Update WiFi state
void app_state_set_wifi(bool connected, const char* ip, const char* ssid, int rssi);

// Update time sync state
void app_state_set_time_synced(bool synced);

// Update weather state
void app_state_set_weather(float temp, int humidity, const char* condition);

// Update battery state
void app_state_set_battery(int level, bool charging);

// Set system ready state
void app_state_set_system_ready(bool ready);

// Register callback for state changes
void app_state_register_callback(StateChangeCallback callback);

// Unregister callback
void app_state_unregister_callback(StateChangeCallback callback);

// Get state change event group (for waiting on events)
void* app_state_get_event_group();

// Cleanup
void app_state_deinit();

#endif
