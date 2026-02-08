#ifndef I2C_BUS_MANAGER_H
#define I2C_BUS_MANAGER_H

#include "driver/i2c_master.h"

i2c_master_bus_handle_t get_i2c_bus_handle();
i2c_master_dev_handle_t create_i2c_device(uint8_t addr);
void scan_i2c_devices();

#endif
