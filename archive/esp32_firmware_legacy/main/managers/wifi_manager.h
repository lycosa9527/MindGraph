#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <stdint.h>
#include <stdbool.h>
#include <string>

struct WiFiNetwork {
    std::string ssid;
    int rssi;
    bool encrypted;
};

bool wifi_init();
bool wifi_scan_networks(WiFiNetwork* networks, int max_networks);
bool wifi_connect(const char* ssid, const char* password);
bool wifi_start_softap();
void wifi_stop_softap();
void wifi_handle();
bool wifi_is_connected();
std::string wifi_get_ip();
std::string wifi_get_ssid();
int wifi_get_rssi();

#endif
