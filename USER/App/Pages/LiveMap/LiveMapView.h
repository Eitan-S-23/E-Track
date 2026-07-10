#ifndef __LIVEMAP_VIEW_H
#define __LIVEMAP_VIEW_H

#include "../Page.h"
#include <vector>
#include "Utils/lv_poly_line/lv_poly_line.h"
#include "Config/Config.h"

namespace Page
{

class LiveMapView
{
public:
    struct
    {
        lv_obj_t* labelInfo;

        lv_style_t styleCont;
        lv_style_t styleNavCont;
        lv_style_t styleLabel;
        lv_style_t styleLine;
        lv_style_t styleRouteLine;
        lv_style_t styleApproachLine;

        struct
        {
            lv_obj_t* cont;
            lv_obj_t* imgArrow;
            lv_obj_t** imgTiles;
            uint32_t tileNum;
#if CONFIG_LIVE_MAP_SNAPSHOT_ENABLE
            lv_obj_t* imgSnapshot;   /* 视口快照图，替代瓦片 img 阵列 */
#endif
        } map;

        struct
        {
            lv_obj_t* cont;
            lv_poly_line* lineTrack;
            lv_obj_t* lineActive;
            lv_point_t pointActive[2];
        } track;

        struct
        {
            lv_poly_line* lineRoute;
            lv_obj_t* lineApproach;
            lv_point_t approachPoints[2];
        } route;

        struct
        {
            lv_obj_t* cont;
            lv_obj_t* labelInfo;
            lv_obj_t* slider;
        } zoom;

        struct
        {
            lv_obj_t* cont;
        } move;

        struct
        {
            lv_obj_t* cont;

            lv_obj_t* labelSpeed;
            lv_obj_t* labelTrip;
            lv_obj_t* labelTime;
        } sportInfo;

        struct
        {
            lv_obj_t* cont;
            lv_obj_t* labelIcon;
            lv_obj_t* labelText;
            lv_obj_t* labelDist;
            lv_obj_t* labelUnit;
        } nav;
    } ui;

    void Create(lv_obj_t* root, uint32_t tileNum);
    void Delete();
    void SetImgArrowStatus(lv_coord_t x, lv_coord_t y, float angle)
    {
        lv_obj_t* img = ui.map.imgArrow;

        // Only update position if it changed (avoid unnecessary redraws)
        if (x != lastArrowX || y != lastArrowY)
        {
            lv_obj_set_pos(img, x, y);
            lastArrowX = x;
            lastArrowY = y;
        }

        // Only update angle if it changed significantly (>= 1 degree)
        // Image rotation is CPU-intensive, avoid if angle didn't change
        int16_t newAngle = int16_t(angle * 10);
        int16_t angleDiff = newAngle - lastArrowAngle;
        if (angleDiff < -10 || angleDiff > 10)  // Absolute difference >= 1 degree
        {
            lv_img_set_angle(img, newAngle);
            lastArrowAngle = newAngle;
        }
    }
    void SetMapContPos(lv_coord_t x, lv_coord_t y)
    {
        // Only update map container position if it changed
        if (x != lastMapContX || y != lastMapContY)
        {
            lv_obj_set_pos(ui.map.cont, x, y);
            lastMapContX = x;
            lastMapContY = y;
        }
    }
    void SetMapTile(uint32_t tileSize, uint32_t widthCnt);
    void SetMapTileSrc(uint32_t index, const char* src);
#if CONFIG_LIVE_MAP_SNAPSHOT_ENABLE
    void SetSnapshotSrc(const void* src)
    {
        lv_img_set_src(ui.map.imgSnapshot, src);
    }
    void SetSnapshotPos(lv_coord_t x, lv_coord_t y)
    {
        lv_obj_set_pos(ui.map.imgSnapshot, x, y);
    }
#endif
    void SetArrowTheme(const char* theme);
    void SetLineActivePoint(lv_coord_t x, lv_coord_t y);
    void SetNavigationBannerVisible(bool visible);
    void SetNavigationBanner(const char* icon, const char* text, uint32_t distanceM, bool distanceValid);
    void RouteLineStart();
    void RouteLineAppend(lv_coord_t x, lv_coord_t y);
    void RouteLineStop();
    void RouteLineReset();
    void SetApproachLine(lv_coord_t fromX, lv_coord_t fromY, lv_coord_t toX, lv_coord_t toY, bool visible);

private:
    // Cache last positions to avoid unnecessary LVGL updates
    lv_coord_t lastArrowX = -1000;
    lv_coord_t lastArrowY = -1000;
    int16_t lastArrowAngle = -3600;
    lv_coord_t lastMapContX = -10000;
    lv_coord_t lastMapContY = -10000;
    lv_point_t lastActivePoint[2] = {{0, 0}, {0, 0}};
    bool lastActiveLineValid = false;
    void Style_Create();
    void Map_Create(lv_obj_t* par, uint32_t tileNum);
    void ZoomCtrl_Create(lv_obj_t* par);
    void SportInfo_Create(lv_obj_t* par);
    void NavigationBanner_Create(lv_obj_t* par);
    lv_obj_t* ImgLabel_Create(lv_obj_t* par, const void* img_src, lv_coord_t x_ofs, lv_coord_t y_ofs);
    void Route_Create(lv_obj_t* par);
    void Track_Create(lv_obj_t* par);
};

}

#endif // !__VIEW_H
