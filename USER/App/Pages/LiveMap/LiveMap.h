#ifndef __LIVEMAP_PRESENTER_H
#define __LIVEMAP_PRESENTER_H

#include "LiveMapView.h"
#include "LiveMapModel.h"

namespace Page
{

class LiveMap : public PageBase
{
public:
    LiveMap();
    virtual ~LiveMap();

    virtual void onCustomAttrConfig();
    virtual void onViewLoad();
    virtual void onViewDidLoad();
    virtual void onViewWillAppear();
    virtual void onViewDidAppear();
    virtual void onViewWillDisappear();
    virtual void onViewDidDisappear();
    virtual void onViewUnload();
    virtual void onViewDidUnload();

private:
    LiveMapView View;
    LiveMapModel Model;

    enum
    {
        ROUTE_RENDER_POINT_MAX = 96
    };

    struct
    {
        uint32_t lastMapUpdateTime;
        uint32_t nextMapUpdateTime;
        uint32_t lastSportUpdateTime;
        uint32_t lastNavigationUpdateTime;
        uint32_t lastContShowTime;
        uint32_t lastRttStatsTime;
        uint32_t updateCnt;
        uint32_t mapReloadCnt;
        lv_timer_t* timer;
        TileConv::Point_t lastTileContOriPoint;
        int32_t lastMapX;
        int32_t lastMapY;
        int16_t lastCourseAngle;
        int lastSportSpeed;
        int32_t lastSportTripDeciKm;
        uint32_t lastSportTimeSec;
        uint32_t lastNavRevision;
        uint32_t lastNavDistanceM;
        uint32_t routeRenderRevision;
        uint16_t routeRenderLevel;
        bool isTrackAvtive;
        bool hasLastMapPoint;
        bool sportInfoValid;
        bool navInfoValid;
        bool navBannerVisible;
        bool routeRenderValid;
        bool zoomCtrlHidden;
        DataProc::Navigation_RouteStatus_t lastNavRouteStatus;
        DataProc::Navigation_State_t lastNavState;
        DataProc::Navigation_TurnType_t lastNavTurnType;
        DataProc::Navigation_RoutePoint_t routeQueryPoints[ROUTE_RENDER_POINT_MAX];
        char lastNavCueText[NAV_CUE_TEXT_MAX];

        /* 周期性 recenter：两次 recenter 之间地图容器保持静止，
         * 仅箭头在静止地图上移动（小区域重绘），偏离中心超阈值才平滑 recenter */
        lv_coord_t appliedContX;
        lv_coord_t appliedContY;
        bool hasContPos;
        bool recentering;   /* 正在平滑滑回中心的动画过程中 */

        /* 平滑滚动插值（实时滚动模式）：显示坐标向 GPS 目标坐标逐周期逼近，
         * 8.8 定点保留 1/256 像素相位（供快照亚像素渲染取用），
         * 把低频 GPS 大步拆成高频小步；轨迹记录仍用真实坐标。
         * 必须 64 位:16 级像素坐标 <<8 已超 int32(见 CheckPosition 注释) */
        int64_t dispMapXFp;
        int64_t dispMapYFp;
        bool hasDispMap;
    } priv;

    static uint16_t mapLevelCurrent;

private:
    typedef  TrackLineFilter::Area_t Area_t;

private:
    void Update();
    void UpdateDelay(uint32_t ms);
    void CheckPosition();

    /* SportInfo */
    void SportInfoUpdate();
    void NavigationBannerUpdate();
    void NavigationApproachLineUpdate(int32_t mapX, int32_t mapY);
    void RouteLineReload();

    /* MapTileCont */
    bool GetIsMapTileContChanged();
    void onMapTileContRefresh(const Area_t* area, int32_t x, int32_t y);
    void MapTileContUpdate(int32_t mapX, int32_t mapY, float course, bool forceRecenter);
    void MapTileContReload();
    void MapTileContPreload();
    
    /* TrackLine */
    void TrackLineReload(const Area_t* area, int32_t x, int32_t y);
    void TrackLineAppend(int32_t x, int32_t y);
    void TrackLineAppendToEnd(int32_t x, int32_t y);
    static void onTrackLineEvent(TrackLineFilter* filter, TrackLineFilter::Event_t* event);
    
    void AttachEvent(lv_obj_t* obj);
    static void onEvent(lv_event_t* event);
};

}

#endif
