#ifndef WEATHER_API_H
#define WEATHER_API_H

#include <stdbool.h>
#include <stdint.h>

// Weather data structure
typedef struct {
    float temperature;      // Temperature in Celsius
    int humidity;           // Humidity percentage (0-100)
    const char* condition;  // Weather condition (e.g., "Clear", "Cloudy", "Rain")
    bool valid;             // Whether data is valid
    int64_t last_update;    // Last update timestamp (milliseconds)
} weather_data_t;

// Initialize weather API
bool weather_api_init();

// Fetch weather data (non-blocking, returns immediately)
// Call weather_api_get_data() later to check if data is ready
bool weather_api_fetch();

// Get current weather data
weather_data_t weather_api_get_data();

// Check if weather data is valid and recent (within cache_timeout_ms)
bool weather_api_is_data_valid(int cache_timeout_ms);

// Set API configuration (for QWeather/和风天气)
// api_key: Bearer token (JWT) for authentication
// city_name: Location ID (e.g., "101010700") or coordinates
// api_host: API host URL (e.g., "https://your_api_host" or use default devapi.qweather.com)
void weather_api_set_config(const char* api_key, const char* city_name, const char* api_host);

// Cleanup
void weather_api_deinit();

#endif
