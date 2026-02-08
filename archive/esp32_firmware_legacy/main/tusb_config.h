#ifndef TUSB_CONFIG_H
#define TUSB_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

// TinyUSB Configuration for ESP32-S3
#define CFG_TUSB_MCU                OPT_MCU_ESP32S3
#define CFG_TUSB_OS                 OPT_OS_FREERTOS

// Enable USB Device mode
#define CFG_TUD_ENABLED             1
#define CFG_TUH_ENABLED             0

// USB Device Configuration
#define CFG_TUD_MAX_SPEED           OPT_MODE_FULL_SPEED

// Mass Storage Class Configuration
#define CFG_TUD_MSC                 1
#define CFG_TUD_MSC_EP_BUFSIZE      512

// CDC Configuration (for serial, optional)
#define CFG_TUD_CDC                 0

// HID Configuration (optional)
#define CFG_TUD_HID                 0

#ifdef __cplusplus
}
#endif

#endif
