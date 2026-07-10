#ifndef MAINMENU_H
#define MAINMENU_H

#include "../Page.h"

struct SettingItem;

namespace Page
{
    class MainMenu : public PageBase
    {
    public:
        MainMenu();
        virtual ~MainMenu();

        virtual void onCustomAttrConfig();
        virtual void onViewLoad();
        virtual void onViewDidLoad();
        virtual void onViewWillAppear();
        virtual void onViewDidAppear();
        virtual void onViewWillDisappear();
        virtual void onViewDidDisappear();
        virtual void onViewUnload();
        virtual void onViewDidUnload();

        void home_screen_cleanup();

    private:
        enum ScreenState
        {
            SCREEN_MAIN,
            SCREEN_SUBPAGE
        };

        enum
        {
            MENU_ITEM_COUNT = 7,
            MENU_FOCUS_ITEM_MAX = 16
        };

        void AttachEvent(lv_obj_t* obj);
        void CreateBase(const char* title);
        void CreateFooter();
        void CreateFocusHalo();
        lv_obj_t* CreateMenuRow(lv_coord_t y, const char* icon, const char* text, int action);
        void CreateSettingRow(lv_coord_t y, const ::SettingItem& item);
        void ShowMainMenu();
        void ShowSettingsPage(const char* title, const ::SettingItem* items, int count);
        void ShowNavigationPage();
        void ShowRecordsPage();
        void OpenAction(int action);
        void OpenSettingAction(int action);
        void OnBack();
        void RequestBack();
        void RegisterFocusItem(lv_obj_t* obj);
        bool IsFocusItem(lv_obj_t* obj);
        void RefreshEncoderGroup();
        void ClearEncoderGroup();
        void CancelEncoderClick();
        void HandleEncoderClick(int action, bool settingAction = false);
        void CommitEncoderClick();
        int FindActionByObj(lv_obj_t* obj);
        int FindSettingActionByObj(lv_obj_t* obj);
        void MoveFocusHaloTo(lv_obj_t* obj, bool anim);

        static void onEncoderClickTimer(lv_timer_t* timer);
        static void onBackAsync(void* userData);
        static void onEvent(lv_event_t* event);

    private:
        lv_timer_t* encoderClickTimer;
        ScreenState currentScreen;
        int focusItemCount;
        int encoderPendingAction;
        bool encoderPendingSettingAction;
        bool navigationPageActive;
        uint32_t encoderShortClickTick;
        bool backRequestPending;
        lv_obj_t* backButton;
        lv_obj_t* listCont;
        lv_obj_t* focusHalo;
        lv_obj_t* encoderShortClickObj;
        lv_obj_t* itemButtons[MENU_ITEM_COUNT];
        lv_obj_t* focusItems[MENU_FOCUS_ITEM_MAX];
        int settingActions[MENU_FOCUS_ITEM_MAX];
    };
}

#endif
