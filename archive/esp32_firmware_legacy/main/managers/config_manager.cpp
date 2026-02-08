#include "config_manager.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"
#include "esp_mac.h"
#include <cstring>
#include <cstdio>

static const char* TAG = "CONFIG";
static nvs_handle_t config_nvs_handle = 0;
static bool config_initialized = false;

bool config_init() {
    if (config_initialized) {
        return true;
    }
    
    esp_err_t err = nvs_open(CONFIG_NAMESPACE, NVS_READWRITE, &config_nvs_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS: %s", esp_err_to_name(err));
        return false;
    }
    
    config_initialized = true;
    return true;
}

bool config_save(const char* key, const char* value) {
    if (!config_initialized || config_nvs_handle == 0) {
        return false;
    }
    esp_err_t err = nvs_set_str(config_nvs_handle, key, value);
    if (err == ESP_OK) {
        err = nvs_commit(config_nvs_handle);
    }
    return err == ESP_OK;
}

bool config_save_int(const char* key, int value) {
    if (!config_initialized || config_nvs_handle == 0) {
        return false;
    }
    esp_err_t err = nvs_set_i32(config_nvs_handle, key, value);
    if (err == ESP_OK) {
        err = nvs_commit(config_nvs_handle);
    }
    return err == ESP_OK;
}

bool config_save_bool(const char* key, bool value) {
    if (!config_initialized || config_nvs_handle == 0) {
        return false;
    }
    esp_err_t err = nvs_set_i8(config_nvs_handle, key, value ? 1 : 0);
    if (err == ESP_OK) {
        err = nvs_commit(config_nvs_handle);
    }
    return err == ESP_OK;
}

std::string config_get(const char* key, const char* default_value) {
    if (!config_initialized || config_nvs_handle == 0) {
        return std::string(default_value);
    }
    
    size_t required_size = 0;
    esp_err_t err = nvs_get_str(config_nvs_handle, key, nullptr, &required_size);
    if (err == ESP_OK && required_size > 0) {
        char* buffer = (char*)malloc(required_size);
        if (buffer != nullptr) {
            err = nvs_get_str(config_nvs_handle, key, buffer, &required_size);
            if (err == ESP_OK) {
                std::string result(buffer);
                free(buffer);
                return result;
            }
            free(buffer);
        }
    }
    return std::string(default_value);
}

int config_get_int(const char* key, int default_value) {
    if (!config_initialized || config_nvs_handle == 0) {
        return default_value;
    }
    int32_t value = default_value;
    esp_err_t err = nvs_get_i32(config_nvs_handle, key, &value);
    if (err == ESP_OK) {
        return value;
    }
    return default_value;
}

bool config_get_bool(const char* key, bool default_value) {
    if (!config_initialized || config_nvs_handle == 0) {
        return default_value;
    }
    int8_t value = default_value ? 1 : 0;
    esp_err_t err = nvs_get_i8(config_nvs_handle, key, &value);
    if (err == ESP_OK) {
        return value != 0;
    }
    return default_value;
}

bool config_has(const char* key) {
    if (!config_initialized || config_nvs_handle == 0) {
        return false;
    }
    size_t required_size = 0;
    esp_err_t err = nvs_get_str(config_nvs_handle, key, nullptr, &required_size);
    if (err == ESP_OK) {
        return true;
    }
    int32_t int_val;
    err = nvs_get_i32(config_nvs_handle, key, &int_val);
    if (err == ESP_OK) {
        return true;
    }
    int8_t bool_val;
    err = nvs_get_i8(config_nvs_handle, key, &bool_val);
    return err == ESP_OK;
}

bool config_clear() {
    if (!config_initialized || config_nvs_handle == 0) {
        return false;
    }
    esp_err_t err = nvs_erase_all(config_nvs_handle);
    if (err == ESP_OK) {
        err = nvs_commit(config_nvs_handle);
    }
    return err == ESP_OK;
}

bool config_clear_key(const char* key) {
    if (!config_initialized || config_nvs_handle == 0) {
        return false;
    }
    esp_err_t err = nvs_erase_key(config_nvs_handle, key);
    if (err == ESP_OK) {
        err = nvs_commit(config_nvs_handle);
    }
    return err == ESP_OK;
}

std::string config_get_watch_id() {
    std::string watch_id = config_get("watch_id", "");
    if (watch_id.length() == 0) {
        uint8_t mac[6];
        esp_read_mac(mac, ESP_MAC_WIFI_STA);
        char mac_str[18];
        snprintf(mac_str, sizeof(mac_str), "%02X%02X%02X%02X%02X%02X",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
        watch_id = "WATCH-";
        watch_id += mac_str + 6;
        config_save("watch_id", watch_id.c_str());
    }
    return watch_id;
}

std::string config_get_default_wifi_ssid() {
    return config_get("wifi_ssid", "");
}

std::string config_get_default_wifi_password() {
    return config_get("wifi_password", "");
}

std::string config_get_default_server_url() {
    return config_get("server_url", "");
}