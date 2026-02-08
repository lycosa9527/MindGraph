#include "ntp_sync.h"
#include "app_state.h"
#include "rtc_manager.h"
#include "esp_log.h"
#include "esp_sntp.h"
#include "esp_timer.h"
#include "freertos/task.h"
#include <sys/types.h>
#include <sys/time.h>
#include <time.h>
#include <stdio.h>

// Timezone offset (UTC+8 for China Standard Time)
// Change this to your timezone offset in hours
#define TIMEZONE_OFFSET_HOURS 8

static const char* TAG = "NTP_SYNC";

extern RTCManager rtcManager;

static bool ntp_initialized = false;
static bool ntp_synced = false;
static time_t last_sync_time = 0;
static int64_t last_sync_attempt = 0;
static const int SYNC_RETRY_INTERVAL_MS = 60 * 1000; // Retry every 60 seconds if failed

// NTP server configuration - Chinese servers
#define NTP_SERVER_CNT 3
static const char* ntp_servers[NTP_SERVER_CNT] = {
    "cn.pool.ntp.org",           // China NTP pool
    "ntp1.aliyun.com",           // Alibaba Cloud NTP server 1
    "time1.cloud.tencent.com"    // Tencent Cloud NTP server 1
};

// Helper function to convert year to RTC format (0-99 for 2000-2099)
static uint8_t convert_year_to_rtc_format(int year) {
    if (year >= 2000 && year <= 2099) {
        return (uint8_t)(year - 2000);
    }
    return (uint8_t)(year % 100);
}

// Helper function to update RTC with synchronized time
static void update_rtc_with_time(const struct tm* timeinfo) {
    if (!rtcManager.isValid()) {
        ESP_LOGW(TAG, "RTC not valid, cannot update");
        return;
    }
    
    int year = timeinfo->tm_year + 1900;
    uint8_t rtc_year = convert_year_to_rtc_format(year);
    
    rtcManager.setDateTime(
        rtc_year,
        (uint8_t)(timeinfo->tm_mon + 1),
        (uint8_t)timeinfo->tm_mday,
        (uint8_t)timeinfo->tm_hour,
        (uint8_t)timeinfo->tm_min,
        (uint8_t)timeinfo->tm_sec
    );
    
    char time_str[64];
    int result = snprintf(time_str, sizeof(time_str), "%04d-%02d-%02d %02d:%02d:%02d",
                          year, timeinfo->tm_mon + 1, timeinfo->tm_mday,
                          timeinfo->tm_hour, timeinfo->tm_min, timeinfo->tm_sec);
    if (result < 0 || result >= (int)sizeof(time_str)) {
        ESP_LOGW(TAG, "Time string truncation occurred");
    }
    ESP_LOGI(TAG, "RTC updated with NTP time: %s", time_str);
}

// Helper function to log synchronized time
static void log_synchronized_time(const struct tm* timeinfo) {
    char time_str[64];
    int result = snprintf(time_str, sizeof(time_str), "%04d-%02d-%02d %02d:%02d:%02d",
                          timeinfo->tm_year + 1900,
                          timeinfo->tm_mon + 1,
                          timeinfo->tm_mday,
                          timeinfo->tm_hour,
                          timeinfo->tm_min,
                          timeinfo->tm_sec);
    if (result < 0 || result >= (int)sizeof(time_str)) {
        ESP_LOGW(TAG, "Time string truncation occurred");
    }
    
    ESP_LOGI(TAG, "NTP time synchronized successfully!");
    ESP_LOGI(TAG, "UTC time: %s", time_str);
}

// Helper function to apply timezone offset
static time_t apply_timezone_offset(time_t utc_time) {
    return utc_time + (TIMEZONE_OFFSET_HOURS * 3600);
}

// Helper function to handle successful time synchronization
static void handle_sync_success(time_t local_time) {
    ntp_synced = true;
    last_sync_time = local_time;
    last_sync_attempt = 0; // Reset retry counter on success
    app_state_set_time_synced(true);
}

// SNTP time sync callback
static void time_sync_notification_cb(struct timeval *tv) {
    ESP_LOGI(TAG, "Notification of a time synchronization event");
    
    time_t now_utc = tv->tv_sec;
    time_t now_local = apply_timezone_offset(now_utc);
    
    struct tm timeinfo;
    gmtime_r(&now_local, &timeinfo);
    
    log_synchronized_time(&timeinfo);
    update_rtc_with_time(&timeinfo);
    handle_sync_success(now_local);
}


bool ntp_sync_init() {
    if (ntp_initialized) {
        return true;
    }
    
    ESP_LOGI(TAG, "Initializing NTP synchronization (UTC+%d)", TIMEZONE_OFFSET_HOURS);
    
    esp_sntp_stop();
    esp_sntp_setoperatingmode(ESP_SNTP_OPMODE_POLL);
    esp_sntp_set_sync_mode(SNTP_SYNC_MODE_SMOOTH);
    esp_sntp_set_time_sync_notification_cb(time_sync_notification_cb);
    
    for (int i = 0; i < NTP_SERVER_CNT; i++) {
        esp_sntp_setservername(i, ntp_servers[i]);
    }
    
    ntp_initialized = true;
    ntp_synced = false;
    
    return true;
}

// Helper function to check if retry is allowed
static bool is_retry_allowed() {
    int64_t now_ms = esp_timer_get_time() / 1000;
    
    if (last_sync_attempt == 0) {
        last_sync_attempt = now_ms;
        return true;
    }
    
    int64_t elapsed = now_ms - last_sync_attempt;
    if (elapsed >= SYNC_RETRY_INTERVAL_MS) {
        last_sync_attempt = now_ms;
        return true;
    }
    
    ESP_LOGD(TAG, "NTP sync retry too soon, skipping");
    return false;
}


// Helper function to ensure NTP is initialized
static bool ensure_ntp_initialized() {
    if (ntp_initialized) {
        return true;
    }
    return ntp_sync_init();
}

// Helper function to start SNTP service
static void start_sntp_service() {
    esp_sntp_stop();
    vTaskDelay(pdMS_TO_TICKS(100));
    esp_sntp_init();
}

bool ntp_sync_start() {
    if (!ensure_ntp_initialized()) {
        ESP_LOGE(TAG, "Failed to initialize NTP");
        return false;
    }
    
    if (!is_retry_allowed()) {
        return false;
    }
    
    ESP_LOGI(TAG, "Starting NTP synchronization");
    start_sntp_service();
    
    return true;
}

void ntp_sync_stop() {
    if (!ntp_initialized) {
        return;
    }
    
    ESP_LOGI(TAG, "Stopping NTP synchronization");
    esp_sntp_stop();
    ntp_synced = false;
}

bool ntp_sync_is_synced() {
    return ntp_synced && (esp_sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED);
}

time_t ntp_sync_get_time() {
    if (ntp_sync_is_synced()) {
        time_t now;
        time(&now);
        return now;
    }
    return last_sync_time;
}
