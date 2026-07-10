/*
 * GPS Simulator for AT32 X-Track
 *
 * This module simulates GPS data for testing when no real GPS hardware is available.
 * It generates realistic GPS coordinates based on the last saved track location.
 */

#ifndef __HAL_GPS_SIMULATOR_H
#define __HAL_GPS_SIMULATOR_H

#include "Arduino.h"
#include "../App/Common/HAL/HAL_Def.h"

namespace HAL
{

class GPS_Simulator
{
public:
    GPS_Simulator();
    ~GPS_Simulator();

    void Init();
    void Update(uint32_t deltaTime);
    bool GetInfo(GPS_Info_t* info);
    bool LocationIsValid();
    /* 位置重置回 DEFAULT 坐标:随机游走出图后由 RTT 调试命令拉回 */
    void ResetToDefault();

private:
    struct SimState
    {
        double baseLongitude;
        double baseLatitude;
        float baseAltitude;

        double currentLongitude;
        double currentLatitude;
        float currentAltitude;

        float currentSpeed;      // km/h
        float currentCourse;     // degrees

        uint32_t updateCounter;
        bool initialized;
        bool locationValid;
    };

    SimState state;

    void LoadLastPosition();
    bool ReadLastTrackFile(char* filepath, size_t size);
    bool ParseLastGPSPoint(const char* filepath);
    void GenerateMovement(uint32_t deltaTime);
    void UpdateClock();
};

}

#endif // __HAL_GPS_SIMULATOR_H
