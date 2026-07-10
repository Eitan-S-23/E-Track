#ifndef __ROUTE_IMPORT_H
#define __ROUTE_IMPORT_H

#include "../Page.h"
#include "Common/DataProc/DataProc.h"

namespace Page
{

class RouteImport : public PageBase
{
public:
    RouteImport();
    virtual ~RouteImport();

    virtual void onViewLoad();
    virtual void onViewDidAppear();
    virtual void onViewWillDisappear();
    virtual void onViewUnload();

private:
    enum
    {
        ROUTE_SEG_COUNT = 18,
        HEADER_SEG_COUNT = 10
    };

    Account* account;
    lv_timer_t* timer;
    lv_obj_t* titleLabel;
    lv_obj_t* statusLabel;
    lv_obj_t* fileLabel;
    lv_obj_t* progressArc;
    lv_obj_t* percentValueLabel;
    lv_obj_t* percentUnitLabel;
    lv_obj_t* routeSegs[ROUTE_SEG_COUNT];
    lv_obj_t* headerSegs[HEADER_SEG_COUNT];
    bool done;
    uint8_t lastProgressPct;

    void CreateUI();
    void CreateFrame();
    void CreateMapTexture();
    void CreateHeaderPanel();
    void CreateRoutePreview();
    void CreateProgressCard();
    void UpdateProgress(uint8_t pct);
    void Tick();
    void Cancel();
    static void onTimer(lv_timer_t* timer);
    static void onEvent(lv_event_t* event);
};

}

#endif
