#ifndef PCF85063_H
#define PCF85063_H

#include "driver/i2c_master.h"
#include <stdint.h>
#include <stdbool.h>

#define PCF85063_I2C_ADDR 0x51
#define PCF85063_REG_CONTROL_1 0x00
#define PCF85063_REG_SECONDS 0x04

class PCF85063 {
public:
    PCF85063();
    bool begin(uint8_t sda = 21, uint8_t scl = 22);
    void setTime(uint8_t hour, uint8_t minute, uint8_t second);
    void setDate(uint8_t day, uint8_t month, uint16_t year);
    void getTime(uint8_t* hour, uint8_t* minute, uint8_t* second);
    void getDate(uint8_t* day, uint8_t* month, uint16_t* year);
    void setDateTime(uint8_t year, uint8_t month, uint8_t day, uint8_t hour, uint8_t minute, uint8_t second);
    bool isValid();

private:
    i2c_master_dev_handle_t _i2c_dev_handle;
    uint8_t bcdToDec(uint8_t bcd);
    uint8_t decToBcd(uint8_t dec);
    uint8_t readRegister(uint8_t reg);
    void writeRegister(uint8_t reg, uint8_t value);
};

#endif