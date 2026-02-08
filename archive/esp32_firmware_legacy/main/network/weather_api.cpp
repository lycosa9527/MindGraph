#include "weather_api.h"
#include "app_state.h"
#include "wifi_manager.h"
#include "esp_log.h"
#include "esp_http_client.h"
#include "esp_timer.h"
#include "cJSON.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include <string.h>
#include <stdlib.h>
#include <math.h>

static const char* TAG = "WEATHER_API";

// Configuration
static char* api_key = nullptr;  // Bearer token (JWT)
static char* city_name = nullptr;  // Location ID or coordinates
static char* api_host = nullptr;  // API host URL

// Weather data cache
static weather_data_t cached_weather = {
    .temperature = 0.0f,
    .humidity = 0,
    .condition = nullptr,
    .valid = false,
    .last_update = 0
};
static bool fetching = false;
static TaskHandle_t fetch_task_handle = nullptr;
static char condition_buffer[32] = "No Data";
static const char* default_condition = "No Data";

// Event group for HTTP request completion
static EventGroupHandle_t http_event_group;
#define HTTP_REQUEST_DONE BIT0
#define HTTP_REQUEST_FAIL BIT1

// HTTP event handler
static esp_err_t http_event_handler(esp_http_client_event_t *evt) {
    static char *output_buffer = nullptr;
    static int output_len = 0;
    
    switch(evt->event_id) {
        case HTTP_EVENT_ERROR:
            ESP_LOGD(TAG, "HTTP_EVENT_ERROR");
            xEventGroupSetBits(http_event_group, HTTP_REQUEST_FAIL);
            break;
            
        case HTTP_EVENT_ON_CONNECTED:
            ESP_LOGD(TAG, "HTTP_EVENT_ON_CONNECTED");
            break;
            
        case HTTP_EVENT_HEADER_SENT:
            ESP_LOGD(TAG, "HTTP_EVENT_HEADER_SENT");
            break;
            
        case HTTP_EVENT_ON_HEADER:
            ESP_LOGD(TAG, "HTTP_EVENT_ON_HEADER, key=%s, value=%s", evt->header_key, evt->header_value);
            break;
            
        case HTTP_EVENT_ON_DATA:
            ESP_LOGD(TAG, "HTTP_EVENT_ON_DATA, len=%d", evt->data_len);
            if (!esp_http_client_is_chunked_response(evt->client)) {
                if (output_buffer == nullptr) {
                    output_buffer = (char*)malloc(esp_http_client_get_content_length(evt->client) + 1);
                    output_len = 0;
                    if (output_buffer == nullptr) {
                        ESP_LOGE(TAG, "Failed to allocate memory for output buffer");
                        return ESP_FAIL;
                    }
                }
                memcpy(output_buffer + output_len, evt->data, evt->data_len);
                output_len += evt->data_len;
            }
            break;
            
        case HTTP_EVENT_ON_FINISH:
            ESP_LOGD(TAG, "HTTP_EVENT_ON_FINISH");
            if (output_buffer != nullptr) {
                output_buffer[output_len] = '\0';
                ESP_LOGI(TAG, "Response: %s", output_buffer);
                
                // Parse JSON response (QWeather format)
                cJSON *json = cJSON_Parse(output_buffer);
                if (json != nullptr) {
                    // Check API response code
                    cJSON *code_item = cJSON_GetObjectItem(json, "code");
                    if (code_item != nullptr && cJSON_GetNumberValue(code_item) == 200) {
                        // Parse QWeather format: {"code": 200, "now": {"temp": "25", "humidity": "60", "text": "晴"}}
                        cJSON *now_obj = cJSON_GetObjectItem(json, "now");
                        
                        if (now_obj != nullptr) {
                            // Temperature (QWeather returns as string)
                            cJSON *temp_item = cJSON_GetObjectItem(now_obj, "temp");
                            if (temp_item != nullptr) {
                                if (cJSON_IsString(temp_item)) {
                                    cached_weather.temperature = (float)atof(cJSON_GetStringValue(temp_item));
                                } else {
                                    cached_weather.temperature = (float)cJSON_GetNumberValue(temp_item);
                                }
                            }
                            
                            // Humidity (QWeather returns as string)
                            cJSON *humidity_item = cJSON_GetObjectItem(now_obj, "humidity");
                            if (humidity_item != nullptr) {
                                if (cJSON_IsString(humidity_item)) {
                                    cached_weather.humidity = (int)atoi(cJSON_GetStringValue(humidity_item));
                                } else {
                                    cached_weather.humidity = (int)cJSON_GetNumberValue(humidity_item);
                                }
                            }
                            
                            // Weather condition text (Chinese)
                            cJSON *text_item = cJSON_GetObjectItem(now_obj, "text");
                            if (text_item != nullptr && cJSON_IsString(text_item)) {
                                strncpy(condition_buffer, cJSON_GetStringValue(text_item), sizeof(condition_buffer) - 1);
                                condition_buffer[sizeof(condition_buffer) - 1] = '\0';
                                cached_weather.condition = condition_buffer;
                            } else {
                                cached_weather.condition = default_condition;
                            }
                        }
                    } else {
                        ESP_LOGW(TAG, "QWeather API returned error code: %d", 
                                code_item ? (int)cJSON_GetNumberValue(code_item) : -1);
                    }
                    
                    cached_weather.valid = true;
                    cached_weather.last_update = esp_timer_get_time() / 1000; // milliseconds
                    
                    // Ensure condition is set
                    if (cached_weather.condition == nullptr) {
                        cached_weather.condition = default_condition;
                    }
                    
                    ESP_LOGI(TAG, "Weather updated: %.1f°C, %d%%, %s", 
                             cached_weather.temperature, 
                             cached_weather.humidity,
                             cached_weather.condition);
                    
                    // Update app state
                    app_state_set_weather(
                        cached_weather.temperature,
                        cached_weather.humidity,
                        cached_weather.condition
                    );
                    
                    cJSON_Delete(json);
                    xEventGroupSetBits(http_event_group, HTTP_REQUEST_DONE);
                } else {
                    ESP_LOGE(TAG, "Failed to parse JSON");
                    xEventGroupSetBits(http_event_group, HTTP_REQUEST_FAIL);
                }
                
                free(output_buffer);
                output_buffer = nullptr;
                output_len = 0;
            }
            break;
            
        case HTTP_EVENT_DISCONNECTED:
            ESP_LOGI(TAG, "HTTP_EVENT_DISCONNECTED");
            break;
            
        default:
            break;
    }
    return ESP_OK;
}

// Weather fetch task
static void weather_fetch_task(void *pvParameters) {
    if (api_key == nullptr || city_name == nullptr) {
        ESP_LOGW(TAG, "Weather API not configured");
        fetching = false;
        vTaskDelete(nullptr);
        return;
    }
    
    // Build URL according to QWeather API documentation
    // Endpoint: /v7/weather/now
    // Uses Bearer token authentication in header, not key parameter
    const char* host = (api_host != nullptr && strlen(api_host) > 0) ? api_host : "https://devapi.qweather.com";
    char url[256];
    snprintf(url, sizeof(url), 
             "%s/v7/weather/now?location=%s&lang=zh",
             host, city_name);
    
    ESP_LOGI(TAG, "Fetching weather from: %s", url);
    
    esp_http_client_config_t config = {};
    config.url = url;
    config.event_handler = http_event_handler;
    config.timeout_ms = 10000;
    
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == nullptr) {
        ESP_LOGE(TAG, "Failed to initialize HTTP client");
        fetching = false;
        vTaskDelete(nullptr);
        return;
    }
    
    // Set Authorization header with Bearer token (JWT)
    // According to QWeather API documentation: Authorization: Bearer your_token
    if (api_key != nullptr && strlen(api_key) > 0) {
        char auth_header[128];
        snprintf(auth_header, sizeof(auth_header), "Bearer %s", api_key);
        esp_http_client_set_header(client, "Authorization", auth_header);
    }
    
    // Clear event group
    xEventGroupClearBits(http_event_group, HTTP_REQUEST_DONE | HTTP_REQUEST_FAIL);
    
    // Perform request
    esp_err_t err = esp_http_client_perform(client);
    
    if (err == ESP_OK) {
        int status_code = esp_http_client_get_status_code(client);
        ESP_LOGI(TAG, "HTTP Status = %d", status_code);
        
        if (status_code == 200) {
            // Wait for data to be parsed (up to 5 seconds)
            EventBits_t bits = xEventGroupWaitBits(http_event_group,
                                                   HTTP_REQUEST_DONE | HTTP_REQUEST_FAIL,
                                                   pdFALSE,
                                                   pdFALSE,
                                                   pdMS_TO_TICKS(5000));
            
            if (bits & HTTP_REQUEST_DONE) {
                ESP_LOGI(TAG, "Weather data fetched successfully");
            } else if (bits & HTTP_REQUEST_FAIL) {
                ESP_LOGW(TAG, "Weather data fetch failed");
                cached_weather.valid = false;
            }
        } else {
            ESP_LOGW(TAG, "HTTP request failed with status %d", status_code);
            cached_weather.valid = false;
        }
    } else {
        ESP_LOGE(TAG, "HTTP request failed: %s", esp_err_to_name(err));
        cached_weather.valid = false;
    }
    
    esp_http_client_cleanup(client);
    fetching = false;
    vTaskDelete(nullptr);
}

bool weather_api_init() {
    if (http_event_group == nullptr) {
        http_event_group = xEventGroupCreate();
        if (http_event_group == nullptr) {
            ESP_LOGE(TAG, "Failed to create event group");
            return false;
        }
    }
    
    // Initialize cached data
    cached_weather.temperature = 0.0f;
    cached_weather.humidity = 0;
    cached_weather.condition = condition_buffer;
    strcpy(condition_buffer, default_condition);
    cached_weather.valid = false;
    cached_weather.last_update = 0;
    
    ESP_LOGI(TAG, "Weather API initialized");
    return true;
}

bool weather_api_fetch() {
    if (fetching) {
        ESP_LOGD(TAG, "Weather fetch already in progress");
        return false;
    }
    
    if (api_key == nullptr || city_name == nullptr) {
        ESP_LOGW(TAG, "Weather API not configured");
        return false;
    }
    
    if (!wifi_is_connected()) {
        ESP_LOGW(TAG, "WiFi not connected, cannot fetch weather");
        return false;
    }
    
    fetching = true;
    
    // Create task to fetch weather (non-blocking)
    BaseType_t ret = xTaskCreate(weather_fetch_task,
                                 "weather_fetch",
                                 8192,
                                 nullptr,
                                 5,
                                 &fetch_task_handle);
    
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create weather fetch task");
        fetching = false;
        return false;
    }
    
    return true;
}

weather_data_t weather_api_get_data() {
    return cached_weather;
}

bool weather_api_is_data_valid(int cache_timeout_ms) {
    if (!cached_weather.valid) {
        return false;
    }
    
    int64_t now = esp_timer_get_time() / 1000; // milliseconds
    int64_t age = now - cached_weather.last_update;
    
    return (age < cache_timeout_ms);
}

void weather_api_set_config(const char* api_key_str, const char* city, const char* host) {
    // Free old strings
    if (api_key != nullptr) {
        free(api_key);
        api_key = nullptr;
    }
    if (city_name != nullptr) {
        free(city_name);
        city_name = nullptr;
    }
    if (api_host != nullptr) {
        free(api_host);
        api_host = nullptr;
    }
    
    // Allocate and copy new strings
    if (api_key_str != nullptr) {
        api_key = (char*)malloc(strlen(api_key_str) + 1);
        if (api_key != nullptr) {
            strcpy(api_key, api_key_str);
        }
    }
    
    if (city != nullptr) {
        city_name = (char*)malloc(strlen(city) + 1);
        if (city_name != nullptr) {
            strcpy(city_name, city);
        }
    }
    
    if (host != nullptr) {
        api_host = (char*)malloc(strlen(host) + 1);
        if (api_host != nullptr) {
            strcpy(api_host, host);
        }
    }
    
    ESP_LOGI(TAG, "Weather API configured (QWeather): location=%s, host=%s", 
             city_name ? city_name : "null",
             api_host ? api_host : "default");
}

void weather_api_deinit() {
    if (fetch_task_handle != nullptr) {
        vTaskDelete(fetch_task_handle);
        fetch_task_handle = nullptr;
    }
    
    if (api_key != nullptr) {
        free(api_key);
        api_key = nullptr;
    }
    if (city_name != nullptr) {
        free(city_name);
        city_name = nullptr;
    }
    if (api_host != nullptr) {
        free(api_host);
        api_host = nullptr;
    }
    
    if (http_event_group != nullptr) {
        vEventGroupDelete(http_event_group);
        http_event_group = nullptr;
    }
    
    fetching = false;
    ESP_LOGI(TAG, "Weather API deinitialized");
}
