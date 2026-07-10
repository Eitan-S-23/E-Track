#ifndef __ROUTE_SELECT_H
#define __ROUTE_SELECT_H

#include "../Page.h"
#include "Common/DataProc/DataProc.h"

namespace Page
{

class RouteSelect : public PageBase
{
public:
    RouteSelect();
    virtual ~RouteSelect();

    virtual void onCustomAttrConfig();
    virtual void onViewLoad();
    virtual void onViewWillAppear();
    virtual void onViewWillDisappear();
    virtual void onViewUnload();

private:
    enum
    {
        ROW_MAX = 24
    };

    typedef struct
    {
        lv_obj_t* row;
        char path[NAV_PATH_MAX];
        char name[NAV_ROUTE_NAME_MAX];
        bool isDir;
        bool isUp;
    } Row_t;

    Account* account;
    lv_obj_t* pathLabel;
    lv_obj_t* msgLabel;
    lv_obj_t* backButton;
    lv_obj_t* focusHalo;
    lv_obj_t* list;
    Row_t rows[ROW_MAX];
    char currentPath[NAV_PATH_MAX];
    char pendingPath[NAV_PATH_MAX];
    bool pendingGoUp;
    bool pendingAsync;
    uint8_t rowCount;

    void CreateUI();
    void CreateFocusHalo();
    void LoadFiles();
    void ClearRows();
    void AddRow(const char* name, const char* path, bool isDir, bool isUp);
    bool IsFocusTarget(lv_obj_t* obj);
    void MoveFocusHaloTo(lv_obj_t* obj, bool anim);
    void SelectRow(uint8_t index);
    void EnterPath(const char* path);
    void GoUp();
    void RequestEnterPath(const char* path);
    void RequestGoUp();
    void RunPendingAction();
    void Back();
    void RefreshGroup();
    void ClearGroup();

    static void onEvent(lv_event_t* event);
    static void onAsyncAction(void* userData);
};

}

#endif
