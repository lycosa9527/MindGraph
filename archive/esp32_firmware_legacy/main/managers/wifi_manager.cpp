#include "wifi_manager.h"
#include "app_state.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include <string>
#include <cstring>

static const char* TAG = "WIFI";
static bool wifi_initialized = false;
static esp_netif_t* sta_netif = nullptr;
static esp_netif_t* ap_netif = nullptr;
static EventGroupHandle_t wifi_event_group = nullptr;
static const int WIFI_CONNECTED_BIT = BIT0;
static const int WIFI_FAIL_BIT = BIT1;
static std::string current_ip;
static std::string current_ssid;
static int current_rssi = 0;

static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                                int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT) {
        switch (event_id) {
            case WIFI_EVENT_STA_START:
                esp_wifi_connect();
                break;
            case WIFI_EVENT_STA_CONNECTED: {
                wifi_event_sta_connected_t* event = (wifi_event_sta_connected_t*)event_data;
                current_ssid = (const char*)event->ssid;
                ESP_LOGI(TAG, "Connected to SSID: %s", current_ssid.c_str());
                break;
            }
            case WIFI_EVENT_STA_DISCONNECTED:
                xEventGroupClearBits(wifi_event_group, WIFI_CONNECTED_BIT);
                xEventGroupSetBits(wifi_event_group, WIFI_FAIL_BIT);
                current_ip = "";
                current_ssid = "";
                current_rssi = 0;
                ESP_LOGI(TAG, "Disconnected");
                // Update app state
                app_state_set_wifi(false, nullptr, nullptr, 0);
                break;
            default:
                break;
        }
    } else if (event_base == IP_EVENT) {
        if (event_id == IP_EVENT_STA_GOT_IP) {
            ip_event_got_ip_t* event = (ip_event_got_ip_t*)event_data;
            char ip_str[16];
            snprintf(ip_str, sizeof(ip_str), IPSTR, IP2STR(&event->ip_info.ip));
            current_ip = ip_str;
            xEventGroupSetBits(wifi_event_group, WIFI_CONNECTED_BIT);
            xEventGroupClearBits(wifi_event_group, WIFI_FAIL_BIT);
            ESP_LOGI(TAG, "Got IP: %s", ip_str);
            // Update app state (will trigger state coordinator to start NTP/Weather)
            app_state_set_wifi(true, ip_str, current_ssid.c_str(), current_rssi);
        }
    }
}

bool wifi_init() {
    if (wifi_initialized) {
        return true;
    }
    
    wifi_event_group = xEventGroupCreate();
    
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    
    sta_netif = esp_netif_create_default_wifi_sta();
    ap_netif = esp_netif_create_default_wifi_ap();
    
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler,
                                                        nullptr,
                                                        nullptr));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler,
                                                        nullptr,
                                                        nullptr));
    
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());
    
    wifi_initialized = true;
    return true;
}

bool wifi_scan_networks(WiFiNetwork* networks, int max_networks) {
    if (!wifi_initialized) {
        wifi_init();
    }
    
    wifi_scan_config_t scan_config = {};
    scan_config.ssid = nullptr;
    scan_config.bssid = nullptr;
    scan_config.channel = 0;
    scan_config.show_hidden = false;
    
    ESP_ERROR_CHECK(esp_wifi_scan_start(&scan_config, true));
    
    uint16_t ap_count = 0;
    ESP_ERROR_CHECK(esp_wifi_scan_get_ap_num(&ap_count));
    
    if (ap_count == 0) {
        return false;
    }
    
    wifi_ap_record_t* ap_records = (wifi_ap_record_t*)malloc(sizeof(wifi_ap_record_t) * ap_count);
    if (ap_records == nullptr) {
        return false;
    }
    
    ESP_ERROR_CHECK(esp_wifi_scan_get_ap_records(&ap_count, ap_records));
    
    int count = 0;
    for (uint16_t i = 0; i < ap_count && count < max_networks; i++) {
        networks[count].ssid = (const char*)ap_records[i].ssid;
        networks[count].rssi = ap_records[i].rssi;
        networks[count].encrypted = (ap_records[i].authmode != WIFI_AUTH_OPEN);
        count++;
    }
    
    free(ap_records);
    return count > 0;
}

bool wifi_connect(const char* ssid, const char* password) {
    if (!wifi_initialized) {
        wifi_init();
    }
    
    // Disconnect if already connecting/connected
    wifi_mode_t mode;
    if (esp_wifi_get_mode(&mode) == ESP_OK) {
        if (mode == WIFI_MODE_STA || mode == WIFI_MODE_APSTA) {
            esp_wifi_disconnect();
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }
    
    // Clear any previous connection state
    xEventGroupClearBits(wifi_event_group, WIFI_CONNECTED_BIT | WIFI_FAIL_BIT);
    
    wifi_config_t wifi_config = {};
    strncpy((char*)wifi_config.sta.ssid, ssid, sizeof(wifi_config.sta.ssid) - 1);
    if (password) {
        strncpy((char*)wifi_config.sta.password, password, sizeof(wifi_config.sta.password) - 1);
    }
    
    esp_err_t ret = esp_wifi_set_config(WIFI_IF_STA, &wifi_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set WiFi config: %s", esp_err_to_name(ret));
        return false;
    }
    
    ret = esp_wifi_connect();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start WiFi connection: %s", esp_err_to_name(ret));
        return false;
    }
    
    EventBits_t bits = xEventGroupWaitBits(wifi_event_group,
                                          WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
                                          false,
                                          false,
                                          pdMS_TO_TICKS(20000));
    
    if (bits & WIFI_CONNECTED_BIT) {
        current_ssid = ssid;
        return true;
    } else {
        ESP_LOGE(TAG, "Connection failed");
        return false;
    }
}

bool wifi_start_softap() {
    if (!wifi_initialized) {
        wifi_init();
    }
    
    wifi_config_t wifi_config = {};
    strncpy((char*)wifi_config.ap.ssid, "ESP32-智回", sizeof(wifi_config.ap.ssid) - 1);
    strncpy((char*)wifi_config.ap.password, "smartresponse123", sizeof(wifi_config.ap.password) - 1);
    wifi_config.ap.ssid_len = strlen((char*)wifi_config.ap.ssid);
    wifi_config.ap.channel = 1;
    wifi_config.ap.authmode = WIFI_AUTH_WPA2_PSK;
    wifi_config.ap.max_connection = 4;
    
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &wifi_config));
    
    return true;
}

void wifi_stop_softap() {
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
}

void wifi_handle() {
}

bool wifi_is_connected() {
    return (xEventGroupGetBits(wifi_event_group) & WIFI_CONNECTED_BIT) != 0;
}

std::string wifi_get_ip() {
    return current_ip;
}

std::string wifi_get_ssid() {
    return current_ssid;
}

int wifi_get_rssi() {
    if (wifi_is_connected()) {
        wifi_ap_record_t ap_info;
        if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
            current_rssi = ap_info.rssi;
            // Update app state with RSSI
            if (wifi_is_connected()) {
                app_state_set_wifi(true, current_ip.c_str(), current_ssid.c_str(), current_rssi);
            }
        }
    }
    return current_rssi;
}
