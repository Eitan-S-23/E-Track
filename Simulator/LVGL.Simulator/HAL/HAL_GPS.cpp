#include "HAL.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <time.h>
#include <cmath>
#include "lvgl/lvgl.h"
#include "Utils/GPX_Parser/GPX_Parser.h"
#include "Config/Config.h"

#define CONFIG_TRACK_VIRTUAL_GPX_FILE_PATH    "/TRK_EXAMPLE.gpx"
#define CONFIG_TRACK_SIM_DIR_PATH             "/Track"
#define CONFIG_TRACK_SIM_DEFAULT_LONGITUDE    104.88393
#define CONFIG_TRACK_SIM_DEFAULT_LATITUDE     26.56854
#define CONFIG_TRACK_SIM_DEFAULT_ALTITUDE     50.0f
#define CONFIG_TRACK_SIM_SPEED_MIN_KPH        50.0f
#define CONFIG_TRACK_SIM_SPEED_MAX_KPH        80.0f
#define CONFIG_TRACK_SIM_SPEED_CHANGE_RATE    5.0f
#define CONFIG_TRACK_SIM_MOVEMENT_RANGE       0.1

#define PI 3.1415926535897932384626433832795f
#define HALF_PI 1.5707963267948966192313216916398f
#define TWO_PI 6.283185307179586476925286766559f
#define DEG_TO_RAD 0.017453292519943295769236907684886f
#define RAD_TO_DEG 57.295779513082320876798154814105f
#define EULER 2.718281828459045235360287471352f
#define radians(deg) ((deg)*DEG_TO_RAD)
#define degrees(rad) ((rad)*RAD_TO_DEG)
#define sq(x) ((x)*(x))

typedef struct
{
    lv_fs_file_t file;
    uint32_t size;
}FileInfo_t;

static HAL::GPS_Info_t gpsInfo;
static GPX_Parser gpxParser;
static FileInfo_t fileInfo;
static bool gpsUseGpxReplay = false;
static bool gpsFallbackInited = false;
static double gpsBaseLongitude = CONFIG_TRACK_SIM_DEFAULT_LONGITUDE;
static double gpsBaseLatitude = CONFIG_TRACK_SIM_DEFAULT_LATITUDE;
static float gpsBaseAltitude = CONFIG_TRACK_SIM_DEFAULT_ALTITUDE;
static uint32_t gpsUpdateCounter = 0;

static double distanceBetween(double lat1, double long1, double lat2, double long2)
{
    // returns distance in meters between two positions, both specified
    // as signed decimal-degrees latitude and longitude. Uses great-circle
    // distance computation for hypothetical sphere of radius 6372795 meters.
    // Because Earth is no exact sphere, rounding errors may be up to 0.5%.
    // Courtesy of Maarten Lamers
    double delta = radians(long1 - long2);
    double sdlong = sin(delta);
    double cdlong = cos(delta);
    lat1 = radians(lat1);
    lat2 = radians(lat2);
    double slat1 = sin(lat1);
    double clat1 = cos(lat1);
    double slat2 = sin(lat2);
    double clat2 = cos(lat2);
    delta = (clat1 * slat2) - (slat1 * clat2 * cdlong);
    delta = sq(delta);
    delta += sq(clat2 * sdlong);
    delta = sqrt(delta);
    double denom = (slat1 * slat2) + (clat1 * clat2 * cdlong);
    delta = atan2(delta, denom);
    return delta * 6372795;
}

static double courseTo(double lat1, double long1, double lat2, double long2)
{
    // returns course in degrees (North=0, West=270) from position 1 to position 2,
    // both specified as signed decimal-degrees latitude and longitude.
    // Because Earth is no exact sphere, calculated course may be off by a tiny fraction.
    // Courtesy of Maarten Lamers
    double dlon = radians(long2 - long1);
    lat1 = radians(lat1);
    lat2 = radians(lat2);
    double a1 = sin(dlon) * cos(lat2);
    double a2 = sin(lat1) * cos(lat2) * cos(dlon);
    a2 = cos(lat1) * sin(lat2) - a2;
    a2 = atan2(a1, a2);
    if (a2 < 0.0)
    {
        a2 += TWO_PI;
    }
    return degrees(a2);
}

static int Parser_FileReadByte(GPX_Parser* parser)
{
    FileInfo_t* info = (FileInfo_t*)parser->userData;
    uint8_t data = 0;
    lv_fs_read(&info->file, &data, 1, nullptr);
    return data;
}

static int Parser_FileAvaliable(GPX_Parser* parser)
{
    FileInfo_t* info = (FileInfo_t*)parser->userData;
    uint32_t cur = 0;
    lv_fs_tell(&info->file, &cur);
    return (info->size - cur);
}

static bool Parser_Init(GPX_Parser* parser, FileInfo_t* info)
{
    bool retval = false;
    lv_fs_res_t res = lv_fs_open(&info->file, CONFIG_TRACK_VIRTUAL_GPX_FILE_PATH, LV_FS_MODE_RD);

    if (res == LV_FS_RES_OK)
    {
        uint32_t cur = 0;
        lv_fs_tell(&info->file, &cur);
        lv_fs_seek(&info->file, 0L, LV_FS_SEEK_END);
        lv_fs_tell(&info->file, &info->size);

        /*Restore file pointer*/
        lv_fs_seek(&info->file, 0L, LV_FS_SEEK_SET);

        parser->SetCallback(Parser_FileAvaliable, Parser_FileReadByte);

        parser->userData = info;

        retval = true;
    }
    return retval;
}

static bool EndsWithGpx(const char* name)
{
    size_t len = strlen(name);
    if (len < 4)
    {
        return false;
    }

    const char* ext = name + len - 4;
    return ext[0] == '.' &&
           (ext[1] == 'g' || ext[1] == 'G') &&
           (ext[2] == 'p' || ext[2] == 'P') &&
           (ext[3] == 'x' || ext[3] == 'X');
}

static bool FindNewestTrackGpx(char* path, size_t size)
{
    lv_fs_dir_t dir;
    if (lv_fs_dir_open(&dir, CONFIG_TRACK_SIM_DIR_PATH) != LV_FS_RES_OK)
    {
        return false;
    }

    char name[96];
    char newest[96] = {0};
    while (1)
    {
        if (lv_fs_dir_read(&dir, name) != LV_FS_RES_OK || name[0] == '\0')
        {
            break;
        }

        if (name[0] == '/')
        {
            continue;
        }

        if (EndsWithGpx(name) && strcmp(name, newest) > 0)
        {
            strncpy(newest, name, sizeof(newest));
            newest[sizeof(newest) - 1] = '\0';
        }
    }
    lv_fs_dir_close(&dir);

    if (newest[0] == '\0')
    {
        return false;
    }

    snprintf(path, size, "%s/%s", CONFIG_TRACK_SIM_DIR_PATH, newest);
    return true;
}

static bool ExtractAttr(const char* tag, const char* attr, char* out, size_t outSize)
{
    const char* p = strstr(tag, attr);
    if (p == nullptr)
    {
        return false;
    }

    p += strlen(attr);
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')
    {
        p++;
    }
    if (*p != '=')
    {
        return false;
    }
    p++;
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')
    {
        p++;
    }

    char quote = *p;
    if (quote != '"' && quote != '\'')
    {
        return false;
    }
    p++;

    size_t len = 0;
    while (*p != '\0' && *p != quote)
    {
        if (len + 1 >= outSize)
        {
            return false;
        }
        out[len++] = *p++;
    }
    out[len] = '\0';
    return *p == quote;
}

static bool ParseLastTrackPoint(const char* path)
{
    lv_fs_file_t file;
    if (lv_fs_open(&file, path, LV_FS_MODE_RD) != LV_FS_RES_OK)
    {
        return false;
    }

    uint32_t fileSize = 0;
    lv_fs_seek(&file, 0, LV_FS_SEEK_END);
    lv_fs_tell(&file, &fileSize);

    const uint32_t readSizeMax = 4096;
    uint32_t readPos = fileSize > readSizeMax ? fileSize - readSizeMax : 0;
    uint32_t readLen = fileSize - readPos;
    lv_fs_seek(&file, readPos, LV_FS_SEEK_SET);

    char* buffer = (char*)malloc(readLen + 1);
    if (buffer == nullptr)
    {
        lv_fs_close(&file);
        return false;
    }

    uint32_t bytesRead = 0;
    lv_fs_res_t res = lv_fs_read(&file, buffer, readLen, &bytesRead);
    lv_fs_close(&file);
    if (res != LV_FS_RES_OK || bytesRead == 0)
    {
        free(buffer);
        return false;
    }
    buffer[bytesRead] = '\0';

    const char* search = buffer;
    const char* lastPoint = nullptr;
    while ((search = strstr(search, "<trkpt")) != nullptr)
    {
        lastPoint = search++;
    }
    search = buffer;
    while ((search = strstr(search, "<rtept")) != nullptr)
    {
        lastPoint = search++;
    }

    bool found = false;
    if (lastPoint != nullptr)
    {
        char lat[24];
        char lon[24];
        if (ExtractAttr(lastPoint, "lat", lat, sizeof(lat)) &&
            ExtractAttr(lastPoint, "lon", lon, sizeof(lon)))
        {
            gpsBaseLatitude = atof(lat);
            gpsBaseLongitude = atof(lon);
            found = true;

            const char* ele = strstr(lastPoint, "<ele>");
            if (ele != nullptr)
            {
                gpsBaseAltitude = (float)atof(ele + 5);
                if (gpsBaseAltitude <= 0.0f)
                {
                    gpsBaseAltitude = CONFIG_TRACK_SIM_DEFAULT_ALTITUDE;
                }
            }
        }
    }

    free(buffer);
    return found;
}

static void InitFallbackSimulator()
{
    char path[128];
    gpsBaseLongitude = CONFIG_TRACK_SIM_DEFAULT_LONGITUDE;
    gpsBaseLatitude = CONFIG_TRACK_SIM_DEFAULT_LATITUDE;
    gpsBaseAltitude = CONFIG_TRACK_SIM_DEFAULT_ALTITUDE;

    if (FindNewestTrackGpx(path, sizeof(path)))
    {
        ParseLastTrackPoint(path);
    }

    gpsInfo.longitude = gpsBaseLongitude;
    gpsInfo.latitude = gpsBaseLatitude;
    gpsInfo.altitude = gpsBaseAltitude;
    gpsInfo.speed = 15.0f;
    gpsInfo.course = 0.0f;
    gpsInfo.satellites = 12;
    gpsInfo.isVaild = true;
    gpsFallbackInited = true;
}

static void UpdateFallbackSimulator()
{
    gpsUpdateCounter++;

    if (gpsUpdateCounter % 50 == 0)
    {
        float speedDelta = ((rand() % 200 - 100) / 100.0f) * CONFIG_TRACK_SIM_SPEED_CHANGE_RATE;
        gpsInfo.speed += speedDelta;
        if (gpsInfo.speed < CONFIG_TRACK_SIM_SPEED_MIN_KPH)
        {
            gpsInfo.speed = CONFIG_TRACK_SIM_SPEED_MIN_KPH;
        }
        if (gpsInfo.speed > CONFIG_TRACK_SIM_SPEED_MAX_KPH)
        {
            gpsInfo.speed = CONFIG_TRACK_SIM_SPEED_MAX_KPH;
        }
    }

    if (gpsUpdateCounter % 30 == 0)
    {
        gpsInfo.course += (float)(rand() % 60 - 30);
        if (gpsInfo.course < 0.0f)
        {
            gpsInfo.course += 360.0f;
        }
        if (gpsInfo.course >= 360.0f)
        {
            gpsInfo.course -= 360.0f;
        }
    }

    float speedDegPerMs = gpsInfo.speed / (3600.0f * 1000.0f * 111.0f);
    float distance = speedDegPerMs * CONFIG_GPS_REFR_PERIOD;
    float courseRad = gpsInfo.course * PI / 180.0f;
    gpsInfo.longitude += distance * sin(courseRad);
    gpsInfo.latitude += distance * cos(courseRad);

    double lonDiff = gpsInfo.longitude - gpsBaseLongitude;
    double latDiff = gpsInfo.latitude - gpsBaseLatitude;
    if (fabs(lonDiff) > CONFIG_TRACK_SIM_MOVEMENT_RANGE)
    {
        gpsInfo.longitude = gpsBaseLongitude + (lonDiff > 0 ? CONFIG_TRACK_SIM_MOVEMENT_RANGE : -CONFIG_TRACK_SIM_MOVEMENT_RANGE);
        gpsInfo.course = 180.0f - gpsInfo.course;
    }
    if (fabs(latDiff) > CONFIG_TRACK_SIM_MOVEMENT_RANGE)
    {
        gpsInfo.latitude = gpsBaseLatitude + (latDiff > 0 ? CONFIG_TRACK_SIM_MOVEMENT_RANGE : -CONFIG_TRACK_SIM_MOVEMENT_RANGE);
        gpsInfo.course = 360.0f - gpsInfo.course;
    }
    if (gpsInfo.course < 0.0f)
    {
        gpsInfo.course += 360.0f;
    }
    if (gpsInfo.course >= 360.0f)
    {
        gpsInfo.course -= 360.0f;
    }

    if (gpsUpdateCounter % 100 == 0)
    {
        gpsInfo.altitude += (float)((rand() % 20 - 10) / 10.0f);
    }
}

bool HAL::GPS_GetInfo(GPS_Info_t* info)
{
    Clock_GetInfo(&gpsInfo.clock);
    *info = gpsInfo;
    return true;
}

void HAL::GPS_Init()
{
    srand((unsigned)time(nullptr));
    gpsInfo.longitude = CONFIG_GPS_LONGITUDE_DEFAULT;
    gpsInfo.latitude = CONFIG_GPS_LATITUDE_DEFAULT;
    gpsUseGpxReplay = Parser_Init(&gpxParser, &fileInfo);
    gpsInfo.isVaild = gpsUseGpxReplay;

    if (gpsUseGpxReplay)
    {
        gpsInfo.satellites = 10;
    }
    else
    {
        InitFallbackSimulator();
    }

    lv_timer_create(
        [](lv_timer_t* timer) {
            GPS_Update();
        },
        CONFIG_GPS_REFR_PERIOD,
        nullptr
    );
}

static time_t Clock_MakeTime(GPX_Parser::Time_t* time)
{
    struct tm t;
    memset(&t, 0, sizeof(t));
    t.tm_year = time->year - 1900;
    t.tm_mon = time->month;
    t.tm_mday = time->day;
    t.tm_hour = time->hour;
    t.tm_min = time->minute;
    t.tm_sec = time->second;

    return mktime(&t);
}

static double Clock_GetDiffTime(GPX_Parser::Time_t* time1, GPX_Parser::Time_t* time2)
{
    time_t t1 = Clock_MakeTime(time1);
    time_t t2 = Clock_MakeTime(time2);
    return difftime(t1, t2);
}

void HAL::GPS_Update()
{
    if (!gpsUseGpxReplay)
    {
        if (!gpsFallbackInited)
        {
            InitFallbackSimulator();
        }
        UpdateFallbackSimulator();
        return;
    }

    static GPX_Parser::Point_t prePoint;
    static bool isReset = false;

    GPX_Parser::Point_t point;
    memset(&point, 0, sizeof(point));

    int parserFlag = gpxParser.ReadNext(&point);

    if (parserFlag & GPX_Parser::PARSER_FLAG_LAT && parserFlag & GPX_Parser::PARSER_FLAG_LNG)
    {
        if (!isReset)
        {
            gpsInfo.longitude = point.longitude;
            gpsInfo.latitude = point.latitude;
            gpsInfo.altitude = point.altitude;

            prePoint = point;
            isReset = true;
            return;
        }

        double distance = GPS_GetDistanceOffset(&gpsInfo, point.longitude, point.latitude);
        double diffTime = CONFIG_GPS_REFR_PERIOD / 1000.0;

        if (parserFlag & GPX_Parser::PARSER_FLAG_TIME)
        {
            diffTime = Clock_GetDiffTime(&point.time, &prePoint.time);
        }

        if (std::abs(diffTime) >= 0.0001)
        {
            gpsInfo.speed = (float)(distance / diffTime) * 3.6f;
        }

        gpsInfo.course = (float)courseTo(
            gpsInfo.latitude,
            gpsInfo.longitude,
            point.latitude,
            point.longitude
        );

        gpsInfo.longitude = point.longitude;
        gpsInfo.latitude = point.latitude;
        gpsInfo.altitude = point.altitude;
        prePoint = point;
    }
    else if (parserFlag & GPX_Parser::PARSER_FLAG_EOF)
    {
        lv_fs_seek(&fileInfo.file, 0, LV_FS_SEEK_SET);
        isReset = false;
    }
}

double HAL::GPS_GetDistanceOffset(GPS_Info_t* info, double preLong, double preLat)
{
    return distanceBetween(info->latitude, info->longitude, preLat, preLong);
}
