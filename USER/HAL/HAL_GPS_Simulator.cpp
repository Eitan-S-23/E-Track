/*
 * GPS Simulator Implementation
 */

#include "HAL_GPS_Simulator.h"
#include "lvgl/lvgl.h"
#include "Config/Config.h"

// Undef Arduino macros that conflict with math.h
// These macros are defined in Arduino.h which is included by HAL.h
#ifdef round
#undef round
#endif
#ifdef abs
#undef abs
#endif
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif

#include <math.h>
#include <stdlib.h>

#include "SdFat.h"
#include "Arduino.h"

using namespace HAL;

// Math constants
#ifndef PI
#define PI 3.14159265358979323846
#endif

// Default location (Beijing, China) if no track file is found
#define DEFAULT_LONGITUDE  104.88393
#define DEFAULT_LATITUDE   26.56854
#define DEFAULT_ALTITUDE   50.0f

// Movement parameters
#define SIM_SPEED_MIN_KPH     50.0f      // Minimum speed in km/h
#define SIM_SPEED_MAX_KPH     80.0f     // Maximum speed in km/h
#define SIM_SPEED_CHANGE_RATE 5.0f      // Speed change per second

// Movement range in degrees (approximately 100 meters)
#define SIM_MOVEMENT_RANGE    0.1

GPS_Simulator::GPS_Simulator()
{
    memset(&state, 0, sizeof(state));
}

GPS_Simulator::~GPS_Simulator()
{
}

void GPS_Simulator::Init()
{
    LV_LOG_USER("GPS Simulator: Initializing...");

    // Initialize random seed
    srand(millis());

    // Try to load last position from track file
    LoadLastPosition();

    if (!state.initialized)
    {
        // Use default location if no track file found
        LV_LOG_WARN("GPS Simulator: No track file found, using default location");
        state.baseLongitude = DEFAULT_LONGITUDE;
        state.baseLatitude = DEFAULT_LATITUDE;
        state.baseAltitude = DEFAULT_ALTITUDE;
    }

    // Initialize current position to base position
    state.currentLongitude = state.baseLongitude;
    state.currentLatitude = state.baseLatitude;
    state.currentAltitude = state.baseAltitude;

    // Initialize movement
    state.currentSpeed = 15.0f; // Default 15 km/h
    state.currentCourse = 0.0f;
    state.updateCounter = 0;
    state.locationValid = true;
    state.initialized = true;

    LV_LOG_USER("GPS Simulator: Base position (%.6f, %.6f), altitude: %.1f m",
                state.baseLongitude, state.baseLatitude, state.baseAltitude);
}

void GPS_Simulator::LoadLastPosition()
{
    char filepath[128];

    if (ReadLastTrackFile(filepath, sizeof(filepath)))
    {
        LV_LOG_USER("GPS Simulator: Found track file: %s", filepath);

        if (ParseLastGPSPoint(filepath))
        {
            state.initialized = true;
            LV_LOG_USER("GPS Simulator: Loaded last position successfully");
        }
    }
}

bool GPS_Simulator::ReadLastTrackFile(char* filepath, size_t size)
{
    // Open track directory
    SdFile dir;
    if (!dir.open("/" CONFIG_TRACK_RECORD_FILE_DIR_NAME))
    {
        LV_LOG_WARN("GPS Simulator: Cannot open track directory");
        return false;
    }

    // Find the newest .gpx file by alphabetical order (TRK_YYYYMMDD_HHMMSS.gpx)
    // Since filenames are timestamped, the last one alphabetically is the newest
    SdFile file;
    char newestFile[64] = {0};

    while (file.openNext(&dir, O_RDONLY))
    {
        char filename[64];
        file.getName(filename, sizeof(filename));

        // Check if it's a GPX file
        if (strstr(filename, ".gpx") || strstr(filename, ".GPX"))
        {
            // Compare alphabetically (filename format: TRK_YYYYMMDD_HHMMSS.gpx)
            // Later timestamps will be alphabetically later
            if (strcmp(filename, newestFile) > 0)
            {
                strncpy(newestFile, filename, sizeof(newestFile) - 1);
            }
        }

        file.close();
    }

    dir.close();

    if (newestFile[0] != '\0')
    {
        snprintf(filepath, size, "/%s/%s", CONFIG_TRACK_RECORD_FILE_DIR_NAME, newestFile);
        return true;
    }

    return false;
}

bool GPS_Simulator::ParseLastGPSPoint(const char* filepath)
{
    lv_fs_file_t file;
    lv_fs_res_t res = lv_fs_open(&file, filepath, LV_FS_MODE_RD);

    if (res != LV_FS_RES_OK)
    {
        LV_LOG_ERROR("GPS Simulator: Cannot open file: %s", filepath);
        return false;
    }

    // Get file size
    uint32_t fileSize = 0;
    lv_fs_seek(&file, 0, LV_FS_SEEK_END);
    lv_fs_tell(&file, &fileSize);

    // Read from end of file (last 4KB or entire file if smaller)
    const uint32_t READ_SIZE = 4096;
    uint32_t readPos = (fileSize > READ_SIZE) ? (fileSize - READ_SIZE) : 0;
    uint32_t readLen = fileSize - readPos;

    lv_fs_seek(&file, readPos, LV_FS_SEEK_SET);

    // Allocate buffer
    char* buffer = (char*)malloc(readLen + 1);
    if (!buffer)
    {
        LV_LOG_ERROR("GPS Simulator: Cannot allocate buffer");
        lv_fs_close(&file);
        return false;
    }

    // Read data
    uint32_t bytesRead = 0;
    res = lv_fs_read(&file, buffer, readLen, &bytesRead);
    lv_fs_close(&file);

    if (res != LV_FS_RES_OK || bytesRead == 0)
    {
        LV_LOG_ERROR("GPS Simulator: Cannot read file");
        free(buffer);
        return false;
    }

    buffer[bytesRead] = '\0';

    // Parse last GPS point by finding the last <trkpt> tag
    double lastLon = 0, lastLat = 0;
    float lastEle = 0;
    bool foundPoint = false;

    char* searchPos = buffer;
    char* lastTrkpt = NULL;

    // Find all <trkpt> tags, remember the last one
    while ((searchPos = strstr(searchPos, "<trkpt")) != NULL)
    {
        lastTrkpt = searchPos;
        searchPos++;
    }

    if (lastTrkpt)
    {
        // Parse latitude and longitude from the last trkpt
        char* lat = strstr(lastTrkpt, "lat=\"");
        char* lon = strstr(lastTrkpt, "lon=\"");

        if (lat && lon)
        {
            lat += 5; // Skip 'lat="'
            lon += 5; // Skip 'lon="'

            lastLat = atof(lat);
            lastLon = atof(lon);
            foundPoint = true;

            // Try to get elevation
            char* ele = strstr(lastTrkpt, "<ele>");
            if (ele)
            {
                ele += 5; // Skip '<ele>'
                lastEle = atof(ele);
            }
        }
    }

    free(buffer);

    if (foundPoint)
    {
        state.baseLongitude = lastLon;
        state.baseLatitude = lastLat;
        state.baseAltitude = lastEle > 0 ? lastEle : DEFAULT_ALTITUDE;

        LV_LOG_USER("GPS Simulator: Parsed last point (%.6f, %.6f, %.1f)",
                    lastLon, lastLat, state.baseAltitude);
        return true;
    }

    LV_LOG_WARN("GPS Simulator: No GPS point found in file");
    return false;
}

void GPS_Simulator::ResetToDefault()
{
    state.baseLongitude = DEFAULT_LONGITUDE;
    state.baseLatitude = DEFAULT_LATITUDE;
    state.baseAltitude = DEFAULT_ALTITUDE;
    state.currentLongitude = state.baseLongitude;
    state.currentLatitude = state.baseLatitude;
    state.currentAltitude = state.baseAltitude;
    state.currentCourse = 0.0f;
    LV_LOG_USER("GPS Simulator: position reset to default (%.6f, %.6f)",
                state.baseLongitude, state.baseLatitude);
}

void GPS_Simulator::Update(uint32_t deltaTime)
{
    if (!state.initialized)
    {
        return;
    }

    state.updateCounter++;

    // Update simulated movement
    GenerateMovement(deltaTime);

    // Update clock
    UpdateClock();
}

void GPS_Simulator::GenerateMovement(uint32_t deltaTime)
{
    // Random speed variation
    if (state.updateCounter % 50 == 0)
    {
        float speedDelta = ((rand() % 200 - 100) / 100.0f) * SIM_SPEED_CHANGE_RATE;
        state.currentSpeed += speedDelta;

        // Clamp speed
        if (state.currentSpeed < SIM_SPEED_MIN_KPH)
            state.currentSpeed = SIM_SPEED_MIN_KPH;
        if (state.currentSpeed > SIM_SPEED_MAX_KPH)
            state.currentSpeed = SIM_SPEED_MAX_KPH;
    }

    // Random course change
    if (state.updateCounter % 30 == 0)
    {
        float courseDelta = (rand() % 60 - 30);
        state.currentCourse += courseDelta;

        if (state.currentCourse < 0)
            state.currentCourse += 360.0f;
        if (state.currentCourse >= 360.0f)
            state.currentCourse -= 360.0f;
    }

    // Calculate movement
    // Convert speed from km/h to degrees per millisecond (approximate)
    // km/h -> km/ms (÷3600000) -> degrees/ms (÷111)
    float speedInDegreesPerMs = state.currentSpeed / (3600.0f * 1000.0f * 111.0f); // 1 degree ≈ 111 km
    float distance = speedInDegreesPerMs * deltaTime;

    // Calculate new position
    float courseRad = state.currentCourse * PI / 180.0f;
    float deltaLon = distance * sin(courseRad);
    float deltaLat = distance * cos(courseRad);

    state.currentLongitude += deltaLon;
    state.currentLatitude += deltaLat;

    // Keep within range of base position
    double lonDiff = state.currentLongitude - state.baseLongitude;
    double latDiff = state.currentLatitude - state.baseLatitude;

    if (fabs(lonDiff) > SIM_MOVEMENT_RANGE)
    {
        state.currentLongitude = state.baseLongitude + (lonDiff > 0 ? SIM_MOVEMENT_RANGE : -SIM_MOVEMENT_RANGE);
        state.currentCourse = 180.0f - state.currentCourse; // Reverse direction
    }

    if (fabs(latDiff) > SIM_MOVEMENT_RANGE)
    {
        state.currentLatitude = state.baseLatitude + (latDiff > 0 ? SIM_MOVEMENT_RANGE : -SIM_MOVEMENT_RANGE);
        state.currentCourse = 360.0f - state.currentCourse; // Reverse direction
    }

    // Normalize course
    if (state.currentCourse < 0)
        state.currentCourse += 360.0f;
    if (state.currentCourse >= 360.0f)
        state.currentCourse -= 360.0f;

    // Random altitude variation
    if (state.updateCounter % 100 == 0)
    {
        state.currentAltitude += ((rand() % 20 - 10) / 10.0f);
    }
}

void GPS_Simulator::UpdateClock()
{
    // Clock is updated by the system, we don't need to simulate it
}

bool GPS_Simulator::GetInfo(GPS_Info_t* info)
{
    if (!state.initialized)
    {
        memset(info, 0, sizeof(GPS_Info_t));
        return false;
    }

    info->isVaild = state.locationValid;
    info->longitude = state.currentLongitude;
    info->latitude = state.currentLatitude;
    info->altitude = state.currentAltitude;
    info->speed = state.currentSpeed;
    info->course = state.currentCourse;
    info->satellites = 12; // Simulated good satellite count

    // Clock will be filled by the GPS data processor
    memset(&info->clock, 0, sizeof(info->clock));

    return info->isVaild;
}

bool GPS_Simulator::LocationIsValid()
{
    return state.locationValid && state.initialized;
}
