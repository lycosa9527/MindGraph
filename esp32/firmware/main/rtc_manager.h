#ifndef RTC_MANAGER_H
#define RTC_MANAGER_H

#include "../components/pcf85063/PCF85063.h"
#include <string>

class RTCManager {
public:
    RTCManager();
    bool init();
    void setTime(uint8_t hour, uint8_t minute, uint8_t second);
    void setDate(uint8_t day, uint8_t month, uint16_t year);
    void getTime(uint8_t* hour, uint8_t* minute, uint8_t* second);
    void getDate(uint8_t* day, uint8_t* month, uint16_t* year);
    void setDateTime(uint8_t year, uint8_t month, uint8_t day, uint8_t hour, uint8_t minute, uint8_t second);
    std::string getTimeString();
    std::string getDateString();
    bool isValid();

private:
    PCF85063 _rtc;
    bool _initialized;
};

#endif