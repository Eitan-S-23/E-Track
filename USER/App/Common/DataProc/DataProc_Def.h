#ifndef __DATA_PROC_DEF_H
#define __DATA_PROC_DEF_H

#include <stdint.h>

namespace DataProc
{

/* Recorder */
typedef enum
{
    RECORDER_CMD_START,
    RECORDER_CMD_PAUSE,
    RECORDER_CMD_CONTINUE,
    RECORDER_CMD_STOP,
} Recorder_Cmd_t;

typedef struct
{
    Recorder_Cmd_t cmd;
    uint16_t time;
} Recorder_Info_t;

/* Storage */
typedef enum
{
    STORAGE_CMD_LOAD,
    STORAGE_CMD_SAVE,
    STORAGE_CMD_ADD,
    STORAGE_CMD_REMOVE
} Storage_Cmd_t;

typedef enum
{
    STORAGE_TYPE_UNKNOW,
    STORAGE_TYPE_INT,
    STORAGE_TYPE_FLOAT,
    STORAGE_TYPE_DOUBLE,
    STORAGE_TYPE_STRING
} Storage_Type_t;

typedef struct
{
    Storage_Cmd_t cmd;
    const char* key;
    void* value;
    uint16_t size;
    Storage_Type_t type;
} Storage_Info_t;

#define STORAGE_VALUE_REG(act, data, dataType)\
do{\
    DataProc::Storage_Info_t info; \
    DATA_PROC_INIT_STRUCT(info); \
    info.cmd = DataProc::STORAGE_CMD_ADD; \
    info.key = #data; \
    info.value = &data; \
    info.size = sizeof(data); \
    info.type = dataType; \
    act->Notify("Storage", &info, sizeof(info)); \
}while(0)

typedef struct
{
    bool isDetect;
    float totalSizeMB;
    float freeSizeMB;
    const char* type;
} Storage_Basic_Info_t;

/* StatusBar */
typedef enum
{
    STATUS_BAR_STYLE_TRANSP,
    STATUS_BAR_STYLE_BLACK,
} StatusBar_Style_t;

typedef enum
{
    STATUS_BAR_CMD_APPEAR,
    STATUS_BAR_CMD_SET_STYLE,
    STATUS_BAR_CMD_SET_LABEL_REC
} StatusBar_Cmd_t;

typedef struct
{
    StatusBar_Cmd_t cmd;
    union
    {
        bool appear;
        StatusBar_Style_t style;
        struct
        {
            bool show;
            const char* str;
        } labelRec;
    } param;
} StatusBar_Info_t;

/* MusicPlayer */
typedef struct
{
    const char* music;
} MusicPlayer_Info_t;

/* Navigation */
#define NAV_PATH_MAX            256
#define NAV_ROUTE_NAME_MAX      48
#define NAV_WAYPOINT_NAME_MAX   32
#define NAV_CUE_TEXT_MAX        32

typedef enum
{
    NAV_CMD_NONE,
    NAV_CMD_SELECT_ROUTE,
    NAV_CMD_START,
    NAV_CMD_STOP,
    NAV_CMD_CLEAR_ERROR,
    NAV_CMD_REFRESH_CACHE,
    NAV_CMD_CANCEL_IMPORT,
    NAV_CMD_IMPORT_STEP
} Navigation_Command_t;

typedef enum
{
    NAV_ROUTE_STATUS_NO_ROUTE,
    NAV_ROUTE_STATUS_SELECTED_UNVALIDATED,
    NAV_ROUTE_STATUS_VALIDATING,
    NAV_ROUTE_STATUS_VALID,
    NAV_ROUTE_STATUS_INVALID,
    NAV_ROUTE_STATUS_IMPORTING,
    NAV_ROUTE_STATUS_ERROR
} Navigation_RouteStatus_t;

typedef enum
{
    NAV_STATE_INACTIVE,
    NAV_STATE_APPROACHING_ROUTE,
    NAV_STATE_ON_ROUTE,
    NAV_STATE_OFF_ROUTE,
    NAV_STATE_REVERSE_DIRECTION,
    NAV_STATE_FINISHED,
    NAV_STATE_ERROR
} Navigation_State_t;

typedef enum
{
    NAV_TURN_NONE,
    NAV_TURN_STRAIGHT,
    NAV_TURN_LEFT,
    NAV_TURN_RIGHT,
    NAV_TURN_SHARP_LEFT,
    NAV_TURN_SHARP_RIGHT,
    NAV_TURN_UTURN,
    NAV_TURN_FINISH,
    NAV_TURN_APPROACH_ROUTE,
    NAV_TURN_OFF_ROUTE,
    NAV_TURN_REVERSE
} Navigation_TurnType_t;

typedef struct
{
    char gpxPath[NAV_PATH_MAX];
    char routeName[NAV_ROUTE_NAME_MAX];
} Navigation_SelectRoute_Cmd_t;

typedef struct
{
    Navigation_Command_t cmd;
    union
    {
        Navigation_SelectRoute_Cmd_t selectRoute;
    } param;
} Navigation_CmdInfo_t;

typedef struct
{
    uint32_t revision;
    Navigation_RouteStatus_t routeStatus;
    Navigation_State_t state;
    Navigation_TurnType_t turnType;
    uint32_t distanceToTurnM;
    uint32_t distanceToFinishM;
    int32_t approachTargetLatE7;
    int32_t approachTargetLonE7;
    int16_t approachBearingDeg;
    uint8_t importProgressPct;
    bool approachTargetValid;
    bool active;
    uint16_t pointCount;
    char routeName[NAV_ROUTE_NAME_MAX];
    char selectedGpxPath[NAV_PATH_MAX];
    char cueText[NAV_CUE_TEXT_MAX];
    char errorText[NAV_CUE_TEXT_MAX];
} Navigation_Info_t;

typedef struct
{
    int32_t latE7;
    int32_t lonE7;
    uint32_t distM;
} Navigation_RoutePoint_t;

typedef enum
{
    NAV_ROUTE_WINDOW_DONE,
    NAV_ROUTE_WINDOW_PARTIAL,
    NAV_ROUTE_WINDOW_BUSY,
    NAV_ROUTE_WINDOW_STALE_REVISION,
    NAV_ROUTE_WINDOW_ERROR
} Navigation_RouteWindowStatus_t;

typedef struct
{
    uint32_t revision;
    uint16_t startIndex;
    uint16_t stride;
} Navigation_RouteWindowQuery_t;

typedef struct
{
    Navigation_RouteWindowStatus_t status;
    uint32_t revision;
    uint16_t written;
    uint16_t nextIndex;
    uint16_t totalCount;
} Navigation_RouteWindowResult_t;

Navigation_RouteWindowStatus_t Navigation_QueryRouteWindow(
    const Navigation_RouteWindowQuery_t* query,
    Navigation_RoutePoint_t* out,
    uint16_t maxCount,
    Navigation_RouteWindowResult_t* result
);

/* SysConfig */
typedef enum
{
    SYSCONFIG_CMD_LOAD,
    SYSCONFIG_CMD_SAVE,
} SysConfig_Cmd_t;

typedef struct
{
    SysConfig_Cmd_t cmd;
    float longitude;
    float latitude;
    int16_t timeZone;
    bool soundEnable;
    char language[8];
    char arrowTheme[16];
    char mapDirPath[16];
    char mapExtName[8];
    bool mapWGS84;
} SysConfig_Info_t;

/* TrackFilter */
typedef enum
{
    TRACK_FILTER_CMD_START = RECORDER_CMD_START,
    TRACK_FILTER_CMD_PAUSE = RECORDER_CMD_PAUSE,
    TRACK_FILTER_CMD_CONTINUE = RECORDER_CMD_CONTINUE,
    TRACK_FILTER_CMD_STOP = RECORDER_CMD_STOP,
} TrackFilter_Cmd_t;

typedef struct
{
    TrackFilter_Cmd_t cmd;
    void* pointCont;
    uint8_t level;
    bool isActive;
} TrackFilter_Info_t;

}

#endif
