#include "DataProc.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

using namespace DataProc;

#define NAV_ROUTE_POINT_MAX      768
#define NAV_IMPORT_READ_BYTES    256
#define NAV_OFF_ROUTE_M          40
#define NAV_ON_ROUTE_M           25
#define NAV_FINISH_M             30
#define NAV_PI                   3.14159265358979323846

typedef struct
{
    lv_fs_file_t file;
    bool open;
    bool haveTag;
    bool useTrack;
    bool sawTrack;
    bool sawRoute;
    char tag[160];
    uint16_t tagLen;
} ImportState_t;

typedef struct
{
    uint16_t segmentIndex;
    uint32_t distanceM;
    uint32_t routeDistM;
    int32_t targetLatE7;
    int32_t targetLonE7;
    int16_t bearingDeg;
} RouteMatch_t;

static Navigation_Info_t navigation;
static Navigation_RoutePoint_t routePoints[NAV_ROUTE_POINT_MAX];
static ImportState_t importState;
static bool acquired;
static uint16_t progressIndex;
static uint8_t offRouteCount;
static uint8_t finishCount;

static bool HasTerminator(const char* text, uint16_t size)
{
    for (uint16_t i = 0; i < size; i++)
    {
        if (text[i] == '\0')
        {
            return true;
        }
    }
    return false;
}

static void CopyBounded(char* dest, uint16_t destSize, const char* src)
{
    strncpy(dest, src, destSize);
    dest[destSize - 1] = '\0';
}

static bool IsSpaceChar(char ch)
{
    return ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n';
}

static bool IsGpxPath(const char* path)
{
    if (path == nullptr || path[0] == '\0')
    {
        return false;
    }

    size_t len = strlen(path);
    if (len < 5)
    {
        return false;
    }

    const char* ext = path + len - 4;
    return ext[0] == '.' &&
           (ext[1] == 'g' || ext[1] == 'G') &&
           (ext[2] == 'p' || ext[2] == 'P') &&
           (ext[3] == 'x' || ext[3] == 'X');
}

static bool ParseDecimalDegrees(const char* text, double minValue, double maxValue, int32_t* valueE7)
{
    if (text == nullptr || valueE7 == nullptr || text[0] == '\0')
    {
        return false;
    }

    char* end = nullptr;
    double value = strtod(text, &end);
    if (end == text)
    {
        return false;
    }
    while (*end != '\0' && IsSpaceChar(*end))
    {
        end++;
    }
    if (*end != '\0' || !(value >= minValue && value <= maxValue))
    {
        return false;
    }

    double scaled = value * 10000000.0;
    *valueE7 = (int32_t)(scaled >= 0.0 ? scaled + 0.5 : scaled - 0.5);
    return true;
}

static double DegToRad(double deg)
{
    return deg * NAV_PI / 180.0;
}

static uint32_t DistanceM(int32_t lat0E7, int32_t lon0E7, int32_t lat1E7, int32_t lon1E7)
{
    double lat0 = DegToRad((double)lat0E7 / 10000000.0);
    double lat1 = DegToRad((double)lat1E7 / 10000000.0);
    double dLat = DegToRad((double)(lat1E7 - lat0E7) / 10000000.0);
    double dLon = DegToRad((double)(lon1E7 - lon0E7) / 10000000.0);
    double a = sin(dLat / 2.0) * sin(dLat / 2.0) +
               cos(lat0) * cos(lat1) * sin(dLon / 2.0) * sin(dLon / 2.0);
    double c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a));
    return (uint32_t)(6371000.0 * c + 0.5);
}

static int16_t BearingDeg(int32_t lat0E7, int32_t lon0E7, int32_t lat1E7, int32_t lon1E7)
{
    double lat0 = DegToRad((double)lat0E7 / 10000000.0);
    double lat1 = DegToRad((double)lat1E7 / 10000000.0);
    double dLon = DegToRad((double)(lon1E7 - lon0E7) / 10000000.0);
    double y = sin(dLon) * cos(lat1);
    double x = cos(lat0) * sin(lat1) - sin(lat0) * cos(lat1) * cos(dLon);
    int16_t deg = (int16_t)(atan2(y, x) * 180.0 / NAV_PI + 0.5);
    while (deg < 0)
    {
        deg += 360;
    }
    while (deg >= 360)
    {
        deg -= 360;
    }
    return deg;
}

static void ClearApproachTarget()
{
    navigation.approachTargetLatE7 = 0;
    navigation.approachTargetLonE7 = 0;
    navigation.approachBearingDeg = 0;
    navigation.approachTargetValid = false;
}

static bool FindNearestRoutePosition(
    int32_t latE7,
    int32_t lonE7,
    uint16_t startPoint,
    uint16_t endPoint,
    RouteMatch_t* match
)
{
    if (match == nullptr || navigation.pointCount < 2)
    {
        return false;
    }

    if (startPoint >= navigation.pointCount - 1)
    {
        startPoint = navigation.pointCount - 2;
    }
    if (endPoint > navigation.pointCount)
    {
        endPoint = navigation.pointCount;
    }
    if (endPoint <= startPoint + 1)
    {
        endPoint = (uint16_t)(startPoint + 2);
        if (endPoint > navigation.pointCount)
        {
            endPoint = navigation.pointCount;
        }
    }

    const double latScale = 111320.0;
    double lonScale = latScale * cos(DegToRad((double)latE7 / 10000000.0));
    if (lonScale < 1.0)
    {
        lonScale = 1.0;
    }

    uint32_t bestDist = 0xffffffffU;
    uint16_t bestSeg = startPoint;
    double bestT = 0.0;
    double bestX = 0.0;
    double bestY = 0.0;

    for (uint16_t i = startPoint; i + 1 < endPoint; i++)
    {
        double x0 = ((double)(routePoints[i].lonE7 - lonE7) / 10000000.0) * lonScale;
        double y0 = ((double)(routePoints[i].latE7 - latE7) / 10000000.0) * latScale;
        double x1 = ((double)(routePoints[i + 1].lonE7 - lonE7) / 10000000.0) * lonScale;
        double y1 = ((double)(routePoints[i + 1].latE7 - latE7) / 10000000.0) * latScale;
        double vx = x1 - x0;
        double vy = y1 - y0;
        double len2 = vx * vx + vy * vy;
        double t = 0.0;

        if (len2 > 0.01)
        {
            t = -(x0 * vx + y0 * vy) / len2;
            if (t < 0.0)
            {
                t = 0.0;
            }
            else if (t > 1.0)
            {
                t = 1.0;
            }
        }

        double px = x0 + vx * t;
        double py = y0 + vy * t;
        uint32_t dist = (uint32_t)(sqrt(px * px + py * py) + 0.5);
        if (dist < bestDist)
        {
            bestDist = dist;
            bestSeg = i;
            bestT = t;
            bestX = px;
            bestY = py;
        }
    }

    uint32_t segDist = routePoints[bestSeg + 1].distM - routePoints[bestSeg].distM;
    match->segmentIndex = bestSeg;
    match->distanceM = bestDist;
    match->targetLatE7 = (int32_t)((double)latE7 + bestY / latScale * 10000000.0);
    match->targetLonE7 = (int32_t)((double)lonE7 + bestX / lonScale * 10000000.0);
    match->routeDistM = routePoints[bestSeg].distM + (uint32_t)((double)segDist * bestT + 0.5);
    match->bearingDeg = BearingDeg(latE7, lonE7, match->targetLatE7, match->targetLonE7);
    return true;
}

static void SetError(const char* text)
{
    navigation.routeStatus = NAV_ROUTE_STATUS_ERROR;
    navigation.state = NAV_STATE_ERROR;
    navigation.active = false;
    CopyBounded(navigation.errorText, sizeof(navigation.errorText), text);
    navigation.revision++;
}

static void CloseImport()
{
    if (importState.open)
    {
        lv_fs_close(&importState.file);
    }
    memset(&importState, 0, sizeof(importState));
}

static void ResetRuntime()
{
    acquired = false;
    progressIndex = 0;
    offRouteCount = 0;
    finishCount = 0;
    ClearApproachTarget();
}

static void ResetNavigation()
{
    memset(&navigation, 0, sizeof(navigation));
    memset(routePoints, 0, sizeof(routePoints));
    CloseImport();
    ResetRuntime();
    navigation.routeStatus = NAV_ROUTE_STATUS_NO_ROUTE;
    navigation.state = NAV_STATE_INACTIVE;
    navigation.turnType = NAV_TURN_NONE;
}

static bool ExtractAttr(const char* tag, const char* name, char* out, uint16_t outSize)
{
    const char* p = strstr(tag, name);
    if (p == nullptr)
    {
        return false;
    }
    p += strlen(name);
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

    uint16_t len = 0;
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

static bool ParsePointTag(const char* tag, int32_t* latE7, int32_t* lonE7, bool* isTrack, bool* isRoute)
{
    *isTrack = strstr(tag, "<trkpt") != nullptr || strstr(tag, ":trkpt") != nullptr;
    *isRoute = strstr(tag, "<rtept") != nullptr || strstr(tag, ":rtept") != nullptr;
    if (!*isTrack && !*isRoute)
    {
        return false;
    }

    char lat[24];
    char lon[24];
    if (!ExtractAttr(tag, "lat", lat, sizeof(lat)) || !ExtractAttr(tag, "lon", lon, sizeof(lon)))
    {
        return false;
    }

    return ParseDecimalDegrees(lat, -90.0, 90.0, latE7) &&
           ParseDecimalDegrees(lon, -180.0, 180.0, lonE7);
}

static void AppendRoutePoint(int32_t latE7, int32_t lonE7, bool isTrack, bool isRoute)
{
    if (navigation.pointCount >= NAV_ROUTE_POINT_MAX)
    {
        SetError("ROUTE TOO LONG");
        CloseImport();
        return;
    }

    if (isTrack)
    {
        importState.sawTrack = true;
        if (!importState.useTrack && importState.sawRoute)
        {
            navigation.pointCount = 0;
        }
        importState.useTrack = true;
    }
    else if (isRoute)
    {
        importState.sawRoute = true;
        if (importState.useTrack)
        {
            return;
        }
    }

    uint16_t idx = navigation.pointCount;
    routePoints[idx].latE7 = latE7;
    routePoints[idx].lonE7 = lonE7;
    routePoints[idx].distM = 0;
    if (idx > 0)
    {
        routePoints[idx].distM = routePoints[idx - 1].distM +
            DistanceM(routePoints[idx - 1].latE7, routePoints[idx - 1].lonE7, latE7, lonE7);
    }
    navigation.pointCount++;
}

static void ProcessImportByte(char ch)
{
    if (navigation.routeStatus == NAV_ROUTE_STATUS_ERROR)
    {
        return;
    }

    if (ch == '<')
    {
        importState.haveTag = true;
        importState.tagLen = 0;
    }

    if (importState.haveTag)
    {
        if (importState.tagLen + 1 < sizeof(importState.tag))
        {
            importState.tag[importState.tagLen++] = ch;
            importState.tag[importState.tagLen] = '\0';
        }
        else
        {
            importState.haveTag = false;
            importState.tagLen = 0;
        }
    }

    if (ch == '>' && importState.haveTag)
    {
        int32_t latE7 = 0;
        int32_t lonE7 = 0;
        bool isTrack = false;
        bool isRoute = false;
        if (ParsePointTag(importState.tag, &latE7, &lonE7, &isTrack, &isRoute))
        {
            AppendRoutePoint(latE7, lonE7, isTrack, isRoute);
        }
        importState.haveTag = false;
        importState.tagLen = 0;
    }
}

static void SelectRoute(const Navigation_SelectRoute_Cmd_t* route)
{
    CloseImport();
    ResetRuntime();

    if (route == nullptr)
    {
        SetError("NO ROUTE");
        return;
    }
    if (!HasTerminator(route->gpxPath, sizeof(route->gpxPath)) ||
        !HasTerminator(route->routeName, sizeof(route->routeName)))
    {
        SetError("PATH TOO LONG");
        return;
    }
    if (!IsGpxPath(route->gpxPath))
    {
        SetError(route->gpxPath[0] == '\0' ? "NO ROUTE" : "BAD GPX PATH");
        return;
    }

    memset(routePoints, 0, sizeof(routePoints));
    navigation.pointCount = 0;
    CopyBounded(navigation.selectedGpxPath, sizeof(navigation.selectedGpxPath), route->gpxPath);
    CopyBounded(navigation.routeName, sizeof(navigation.routeName), route->routeName);
    navigation.routeStatus = NAV_ROUTE_STATUS_SELECTED_UNVALIDATED;
    navigation.state = NAV_STATE_INACTIVE;
    navigation.turnType = NAV_TURN_NONE;
    navigation.active = false;
    navigation.cueText[0] = '\0';
    navigation.errorText[0] = '\0';
    navigation.distanceToTurnM = 0;
    navigation.distanceToFinishM = 0;
    ClearApproachTarget();
    navigation.importProgressPct = 0;
    navigation.revision++;
}

static void ImportStep()
{
    if (navigation.routeStatus != NAV_ROUTE_STATUS_SELECTED_UNVALIDATED &&
        navigation.routeStatus != NAV_ROUTE_STATUS_IMPORTING)
    {
        return;
    }

    if (!importState.open)
    {
        if (navigation.selectedGpxPath[0] == '\0')
        {
            SetError("NO ROUTE");
            return;
        }
        if (lv_fs_open(&importState.file, navigation.selectedGpxPath, LV_FS_MODE_RD) != LV_FS_RES_OK)
        {
            SetError("OPEN GPX FAIL");
            return;
        }
        importState.open = true;
        navigation.pointCount = 0;
        navigation.routeStatus = NAV_ROUTE_STATUS_IMPORTING;
        navigation.importProgressPct = 5;
        navigation.revision++;
    }

    uint8_t buf[NAV_IMPORT_READ_BYTES];
    uint32_t br = 0;
    if (lv_fs_read(&importState.file, buf, sizeof(buf), &br) != LV_FS_RES_OK)
    {
        CloseImport();
        SetError("READ GPX FAIL");
        return;
    }

    for (uint32_t i = 0; i < br; i++)
    {
        ProcessImportByte((char)buf[i]);
        if (navigation.routeStatus == NAV_ROUTE_STATUS_ERROR)
        {
            return;
        }
    }

    if (br < sizeof(buf))
    {
        CloseImport();
        if (navigation.pointCount < 2)
        {
            SetError("GPX NO ROUTE");
            return;
        }
        navigation.routeStatus = NAV_ROUTE_STATUS_VALID;
        navigation.importProgressPct = 100;
        navigation.distanceToFinishM = routePoints[navigation.pointCount - 1].distM;
        navigation.state = NAV_STATE_INACTIVE;
        navigation.turnType = NAV_TURN_NONE;
        navigation.active = false;
        navigation.revision++;
        return;
    }

    if (navigation.importProgressPct < 95)
    {
        navigation.importProgressPct++;
    }
    navigation.revision++;
}

static void StartNavigation()
{
    if (navigation.routeStatus != NAV_ROUTE_STATUS_VALID || navigation.pointCount < 2)
    {
        SetError("ROUTE NOT READY");
        return;
    }

    ResetRuntime();
    navigation.active = true;
    navigation.state = NAV_STATE_APPROACHING_ROUTE;
    navigation.turnType = NAV_TURN_APPROACH_ROUTE;
    CopyBounded(navigation.cueText, sizeof(navigation.cueText), "APPROACH ROUTE");
    navigation.revision++;
}

static void StopNavigation()
{
    navigation.active = false;
    navigation.state = NAV_STATE_INACTIVE;
    navigation.turnType = NAV_TURN_NONE;
    navigation.distanceToTurnM = 0;
    navigation.cueText[0] = '\0';
    ResetRuntime();
    navigation.revision++;
}

static void UpdateGuidance(Account* account)
{
    if (!navigation.active || navigation.routeStatus != NAV_ROUTE_STATUS_VALID || navigation.pointCount < 2)
    {
        return;
    }

    HAL::GPS_Info_t gps;
    if (account->Pull("GPS", &gps, sizeof(gps)) != Account::RES_OK || !gps.isVaild)
    {
        return;
    }

    int32_t latE7 = (int32_t)(gps.latitude * 10000000.0);
    int32_t lonE7 = (int32_t)(gps.longitude * 10000000.0);
    uint16_t start = acquired && progressIndex > 8 ? (uint16_t)(progressIndex - 8) : 0;
    uint16_t end = acquired ? (uint16_t)(progressIndex + 32) : navigation.pointCount;
    RouteMatch_t match;
    memset(&match, 0, sizeof(match));
    if (!FindNearestRoutePosition(latE7, lonE7, start, end, &match))
    {
        return;
    }

    progressIndex = match.segmentIndex;
    navigation.distanceToFinishM = routePoints[navigation.pointCount - 1].distM > match.routeDistM ?
        routePoints[navigation.pointCount - 1].distM - match.routeDistM : 0;
    navigation.approachTargetLatE7 = match.targetLatE7;
    navigation.approachTargetLonE7 = match.targetLonE7;
    navigation.approachBearingDeg = match.bearingDeg;
    navigation.approachTargetValid = true;

    if (!acquired)
    {
        navigation.distanceToTurnM = match.distanceM;
        if (match.distanceM <= NAV_ON_ROUTE_M)
        {
            acquired = true;
            navigation.state = NAV_STATE_ON_ROUTE;
            navigation.turnType = NAV_TURN_STRAIGHT;
            ClearApproachTarget();
            CopyBounded(navigation.cueText, sizeof(navigation.cueText), "STRAIGHT");
        }
        else
        {
            navigation.state = NAV_STATE_APPROACHING_ROUTE;
            navigation.turnType = NAV_TURN_APPROACH_ROUTE;
            CopyBounded(navigation.cueText, sizeof(navigation.cueText), "APPROACH ROUTE");
        }
        navigation.revision++;
        return;
    }

    if (match.distanceM > NAV_OFF_ROUTE_M)
    {
        if (offRouteCount < 2)
        {
            offRouteCount++;
        }
    }
    else if (match.distanceM < NAV_ON_ROUTE_M)
    {
        offRouteCount = 0;
    }

    uint32_t finishDist = DistanceM(latE7, lonE7, routePoints[navigation.pointCount - 1].latE7, routePoints[navigation.pointCount - 1].lonE7);
    if (match.segmentIndex + 2 >= navigation.pointCount && finishDist <= NAV_FINISH_M)
    {
        if (finishCount < 2)
        {
            finishCount++;
        }
    }
    else
    {
        finishCount = 0;
    }

    if (finishCount >= 2)
    {
        navigation.state = NAV_STATE_FINISHED;
        navigation.turnType = NAV_TURN_FINISH;
        navigation.distanceToTurnM = 0;
        ClearApproachTarget();
        CopyBounded(navigation.cueText, sizeof(navigation.cueText), "FINISH");
    }
    else if (offRouteCount >= 2)
    {
        navigation.state = NAV_STATE_OFF_ROUTE;
        navigation.turnType = NAV_TURN_OFF_ROUTE;
        navigation.distanceToTurnM = match.distanceM;
        CopyBounded(navigation.cueText, sizeof(navigation.cueText), "OFF ROUTE");
    }
    else
    {
        navigation.state = NAV_STATE_ON_ROUTE;
        navigation.turnType = NAV_TURN_STRAIGHT;
        navigation.distanceToTurnM = navigation.distanceToFinishM;
        ClearApproachTarget();
        CopyBounded(navigation.cueText, sizeof(navigation.cueText), "STRAIGHT");
    }
    navigation.revision++;
}

static int onEvent(Account* account, Account::EventParam_t* param)
{
    switch (param->event)
    {
    case Account::EVENT_TIMER:
        UpdateGuidance(account);
        return Account::RES_OK;
    case Account::EVENT_SUB_PULL:
    {
        if (param->size != sizeof(Navigation_Info_t))
        {
            return Account::RES_SIZE_MISMATCH;
        }

        memcpy(param->data_p, &navigation, sizeof(navigation));
        return Account::RES_OK;
    }
    case Account::EVENT_NOTIFY:
    {
        if (param->size != sizeof(Navigation_CmdInfo_t))
        {
            return Account::RES_SIZE_MISMATCH;
        }

        Navigation_CmdInfo_t* info = (Navigation_CmdInfo_t*)param->data_p;
        switch (info->cmd)
        {
        case NAV_CMD_SELECT_ROUTE:
            SelectRoute(&info->param.selectRoute);
            break;
        case NAV_CMD_IMPORT_STEP:
            ImportStep();
            break;
        case NAV_CMD_START:
            StartNavigation();
            break;
        case NAV_CMD_STOP:
            StopNavigation();
            break;
        case NAV_CMD_CANCEL_IMPORT:
            CloseImport();
            if (navigation.routeStatus == NAV_ROUTE_STATUS_IMPORTING)
            {
                navigation.routeStatus = NAV_ROUTE_STATUS_SELECTED_UNVALIDATED;
                navigation.importProgressPct = 0;
            }
            navigation.revision++;
            break;
        case NAV_CMD_CLEAR_ERROR:
            navigation.errorText[0] = '\0';
            if (navigation.routeStatus == NAV_ROUTE_STATUS_ERROR)
            {
                navigation.routeStatus = navigation.selectedGpxPath[0] ? NAV_ROUTE_STATUS_SELECTED_UNVALIDATED : NAV_ROUTE_STATUS_NO_ROUTE;
            }
            if (navigation.state == NAV_STATE_ERROR)
            {
                navigation.state = NAV_STATE_INACTIVE;
            }
            navigation.revision++;
            break;
        default:
            break;
        }
        return Account::RES_OK;
    }
    default:
        return Account::RES_UNSUPPORTED_REQUEST;
    }
}

namespace DataProc
{

Navigation_RouteWindowStatus_t Navigation_QueryRouteWindow(
    const Navigation_RouteWindowQuery_t* query,
    Navigation_RoutePoint_t* out,
    uint16_t maxCount,
    Navigation_RouteWindowResult_t* result
)
{
    if (result != nullptr)
    {
        memset(result, 0, sizeof(*result));
        result->status = NAV_ROUTE_WINDOW_ERROR;
        result->revision = navigation.revision;
        result->totalCount = navigation.pointCount;
    }

    if (query == nullptr || out == nullptr || maxCount == 0 || result == nullptr)
    {
        return NAV_ROUTE_WINDOW_ERROR;
    }

    if (query->revision != navigation.revision)
    {
        result->status = NAV_ROUTE_WINDOW_STALE_REVISION;
        return result->status;
    }

    if (navigation.routeStatus != NAV_ROUTE_STATUS_VALID || navigation.pointCount == 0)
    {
        result->status = NAV_ROUTE_WINDOW_ERROR;
        return result->status;
    }

    uint16_t stride = query->stride == 0 ? 1 : query->stride;
    uint16_t index = query->startIndex;
    uint16_t written = 0;

    while (index < navigation.pointCount && written < maxCount)
    {
        out[written++] = routePoints[index];
        index = (uint16_t)(index + stride);
    }

    result->written = written;
    result->nextIndex = index;
    result->status = index < navigation.pointCount ? NAV_ROUTE_WINDOW_PARTIAL : NAV_ROUTE_WINDOW_DONE;
    return result->status;
}

}

DATA_PROC_INIT_DEF(Navigation)
{
    ResetNavigation();
    account->Subscribe("GPS");
    account->SetTimerPeriod(1000);
    account->SetEventCallback(onEvent);
}
