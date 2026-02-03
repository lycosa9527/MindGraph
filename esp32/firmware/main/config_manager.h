#ifndef CONFIG_MANAGER_H
#define CONFIG_MANAGER_H

#include <string>
#include <stdbool.h>

#define CONFIG_NAMESPACE "config"

bool config_init();
bool config_save(const char* key, const char* value);
bool config_save_int(const char* key, int value);
bool config_save_bool(const char* key, bool value);
std::string config_get(const char* key, const char* default_value);
int config_get_int(const char* key, int default_value);
bool config_get_bool(const char* key, bool default_value);
bool config_has(const char* key);
bool config_clear();
bool config_clear_key(const char* key);

std::string config_get_watch_id();
std::string config_get_default_wifi_ssid();
std::string config_get_default_wifi_password();
std::string config_get_default_server_url();

#endif