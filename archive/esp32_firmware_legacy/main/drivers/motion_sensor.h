#ifndef MOTION_SENSOR_H
#define MOTION_SENSOR_H

#include "../components/qmi8658/QMI8658.h"

class MotionSensor {
public:
    MotionSensor();
    bool init();
    bool detectHandRaise();
    void getMotion(float* accel, float* gyro);
    bool isDataReady();

private:
    QMI8658 _imu;
    float _lastAccel[3];
    int64_t _lastCheckTime;
    bool _handRaiseDetected;
    bool _initialized;
};

#endif