#ifndef SD_STORAGE_H
#define SD_STORAGE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "driver/spi_common.h"
#include "driver/sdspi_host.h"
#include "sdmmc_cmd.h"
#include "esp_vfs_fat.h"

#define SD_CS_PIN 17

class SDStorage {
public:
    SDStorage();
    bool init();
    bool saveAudio(const char* filename, uint8_t* data, size_t len);
    bool loadConfig(const char* filename, char* buffer, size_t len);
    bool saveConfig(const char* filename, const char* data);
    bool fileExists(const char* filename);
    bool deleteFile(const char* filename);
    bool format();

private:
    bool _initialized;
};

#endif