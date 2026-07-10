#include "HAL.h"
#include "Config/Config.h"

// Undef Arduino macros that conflict with math.h
#ifdef round
#undef round
#endif
#ifdef abs
#undef abs
#endif

#include <math.h>

// Math constants
#ifndef PI
#define PI 3.14159265358979323846
#endif

#if CONFIG_GPS_USE_SIMULATOR
#include "HAL_GPS_Simulator.h"
#include "lvgl/lvgl.h"
#else
#include "TinyGPSPlus/src/TinyGPS++.h"
#endif

#define GPS_SERIAL             CONFIG_GPS_SERIAL
#define DEBUG_SERIAL           CONFIG_DEBUG_SERIAL
#define GPS_USE_TRANSPARENT    CONFIG_GPS_USE_TRANSPARENT

#if CONFIG_GPS_USE_SIMULATOR
static HAL::GPS_Simulator gpsSimulator;
static uint32_t lastUpdateTime = 0;
#else
static TinyGPSPlus gps;
#endif

void HAL::GPS_Init()
{
#if CONFIG_GPS_USE_SIMULATOR
    LV_LOG_USER("GPS: Using GPS Simulator");
    gpsSimulator.Init();
    lastUpdateTime = millis();
#else
    GPS_SERIAL.begin(9600);

    CONFIG_DEBUG_SERIAL.print("GPS: TinyGPS++ library v. ");
    CONFIG_DEBUG_SERIAL.print(TinyGPSPlus::libraryVersion());
    CONFIG_DEBUG_SERIAL.println(" by Mikal Hart");
#endif
}

void HAL::GPS_SimulatorResetPosition()
{
#if CONFIG_GPS_USE_SIMULATOR
    gpsSimulator.ResetToDefault();
#endif
}

void HAL::GPS_Update()
{
#if CONFIG_GPS_USE_SIMULATOR
    uint32_t currentTime = millis();
    uint32_t deltaTime = currentTime - lastUpdateTime;
    lastUpdateTime = currentTime;

    gpsSimulator.Update(deltaTime);
#else
#if CONFIG_GPS_BUF_OVERLOAD_CHK && !GPS_USE_TRANSPARENT
    int available = GPS_SERIAL.available();
    DEBUG_SERIAL.printf("GPS: Buffer available = %d", available);
    if(available >= SERIAL_RX_BUFFER_SIZE / 2)
    {
        DEBUG_SERIAL.print(", maybe overload!");
    }
    DEBUG_SERIAL.println();
#endif

    while (GPS_SERIAL.available() > 0)
    {
        char c = GPS_SERIAL.read();
#if GPS_USE_TRANSPARENT
        DEBUG_SERIAL.write(c);
#endif
        gps.encode(c);
    }

#if GPS_USE_TRANSPARENT
    while (DEBUG_SERIAL.available() > 0)
    {
        GPS_SERIAL.write(DEBUG_SERIAL.read());
    }
#endif
#endif
}

bool HAL::GPS_GetInfo(GPS_Info_t* info)
{
    memset(info, 0, sizeof(GPS_Info_t));

#if CONFIG_GPS_USE_SIMULATOR
    return gpsSimulator.GetInfo(info);
#else
    info->isVaild = gps.location.isValid();
    info->longitude = gps.location.lng();
    info->latitude = gps.location.lat();
    info->altitude = gps.altitude.meters();
    info->speed = gps.speed.kmph();
    info->course = gps.course.deg();

    info->clock.year = gps.date.year();
    info->clock.month = gps.date.month();
    info->clock.day = gps.date.day();
    info->clock.hour = gps.time.hour();
    info->clock.minute = gps.time.minute();
    info->clock.second = gps.time.second();
    info->satellites = gps.satellites.value();

    return info->isVaild;
#endif
}

bool HAL::GPS_LocationIsValid()
{
#if CONFIG_GPS_USE_SIMULATOR
    return gpsSimulator.LocationIsValid();
#else
    return gps.location.isValid();
#endif
}

double HAL::GPS_GetDistanceOffset(GPS_Info_t* info,  double preLong, double preLat)
{
#if CONFIG_GPS_USE_SIMULATOR
    // Simple distance calculation using Haversine formula (approximate)
    const double R = 6371000; // Earth radius in meters
    double lat1 = preLat * PI / 180.0;
    double lat2 = info->latitude * PI / 180.0;
    double deltaLat = (info->latitude - preLat) * PI / 180.0;
    double deltaLon = (info->longitude - preLong) * PI / 180.0;

    double a = sin(deltaLat/2) * sin(deltaLat/2) +
               cos(lat1) * cos(lat2) *
               sin(deltaLon/2) * sin(deltaLon/2);
    double c = 2 * atan2(sqrt(a), sqrt(1-a));

    return R * c;
#else
    return gps.distanceBetween(info->latitude, info->longitude, preLat, preLong);
#endif
}
