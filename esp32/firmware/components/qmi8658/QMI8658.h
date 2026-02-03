#ifndef QMI8658_H
#define QMI8658_H

#include "driver/i2c_master.h"
#include <stdint.h>
#include <stdbool.h>

#define QMI8658_I2C_ADDR 0x6A
#define QMI8658_REG_WHO_AM_I 0x00
#define QMI8658_REG_CTRL1 0x02
#define QMI8658_REG_ACC_X_L 0x35
#define QMI8658_REG_GYRO_X_L 0x3D

class QMI8658 {
public:
    QMI8658();
    bool begin(uint8_t sda = 21, uint8_t scl = 22);
    void readAccelerometer(float* accel);
    void readGyroscope(float* gyro);
    void readMotion(float* accel, float* gyro);
    bool isDataReady();

private:
    i2c_master_dev_handle_t _i2c_dev_handle;
    int16_t readRegister16(uint8_t reg);
    uint8_t readRegister(uint8_t reg);
    void writeRegister(uint8_t reg, uint8_t value);
};

#endif