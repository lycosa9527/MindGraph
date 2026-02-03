#ifndef AXP2101_H
#define AXP2101_H

#include "driver/i2c_master.h"
#include "esp_log.h"
#include <stdint.h>
#include <stdbool.h>

#define AXP2101_I2C_ADDR 0x34
#define AXP2101_REG_BATTERY_PERCENTAGE 0xB9
#define AXP2101_REG_POWER_STATUS 0x01
#define AXP2101_REG_BATTERY_VOLTAGE_L 0x34

class AXP2101 {
public:
    AXP2101();
    ~AXP2101();
    bool begin(uint8_t sda = 15, uint8_t scl = 14);
    int getBatteryPercentage();
    bool isCharging();
    float getBatteryVoltage();
    bool isBatteryConnected();
    void setChargingCurrent(uint16_t current);
    
    void disableDC2();
    void disableDC3();
    void disableDC4();
    void disableDC5();
    void disableALDO1();
    void disableALDO2();
    void disableALDO3();
    void disableALDO4();
    void disableBLDO1();
    void disableBLDO2();
    void disableCPUSLDO();
    void disableDLDO1();
    void disableDLDO2();
    void setDC1Voltage(uint16_t voltage_mv);
    void enableDC1();
    void setALDO1Voltage(uint16_t voltage_mv);
    void enableALDO1();
    void disableTSPinMeasure();
    void setPrechargeCurr(uint8_t current);
    void setChargerConstantCurr(uint8_t current);
    void setChargerTerminationCurr(uint8_t current);
    void setChargeTargetVoltage(uint8_t voltage);
    void clearIrqStatus();

private:
    i2c_master_bus_handle_t _i2c_bus_handle;
    i2c_master_dev_handle_t _i2c_dev_handle;
    uint8_t readRegister(uint8_t reg);
    void writeRegister(uint8_t reg, uint8_t value);
    uint16_t readRegister16(uint8_t reg);
};

#endif