#ifndef USB_MSC_H
#define USB_MSC_H

#include <stdbool.h>

bool usb_msc_init();
void usb_msc_deinit();
bool usb_msc_is_connected();
void usb_msc_switch_to_app();  // Switch storage access to app
void usb_msc_switch_to_usb();   // Switch storage access to USB host

#endif
