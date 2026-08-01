#ifndef E_TRACK_FIRMWARE_UPDATE_H
#define E_TRACK_FIRMWARE_UPDATE_H

#include "../Page.h"
#include "Common/DataProc/DataProc.h"
#include "Utils/OtaUpdate/OtaUpdate.h"

namespace Page
{

class FirmwareUpdate : public PageBase
{
public:
    FirmwareUpdate();
    virtual ~FirmwareUpdate();

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

    enum ViewMode
    {
        MODE_BROWSER,
        MODE_CONFIRM,
        MODE_WORKING,
        MODE_RESULT
    };

    typedef struct
    {
        lv_obj_t* row;
        char path[NAV_PATH_MAX];
        char name[NAV_ROUTE_NAME_MAX];
        bool isDir;
        bool isUp;
    } Row_t;

    OtaUpdate::Session updater;
    ota_sd_package_info_t selectedInfo;
    lv_obj_t* titleLabel;
    lv_obj_t* pathLabel;
    lv_obj_t* msgLabel;
    lv_obj_t* detailLabel;
    lv_obj_t* backButton;
    lv_obj_t* focusHalo;
    lv_obj_t* list;
    lv_obj_t* confirmPanel;
    lv_obj_t* confirmNameLabel;
    lv_obj_t* confirmKindLabel;
    lv_obj_t* currentVersionLabel;
    lv_obj_t* targetVersionLabel;
    lv_obj_t* cancelButton;
    lv_obj_t* startButton;
    lv_obj_t* workPanel;
    lv_obj_t* workStatusLabel;
    lv_obj_t* workNameLabel;
    lv_obj_t* workKindLabel;
    lv_obj_t* progressBar;
    lv_obj_t* progressLabel;
    lv_obj_t* workDetailLabel;
    lv_obj_t* resultButton;
    lv_timer_t* workTimer;
    Row_t rows[ROW_MAX];
    char currentPath[NAV_PATH_MAX];
    char pendingPath[NAV_PATH_MAX];
    char selectedPath[NAV_PATH_MAX];
    char selectedName[NAV_ROUTE_NAME_MAX];
    bool pendingGoUp;
    bool pendingAsync;
    bool deviceReady;
    bool applyPending;
    bool resultSuccess;
    uint8_t rowCount;
    ViewMode mode;

    void CreateUI();
    void CreateBrowserUI();
    void CreateConfirmUI();
    void CreateWorkUI();
    void CreateFocusHalo();
    void LoadFiles();
    void ClearRows();
    void AddRow(const char* name, const char* path,
                bool isDir, bool isUp);
    bool IsFocusTarget(lv_obj_t* obj);
    void MoveFocusHaloTo(lv_obj_t* obj, bool anim);
    void SelectRow(uint8_t index);
    void EnterPath(const char* path);
    void GoUp();
    void RequestEnterPath(const char* path);
    void RequestGoUp();
    void RunPendingAction();
    void ShowConfirm(const Row_t& row);
    void HideConfirm();
    void StartImport();
    void RunWorkStep();
    void FinishImport(bool success);
    void Back();
    void RefreshGroup();
    void ClearGroup();
    void SetBrowserMessage(const char* message, const char* detail);

    static void onEvent(lv_event_t* event);
    static void onAsyncAction(void* userData);
    static void onWorkTimer(lv_timer_t* timer);
};

}

#endif
