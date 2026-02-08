#ifndef STATE_COORDINATOR_H
#define STATE_COORDINATOR_H

#include <stdbool.h>

// Initialize state coordinator
// This sets up the state manager and coordinates between WiFi, NTP, and weather
bool state_coordinator_init();

// Deinitialize state coordinator
void state_coordinator_deinit();

#endif
