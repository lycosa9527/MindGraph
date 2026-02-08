#ifndef NTP_SYNC_H
#define NTP_SYNC_H

#include <stdbool.h>
#include <time.h>

#ifdef __cplusplus
extern "C" {
#endif

// Initialize NTP time synchronization
bool ntp_sync_init();

// Start NTP synchronization (call when WiFi is connected)
bool ntp_sync_start();

// Stop NTP synchronization
void ntp_sync_stop();

// Check if time is synchronized
bool ntp_sync_is_synced();

// Get last sync time (Unix timestamp)
time_t ntp_sync_get_time();

#ifdef __cplusplus
}
#endif

#endif
