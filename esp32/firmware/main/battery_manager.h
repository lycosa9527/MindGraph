#ifndef BATTERY_MANAGER_H
#define BATTERY_MANAGER_H

#include "../components/axp2101/AXP2101.h"

class BatteryManager {
public:
    BatteryManager();
    bool init();
    int getBatteryLevel();
    bool isCharging();
    float getBatteryVoltage();
    bool isBatteryConnected();
    void update();

private:
    AXP2101 _pmic;
    int _batteryLevel;
    bool _isCharging;
    int64_t _lastUpdateTime;
    bool _initialized;
};

#endif