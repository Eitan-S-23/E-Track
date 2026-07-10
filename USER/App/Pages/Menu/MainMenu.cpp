#include "MainMenu.h"
#include "Common/DataProc/DataProc.h"

#include <string.h>

using namespace Page;

struct SettingItem
{
    const char* name;
    const char* value;
    bool toggle;
    bool on;
    int action;
};

#define MENU_ACTION_DEVICE     0
#define MENU_ACTION_RECORDS    1
#define MENU_ACTION_NAV        2
#define MENU_ACTION_DISPLAY    3
#define MENU_ACTION_SENSOR     4
#define MENU_ACTION_SYSTEM     5
#define MENU_ACTION_ABOUT      6
#define SETTING_ACTION_NONE    0
#define SETTING_ACTION_ROUTE_SELECT  1
#define SETTING_ACTION_NAV_TOGGLE    2

#define ICON_DETAIL     "\xEE\x98\xAD" /* U+E62D */
#define ICON_RECORD     "\xEE\x98\x93" /* U+E613 */
#define ICON_NAV        "\xEE\x99\x83" /* U+E643 */
#define ICON_BRIGHTNESS "\xEE\x98\x88" /* U+E608 */
#define ICON_SENSOR     "\xEE\x98\x9E" /* U+E61E */
#define ICON_SETTING    "\xEE\xA1\x91" /* U+E851 */
#define ICON_BACK       "\xEE\x94\x81" /* U+E501 iconfont: back */

#define TXT_DEVICE          "\xE8\xAE\xBE\xE5\xA4\x87\xE4\xBF\xA1\xE6\x81\xAF"
#define TXT_RECORDS         "\xE9\xAA\x91\xE8\xA1\x8C\xE8\xAE\xB0\xE5\xBD\x95"
#define TXT_NAV             "\xE5\xAF\xBC\xE8\x88\xAA\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_DISPLAY         "\xE6\x98\xBE\xE7\xA4\xBA\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_SENSOR          "\xE4\xBC\xA0\xE6\x84\x9F\xE5\x99\xA8\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_SYSTEM          "\xE7\xB3\xBB\xE7\xBB\x9F\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_ABOUT           "\xE5\x85\xB3\xE4\xBA\x8E\xE8\xAE\xBE\xE5\xA4\x87"
#define TXT_NAV_MODE        "\xE5\xAF\xBC\xE8\x88\xAA\xE6\xA8\xA1\xE5\xBC\x8F"
#define TXT_MAP_NAV         "\xE5\x9C\xB0\xE5\x9B\xBE\xE5\xAF\xBC\xE8\x88\xAA"
#define TXT_ROUTE_PLAN      "\xE8\xB7\xAF\xE7\xBA\xBF\xE8\xA7\x84\xE5\x88\x92"
#define TXT_AUTO_PLAN       "\xE8\x87\xAA\xE5\x8A\xA8\xE8\xA7\x84\xE5\x88\x92"
#define TXT_VOICE_PROMPT    "\xE8\xAF\xAD\xE9\x9F\xB3\xE6\x8F\x90\xE7\xA4\xBA"
#define TXT_ON              "\xE5\xBC\x80\xE5\x90\xAF"
#define TXT_OFF_ROUTE_GUIDE "\xE5\x81\x8F\xE8\x88\xAA\xE6\x8C\x87\xE5\xBC\x95"
#define TXT_ROUTE_DEVIATION "\xE8\xB7\xAF\xE7\xBA\xBF\xE5\x81\x8F\xE7\xA6\xBB\xE6\x8F\x90\xE9\x86\x92"
#define TXT_DEST_MGMT       "\xE7\x9B\xAE\xE7\x9A\x84\xE5\x9C\xB0\xE7\xAE\xA1\xE7\x90\x86"
#define TXT_MAP_MGMT        "\xE5\x9C\xB0\xE5\x9B\xBE\xE7\xAE\xA1\xE7\x90\x86"
#define TXT_BRIGHTNESS      "\xE4\xBA\xAE\xE5\xBA\xA6\xE8\xB0\x83\xE8\x8A\x82"
#define TXT_AUTO_BRIGHT     "\xE8\x87\xAA\xE5\x8A\xA8\xE4\xBA\xAE\xE5\xBA\xA6"
#define TXT_THEME           "\xE4\xB8\xBB\xE9\xA2\x98\xE9\xA3\x8E\xE6\xA0\xBC"
#define TXT_TECH_BLUE       "\xE7\xA7\x91\xE6\x8A\x80\xE8\x93\x9D"
#define TXT_DASH_LAYOUT     "\xE4\xBB\xAA\xE8\xA1\xA8\xE7\x9B\x98\xE5\xB8\x83\xE5\xB1\x80"
#define TXT_LAYOUT1         "\xE5\xB8\x83\xE5\xB1\x80" "1"
#define TXT_UNIT            "\xE5\x8D\x95\xE4\xBD\x8D\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_METRIC          "\xE5\x85\xAC\xE5\x88\xB6"
#define TXT_FONT_SIZE       "\xE5\xAD\x97\xE4\xBD\x93\xE5\xA4\xA7\xE5\xB0\x8F"
#define TXT_MEDIUM          "\xE4\xB8\xAD\xE5\x8F\xB7"
#define TXT_SLEEP           "\xE6\x81\xAF\xE5\xB1\x8F\xE6\x97\xB6\xE9\x97\xB4"
#define TXT_1_MIN           "1" "\xE5\x88\x86\xE9\x92\x9F"
#define TXT_BT              "\xE8\x93\x9D\xE7\x89\x99\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_WIFI            "Wi-Fi" "\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_AUTO_OFF        "\xE8\x87\xAA\xE5\x8A\xA8\xE5\x85\xB3\xE6\x9C\xBA"
#define TXT_10_MIN          "10" "\xE5\x88\x86\xE9\x92\x9F"
#define TXT_KEY_SOUND       "\xE6\x8C\x89\xE9\x94\xAE\xE9\x9F\xB3"
#define TXT_LANG            "\xE8\xAF\xAD\xE8\xA8\x80\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_CN              "\xE7\xAE\x80\xE4\xBD\x93\xE4\xB8\xAD\xE6\x96\x87"
#define TXT_TIME            "\xE6\x97\xB6\xE9\x97\xB4\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_FACTORY         "\xE6\x81\xA2\xE5\xA4\x8D\xE5\x87\xBA\xE5\x8E\x82\xE8\xAE\xBE\xE7\xBD\xAE"
#define TXT_HR_SENSOR       "\xE5\xBF\x83\xE7\x8E\x87\xE4\xBC\xA0\xE6\x84\x9F\xE5\x99\xA8"
#define TXT_NOT_CONNECTED   "\xE6\x9C\xAA\xE8\xBF\x9E\xE6\x8E\xA5"
#define TXT_SPEED_SENSOR    "\xE9\x80\x9F\xE5\xBA\xA6\xE4\xBC\xA0\xE6\x84\x9F\xE5\x99\xA8"
#define TXT_CADENCE_SENSOR  "\xE8\xB8\x8F\xE9\xA2\x91\xE4\xBC\xA0\xE6\x84\x9F\xE5\x99\xA8"
#define TXT_POWER_METER     "\xE5\x8A\x9F\xE7\x8E\x87\xE8\xAE\xA1"
#define TXT_AUTO_SEARCH     "\xE8\x87\xAA\xE5\x8A\xA8\xE6\x90\x9C\xE7\xB4\xA2"
#define TXT_BACK            "\xE8\xBF\x94\xE5\x9B\x9E"
#define TXT_MENU            "\xE8\x8F\x9C\xE5\x8D\x95"
#define TXT_TOTAL_DIST      "\xE6\x80\xBB\xE9\x87\x8C\xE7\xA8\x8B"
#define TXT_TOTAL_TIME      "\xE6\x80\xBB\xE6\x97\xB6\xE9\x97\xB4"
#define TXT_TOTAL_COUNT     "\xE6\x80\xBB\xE6\xAC\xA1\xE6\x95\xB0"
#define TXT_CUR_ROUTE       "\xE5\xBD\x93\xE5\x89\x8D\xE8\xB7\xAF\xE7\xBA\xBF"
#define TXT_SELECT_ROUTE    "\xE9\x80\x89\xE6\x8B\xA9\xE8\xB7\xAF\xE7\xBA\xBF"
#define TXT_START_NAV       "\xE5\xBC\x80\xE5\xA7\x8B\xE5\xAF\xBC\xE8\x88\xAA"
#define TXT_STOP_NAV        "\xE5\x81\x9C\xE6\xAD\xA2\xE5\xAF\xBC\xE8\x88\xAA"
#define TXT_NO_ROUTE        "\xE6\x97\xA0\xE8\xB7\xAF\xE7\xBA\xBF"
#define TXT_READY           "\xE5\xB7\xB2\xE5\xB0\xB1\xE7\xBB\xAA"
#define TXT_IMPORTING       "\xE5\xAF\xBC\xE5\x85\xA5\xE4\xB8\xAD"
#define TXT_NOT_READY       "\xE6\x9C\xAA\xE5\xB0\xB1\xE7\xBB\xAA"
#define TXT_RUNNING         "\xE5\xAF\xBC\xE8\x88\xAA\xE4\xB8\xAD"

#define MENU_ENCODER_CLICK_MS  250
#define MENU_BACK_CLICK_MS     450
#define MENU_FOCUS_ANIM_MS     160
#define MENU_FOCUS_PAD_X       3
#define MENU_FOCUS_PAD_Y       3
#define MENU_ROW_H             30
#define MENU_ROW_GAP            5
#define MENU_ROW_STEP          (MENU_ROW_H + MENU_ROW_GAP)
#define MENU_LIST_X            12
#define MENU_LIST_Y            61
#define MENU_LIST_W            (LV_HOR_RES - MENU_LIST_X * 2)
#define MENU_VISIBLE_ROWS      6
#define MENU_LIST_H            (MENU_ROW_H * MENU_VISIBLE_ROWS + MENU_ROW_GAP * (MENU_VISIBLE_ROWS - 1))
#define MENU_ACTION_NONE      -1
#define MENU_CONFIRM_DUP_MS   60

namespace
{
    struct MenuItem
    {
        const char* icon;
        const char* text;
        int action;
    };

    const MenuItem kMenuItems[] =
    {
        { ICON_DETAIL,     TXT_DEVICE,  MENU_ACTION_DEVICE  },
        { ICON_RECORD,     TXT_RECORDS, MENU_ACTION_RECORDS },
        { ICON_NAV,        TXT_NAV,     MENU_ACTION_NAV     },
        { ICON_BRIGHTNESS, TXT_DISPLAY, MENU_ACTION_DISPLAY },
        { ICON_SENSOR,     TXT_SENSOR,  MENU_ACTION_SENSOR  },
        { ICON_SETTING,    TXT_SYSTEM,  MENU_ACTION_SYSTEM  },
        { ICON_DETAIL,     TXT_ABOUT,   MENU_ACTION_ABOUT   },
    };

    const SettingItem kDisplayItems[] =
    {
        { TXT_BRIGHTNESS,  "",            false, false, SETTING_ACTION_NONE },
        { TXT_AUTO_BRIGHT, TXT_ON,        true,  true,  SETTING_ACTION_NONE },
        { TXT_THEME,       TXT_TECH_BLUE, false, false, SETTING_ACTION_NONE },
        { TXT_DASH_LAYOUT, TXT_LAYOUT1,   false, false, SETTING_ACTION_NONE },
        { TXT_UNIT,        TXT_METRIC,    false, false, SETTING_ACTION_NONE },
        { TXT_FONT_SIZE,   TXT_MEDIUM,    false, false, SETTING_ACTION_NONE },
        { TXT_SLEEP,       TXT_1_MIN,     false, false, SETTING_ACTION_NONE },
    };

    const SettingItem kSystemItems[] =
    {
        { TXT_BT,        "",         false, false, SETTING_ACTION_NONE },
        { TXT_WIFI,      "",         false, false, SETTING_ACTION_NONE },
        { TXT_AUTO_OFF,  TXT_10_MIN, false, false, SETTING_ACTION_NONE },
        { TXT_KEY_SOUND, TXT_ON,     true,  true,  SETTING_ACTION_NONE },
        { TXT_LANG,      TXT_CN,     false, false, SETTING_ACTION_NONE },
        { TXT_TIME,      "16:32:45", false, false, SETTING_ACTION_NONE },
        { TXT_FACTORY,   "",         false, false, SETTING_ACTION_NONE },
    };

    const SettingItem kSensorItems[] =
    {
        { TXT_HR_SENSOR,      TXT_NOT_CONNECTED, false, false, SETTING_ACTION_NONE },
        { TXT_SPEED_SENSOR,   TXT_NOT_CONNECTED, false, false, SETTING_ACTION_NONE },
        { TXT_CADENCE_SENSOR, TXT_NOT_CONNECTED, false, false, SETTING_ACTION_NONE },
        { TXT_POWER_METER,    TXT_NOT_CONNECTED, false, false, SETTING_ACTION_NONE },
        { TXT_AUTO_SEARCH,    TXT_ON,            true,  true,  SETTING_ACTION_NONE },
    };

    lv_font_t* FontCn()
    {
        return ResourcePool::GetFont("cn_16");
    }

    lv_font_t* FontIcon()
    {
        return ResourcePool::GetFont("iconfont_20");
    }

    lv_font_t* FontNum()
    {
        return ResourcePool::GetFont("bahnschrift_13");
    }

    void SetStatusBarAppear(bool en)
    {
        DataProc::StatusBar_Info_t info;
        DATA_PROC_INIT_STRUCT(info);
        info.cmd = DataProc::STATUS_BAR_CMD_APPEAR;
        info.param.appear = en;
        DataProc::Center()->AccountMain.Notify("StatusBar", &info, sizeof(info));
    }

    void SetStatusBarStyle(DataProc::StatusBar_Style_t style)
    {
        DataProc::StatusBar_Info_t info;
        DATA_PROC_INIT_STRUCT(info);
        info.cmd = DataProc::STATUS_BAR_CMD_SET_STYLE;
        info.param.style = style;
        DataProc::Center()->AccountMain.Notify("StatusBar", &info, sizeof(info));
    }

    void ApplyFocusStyle(lv_obj_t* row)
    {
        lv_obj_set_style_bg_color(row, lv_color_hex(0x07333b), LV_STATE_FOCUSED);
        lv_obj_set_style_bg_opa(row, LV_OPA_90, LV_STATE_FOCUSED);
        lv_obj_set_style_border_color(row, lv_color_hex(0x00eaff), LV_STATE_FOCUSED);
        lv_obj_set_style_shadow_width(row, 4, LV_STATE_FOCUSED);
        lv_obj_set_style_shadow_color(row, lv_color_hex(0x00eaff), LV_STATE_FOCUSED);
        lv_obj_set_style_shadow_opa(row, LV_OPA_30, LV_STATE_FOCUSED);

        static lv_style_transition_dsc_t trans;
        static const lv_style_prop_t props[] =
        {
            LV_STYLE_BG_COLOR,
            LV_STYLE_BG_OPA,
            LV_STYLE_BORDER_COLOR,
            LV_STYLE_SHADOW_WIDTH,
            LV_STYLE_SHADOW_OPA,
            LV_STYLE_PROP_INV
        };
        static bool transInited = false;
        if (!transInited)
        {
            lv_style_transition_dsc_init(
                &trans,
                props,
                lv_anim_path_ease_out,
                MENU_FOCUS_ANIM_MS,
                0,
                nullptr
            );
            transInited = true;
        }
        lv_obj_set_style_transition(row, &trans, 0);
        lv_obj_set_style_transition(row, &trans, LV_STATE_FOCUSED);
    }

    bool IsEncoderEvent()
    {
        lv_indev_t* indev = lv_indev_get_act();
        if (indev == nullptr)
        {
            return false;
        }

        lv_indev_type_t type = lv_indev_get_type(indev);
        return type == LV_INDEV_TYPE_ENCODER || type == LV_INDEV_TYPE_KEYPAD;
    }

    void FocusHaloYAnimCb(void* obj, int32_t y)
    {
        lv_obj_set_y((lv_obj_t*)obj, (lv_coord_t)y);
    }

    void ClearFocusState(lv_obj_t* obj)
    {
        if (obj == nullptr)
        {
            return;
        }

        lv_obj_clear_state(obj, (lv_state_t)(LV_STATE_FOCUSED | LV_STATE_EDITED | LV_STATE_FOCUS_KEY));
    }
}

MainMenu::MainMenu()
    : encoderClickTimer(nullptr),
      currentScreen(SCREEN_MAIN),
      focusItemCount(0),
      encoderPendingAction(MENU_ACTION_NONE),
      encoderPendingSettingAction(false),
      navigationPageActive(false),
      encoderShortClickTick(0),
      backRequestPending(false),
      backButton(nullptr),
      listCont(nullptr),
      focusHalo(nullptr),
      encoderShortClickObj(nullptr)
{
    memset(itemButtons, 0, sizeof(itemButtons));
    memset(focusItems, 0, sizeof(focusItems));
    memset(settingActions, 0, sizeof(settingActions));
}

MainMenu::~MainMenu()
{
}

void MainMenu::onCustomAttrConfig()
{
    SetCustomLoadAnimType(PageManager::LOAD_ANIM_OVER_LEFT);
}

void MainMenu::onViewLoad()
{
    ShowMainMenu();
    AttachEvent(_root);
}

void MainMenu::onViewDidLoad()
{
}

void MainMenu::onViewWillAppear()
{
    backRequestPending = false;
    SetStatusBarStyle(DataProc::STATUS_BAR_STYLE_BLACK);
    SetStatusBarAppear(true);
    if (currentScreen == SCREEN_SUBPAGE && navigationPageActive)
    {
        ShowNavigationPage();
        return;
    }
    RefreshEncoderGroup();
}

void MainMenu::onViewDidAppear()
{
}

void MainMenu::onViewWillDisappear()
{
    backRequestPending = false;
    CancelEncoderClick();
    ClearEncoderGroup();
    SetStatusBarAppear(true);
}

void MainMenu::onViewDidDisappear()
{
}

void MainMenu::onViewUnload()
{
    backRequestPending = false;
    CancelEncoderClick();
    ClearEncoderGroup();
    focusHalo = nullptr;
    listCont = nullptr;
    backButton = nullptr;
    memset(itemButtons, 0, sizeof(itemButtons));
    memset(focusItems, 0, sizeof(focusItems));
    memset(settingActions, 0, sizeof(settingActions));
    focusItemCount = 0;
}

void MainMenu::onViewDidUnload()
{
}

void MainMenu::home_screen_cleanup()
{
}

void MainMenu::AttachEvent(lv_obj_t* obj)
{
    lv_obj_add_event_cb(obj, onEvent, LV_EVENT_ALL, this);
}

void MainMenu::CreateBase(const char* title)
{
    CancelEncoderClick();
    ClearEncoderGroup();
    lv_obj_clean(_root);
    focusHalo = nullptr;
    listCont = nullptr;
    backButton = nullptr;
    lv_obj_remove_style_all(_root);
    lv_obj_set_pos(_root, 0, 0);
    lv_obj_set_size(_root, LV_HOR_RES, LV_VER_RES);
    lv_obj_set_style_bg_color(_root, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(_root, LV_OPA_COVER, 0);
    lv_obj_clear_flag(_root, LV_OBJ_FLAG_SCROLLABLE);

    memset(itemButtons, 0, sizeof(itemButtons));
    memset(focusItems, 0, sizeof(focusItems));
    focusItemCount = 0;

    CreateFocusHalo();

    lv_obj_t* titleLabel = lv_label_create(_root);
    lv_obj_set_style_text_font(titleLabel, FontCn(), 0);
    lv_obj_set_style_text_color(titleLabel, lv_color_white(), 0);
    lv_label_set_text(titleLabel, title);
    lv_obj_align(titleLabel, LV_ALIGN_TOP_MID, 0, 30);

    listCont = lv_obj_create(_root);
    lv_obj_remove_style_all(listCont);
    lv_obj_set_pos(listCont, MENU_LIST_X, MENU_LIST_Y);
    lv_obj_set_size(listCont, MENU_LIST_W, MENU_LIST_H);
    lv_obj_set_style_bg_opa(listCont, LV_OPA_TRANSP, 0);
    lv_obj_set_scroll_dir(listCont, LV_DIR_VER);
    lv_obj_set_scrollbar_mode(listCont, LV_SCROLLBAR_MODE_OFF);
    lv_obj_add_flag(listCont, LV_OBJ_FLAG_SCROLLABLE);
    AttachEvent(listCont);

    CreateFooter();
}

void MainMenu::CreateFooter()
{
    backButton = lv_obj_create(_root);
    lv_obj_remove_style_all(backButton);
    lv_obj_set_pos(backButton, 7, LV_VER_RES - 31);
    lv_obj_set_size(backButton, 70, 24);
    lv_obj_set_style_bg_color(backButton, lv_color_hex(0x031318), 0);
    lv_obj_set_style_bg_opa(backButton, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(backButton, 1, 0);
    lv_obj_set_style_border_color(backButton, lv_color_hex(0x00dfff), 0);
    lv_obj_set_style_radius(backButton, 4, 0);
    lv_obj_clear_flag(backButton, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(backButton, LV_OBJ_FLAG_CLICKABLE);
    AttachEvent(backButton);

    lv_obj_t* iconLabel = lv_label_create(backButton);
    lv_obj_set_style_text_font(iconLabel, FontIcon(), 0);
    lv_obj_set_style_text_color(iconLabel, lv_color_hex(0x00eaff), 0);
    lv_label_set_text(iconLabel, ICON_BACK);
    lv_obj_align(iconLabel, LV_ALIGN_LEFT_MID, 7, 0);

    lv_obj_t* textLabel = lv_label_create(backButton);
    lv_obj_set_style_text_font(textLabel, FontCn(), 0);
    lv_obj_set_style_text_color(textLabel, lv_color_hex(0x00eaff), 0);
    lv_label_set_text(textLabel, TXT_BACK);
    lv_obj_align(textLabel, LV_ALIGN_LEFT_MID, 31, 0);
}

void MainMenu::CreateFocusHalo()
{
    focusHalo = lv_obj_create(_root);
    if (focusHalo == nullptr)
    {
        return;
    }

    lv_obj_remove_style_all(focusHalo);
    lv_obj_set_size(focusHalo, 10, 10);
    lv_obj_add_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(focusHalo, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(focusHalo, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_set_style_bg_color(focusHalo, lv_color_hex(0x00eaff), 0);
    lv_obj_set_style_bg_opa(focusHalo, LV_OPA_20, 0);
    lv_obj_set_style_border_width(focusHalo, 2, 0);
    lv_obj_set_style_border_color(focusHalo, lv_color_hex(0x00f2ff), 0);
    lv_obj_set_style_border_opa(focusHalo, LV_OPA_COVER, 0);
    lv_obj_set_style_shadow_width(focusHalo, 14, 0);
    lv_obj_set_style_shadow_color(focusHalo, lv_color_hex(0x00eaff), 0);
    lv_obj_set_style_shadow_opa(focusHalo, LV_OPA_60, 0);
    lv_obj_set_style_radius(focusHalo, 6, 0);
}

lv_obj_t* MainMenu::CreateMenuRow(lv_coord_t y, const char* icon, const char* text, int action)
{
    lv_obj_t* parent = listCont ? listCont : _root;
    lv_obj_t* row = lv_obj_create(parent);
    lv_obj_remove_style_all(row);
    lv_obj_set_pos(row, 5, y);
    lv_obj_set_size(row, MENU_LIST_W - 10, MENU_ROW_H);
    lv_obj_set_style_bg_color(row, lv_color_hex(0x031419), 0);
    lv_obj_set_style_bg_opa(row, LV_OPA_80, 0);
    lv_obj_set_style_border_width(row, 1, 0);
    lv_obj_set_style_border_color(row, lv_color_hex(0x008aa0), 0);
    lv_obj_set_style_radius(row, 4, 0);
    lv_obj_clear_flag(row, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(row, LV_OBJ_FLAG_CLICKABLE);
    ApplyFocusStyle(row);
    AttachEvent(row);

    lv_obj_t* iconLabel = lv_label_create(row);
    lv_obj_set_style_text_font(iconLabel, FontIcon(), 0);
    lv_obj_set_style_text_color(iconLabel, lv_color_hex(0x00eaff), 0);
    lv_label_set_text(iconLabel, icon);
    lv_obj_align(iconLabel, LV_ALIGN_LEFT_MID, 20, 0);

    lv_obj_t* textLabel = lv_label_create(row);
    lv_obj_set_style_text_font(textLabel, FontCn(), 0);
    lv_obj_set_style_text_color(textLabel, lv_color_white(), 0);
    lv_label_set_text(textLabel, text);
    lv_obj_align(textLabel, LV_ALIGN_LEFT_MID, 56, 0);

    lv_obj_t* arrow = lv_label_create(row);
    lv_obj_set_style_text_font(arrow, LV_FONT_DEFAULT, 0);
    lv_obj_set_style_text_color(arrow, lv_color_white(), 0);
    lv_label_set_text(arrow, LV_SYMBOL_RIGHT);
    lv_obj_align(arrow, LV_ALIGN_RIGHT_MID, -12, 0);

    if (action >= 0 && action < MENU_ITEM_COUNT)
    {
        itemButtons[action] = row;
    }
    RegisterFocusItem(row);
    return row;
}

void MainMenu::ShowMainMenu()
{
    currentScreen = SCREEN_MAIN;
    navigationPageActive = false;
    CreateBase(TXT_MENU);

    for (int i = 0; i < MENU_ITEM_COUNT; i++)
    {
        CreateMenuRow(i * MENU_ROW_STEP, kMenuItems[i].icon, kMenuItems[i].text, kMenuItems[i].action);
    }

    RefreshEncoderGroup();
}

void MainMenu::CreateSettingRow(lv_coord_t y, const SettingItem& item)
{
    lv_obj_t* parent = listCont ? listCont : _root;
    lv_obj_t* row = lv_obj_create(parent);
    lv_obj_remove_style_all(row);
    lv_obj_set_pos(row, 5, y);
    lv_obj_set_size(row, MENU_LIST_W - 10, MENU_ROW_H);
    lv_obj_set_style_bg_color(row, lv_color_hex(0x031419), 0);
    lv_obj_set_style_bg_opa(row, LV_OPA_70, 0);
    lv_obj_set_style_border_width(row, 1, 0);
    lv_obj_set_style_border_color(row, lv_color_hex(0x006f80), 0);
    lv_obj_set_style_radius(row, 4, 0);
    lv_obj_clear_flag(row, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(row, LV_OBJ_FLAG_CLICKABLE);
    ApplyFocusStyle(row);
    AttachEvent(row);
    RegisterFocusItem(row);
    if (focusItemCount > 0)
    {
        settingActions[focusItemCount - 1] = item.action;
    }

    lv_obj_t* name = lv_label_create(row);
    lv_obj_set_style_text_font(name, FontCn(), 0);
    lv_obj_set_style_text_color(name, lv_color_white(), 0);
    lv_label_set_text(name, item.name);
    lv_obj_align(name, LV_ALIGN_LEFT_MID, 8, 0);

    if (item.toggle)
    {
        lv_obj_t* sw = lv_switch_create(row);
        lv_obj_set_size(sw, 28, 14);
        lv_obj_align(sw, LV_ALIGN_RIGHT_MID, -8, 0);
        if (item.on)
        {
            lv_obj_add_state(sw, LV_STATE_CHECKED);
        }
        lv_obj_clear_flag(sw, LV_OBJ_FLAG_CLICKABLE);
    }
    else
    {
        if (item.value && item.value[0] != '\0')
        {
            lv_obj_t* value = lv_label_create(row);
            lv_obj_set_style_text_font(value, FontCn(), 0);
            lv_obj_set_style_text_color(value, lv_color_hex(0x00eaff), 0);
            lv_label_set_text(value, item.value);
            lv_obj_align(value, LV_ALIGN_RIGHT_MID, -22, 0);
        }

        lv_obj_t* arrow = lv_label_create(row);
        lv_obj_set_style_text_font(arrow, LV_FONT_DEFAULT, 0);
        lv_obj_set_style_text_color(arrow, lv_color_white(), 0);
        lv_label_set_text(arrow, LV_SYMBOL_RIGHT);
        lv_obj_align(arrow, LV_ALIGN_RIGHT_MID, -7, 0);
    }
}

void MainMenu::ShowSettingsPage(const char* title, const SettingItem* items, int count)
{
    currentScreen = SCREEN_SUBPAGE;
    navigationPageActive = false;
    CreateBase(title);

    for (int i = 0; i < count; i++)
    {
        CreateSettingRow(i * MENU_ROW_STEP, items[i]);
    }

    RefreshEncoderGroup();
}

static const char* NavStatusText(const DataProc::Navigation_Info_t* info)
{
    if (info->active)
    {
        return TXT_RUNNING;
    }

    switch (info->routeStatus)
    {
    case DataProc::NAV_ROUTE_STATUS_NO_ROUTE:
        return TXT_NO_ROUTE;
    case DataProc::NAV_ROUTE_STATUS_VALID:
        return TXT_READY;
    case DataProc::NAV_ROUTE_STATUS_IMPORTING:
    case DataProc::NAV_ROUTE_STATUS_VALIDATING:
        return TXT_IMPORTING;
    default:
        return TXT_NOT_READY;
    }
}

void MainMenu::ShowNavigationPage()
{
    currentScreen = SCREEN_SUBPAGE;
    navigationPageActive = true;
    CreateBase(TXT_NAV);

    DataProc::Navigation_Info_t nav;
    DATA_PROC_INIT_STRUCT(nav);
    DataProc::Center()->AccountMain.Pull("Navigation", &nav, sizeof(nav));

    const char* routeValue = nav.routeName[0] ? nav.routeName : NavStatusText(&nav);
    SettingItem items[] =
    {
        { TXT_CUR_ROUTE,    routeValue, false, false, SETTING_ACTION_NONE },
        { TXT_SELECT_ROUTE, "",         false, false, SETTING_ACTION_ROUTE_SELECT },
        { nav.active ? TXT_STOP_NAV : TXT_START_NAV, NavStatusText(&nav), false, false, SETTING_ACTION_NAV_TOGGLE },
    };

    for (int i = 0; i < (int)(sizeof(items) / sizeof(items[0])); i++)
    {
        CreateSettingRow(i * MENU_ROW_STEP, items[i]);
    }

    RefreshEncoderGroup();
}

void MainMenu::ShowRecordsPage()
{
    currentScreen = SCREEN_SUBPAGE;
    navigationPageActive = false;
    CreateBase(TXT_RECORDS);

    const char* rows[][4] =
    {
        { "2024-04-18  08:15", "32.6 KM", "01:28:34", "22.1 KM/H" },
        { "2024-04-17  17:45", "45.3 KM", "02:15:20", "20.1 KM/H" },
        { "2024-04-16  07:30", "28.7 KM", "01:10:05", "24.6 KM/H" },
        { "2024-04-15  18:20", "38.9 KM", "01:45:42", "22.1 KM/H" },
    };

    for (int i = 0; i < 4; i++)
    {
        lv_obj_t* row = lv_obj_create(listCont ? listCont : _root);
        lv_obj_remove_style_all(row);
        lv_obj_set_pos(row, 5, i * 47);
        lv_obj_set_size(row, MENU_LIST_W - 10, 40);
        lv_obj_set_style_bg_color(row, lv_color_hex(0x031419), 0);
        lv_obj_set_style_bg_opa(row, LV_OPA_70, 0);
        lv_obj_set_style_border_width(row, 1, 0);
        lv_obj_set_style_border_color(row, lv_color_hex(0x007f90), 0);
        lv_obj_set_style_radius(row, 4, 0);
        lv_obj_clear_flag(row, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_add_flag(row, LV_OBJ_FLAG_CLICKABLE);
        ApplyFocusStyle(row);
        AttachEvent(row);
        RegisterFocusItem(row);

        lv_obj_t* date = lv_label_create(row);
        lv_obj_set_style_text_font(date, FontNum(), 0);
        lv_obj_set_style_text_color(date, lv_color_hex(0x00eaff), 0);
        lv_label_set_text(date, rows[i][0]);
        lv_obj_align(date, LV_ALIGN_TOP_LEFT, 8, 4);

        for (int j = 0; j < 3; j++)
        {
            lv_obj_t* value = lv_label_create(row);
            lv_obj_set_style_text_font(value, FontNum(), 0);
            lv_obj_set_style_text_color(value, lv_color_white(), 0);
            lv_label_set_text(value, rows[i][j + 1]);
            lv_obj_align(value, LV_ALIGN_BOTTOM_LEFT, 9 + j * 67, -5);
        }
    }

    lv_obj_t* summary = lv_obj_create(listCont ? listCont : _root);
    lv_obj_remove_style_all(summary);
    lv_obj_set_pos(summary, 5, 4 * 47);
    lv_obj_set_size(summary, MENU_LIST_W - 10, 42);
    lv_obj_set_style_bg_color(summary, lv_color_hex(0x031419), 0);
    lv_obj_set_style_bg_opa(summary, LV_OPA_70, 0);
    lv_obj_set_style_border_width(summary, 1, 0);
    lv_obj_set_style_border_color(summary, lv_color_hex(0x007f90), 0);
    lv_obj_set_style_radius(summary, 4, 0);
    lv_obj_clear_flag(summary, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(summary, LV_OBJ_FLAG_CLICKABLE);
    ApplyFocusStyle(summary);
    AttachEvent(summary);
    RegisterFocusItem(summary);

    const char* names[] = { TXT_TOTAL_DIST, TXT_TOTAL_TIME, TXT_TOTAL_COUNT };
    const char* vals[] = { "1234 KM", "56:32:10", "48" };
    for (int i = 0; i < 3; i++)
    {
        lv_obj_t* name = lv_label_create(summary);
        lv_obj_set_style_text_font(name, FontCn(), 0);
        lv_obj_set_style_text_color(name, lv_color_hex(0x00eaff), 0);
        lv_label_set_text(name, names[i]);
        lv_obj_align(name, LV_ALIGN_TOP_LEFT, 12 + i * 64, 5);

        lv_obj_t* value = lv_label_create(summary);
        lv_obj_set_style_text_font(value, FontNum(), 0);
        lv_obj_set_style_text_color(value, lv_color_white(), 0);
        lv_label_set_text(value, vals[i]);
        lv_obj_align(value, LV_ALIGN_BOTTOM_LEFT, 10 + i * 65, -5);
    }

    RefreshEncoderGroup();
}

void MainMenu::OpenAction(int action)
{
    switch (action)
    {
    case MENU_ACTION_DEVICE:
    case MENU_ACTION_ABOUT:
        SetStatusBarAppear(true);
        _Manager->Push("Pages/SystemInfos");
        break;
    case MENU_ACTION_RECORDS:
        ShowRecordsPage();
        break;
    case MENU_ACTION_NAV:
        ShowNavigationPage();
        break;
    case MENU_ACTION_DISPLAY:
        ShowSettingsPage(TXT_DISPLAY, kDisplayItems, sizeof(kDisplayItems) / sizeof(kDisplayItems[0]));
        break;
    case MENU_ACTION_SENSOR:
        ShowSettingsPage(TXT_SENSOR, kSensorItems, sizeof(kSensorItems) / sizeof(kSensorItems[0]));
        break;
    case MENU_ACTION_SYSTEM:
        ShowSettingsPage(TXT_SYSTEM, kSystemItems, sizeof(kSystemItems) / sizeof(kSystemItems[0]));
        break;
    default:
        break;
    }
}

void MainMenu::OpenSettingAction(int action)
{
    switch (action)
    {
    case SETTING_ACTION_ROUTE_SELECT:
        _Manager->Push("Pages/RouteSelect");
        break;
    case SETTING_ACTION_NAV_TOGGLE:
    {
        DataProc::Navigation_Info_t nav;
        DATA_PROC_INIT_STRUCT(nav);
        DataProc::Center()->AccountMain.Pull("Navigation", &nav, sizeof(nav));

        if (!nav.active)
        {
            if (nav.routeStatus != DataProc::NAV_ROUTE_STATUS_VALID || nav.pointCount < 2)
            {
                ShowNavigationPage();
                break;
            }
        }

        DataProc::Navigation_CmdInfo_t cmd;
        DATA_PROC_INIT_STRUCT(cmd);
        cmd.cmd = nav.active ? DataProc::NAV_CMD_STOP : DataProc::NAV_CMD_START;
        DataProc::Center()->AccountMain.Notify("Navigation", &cmd, sizeof(cmd));
        ShowNavigationPage();
        break;
    }
    default:
        break;
    }
}

void MainMenu::OnBack()
{
    if (currentScreen == SCREEN_MAIN)
    {
        _Manager->Pop();
    }
    else
    {
        ShowMainMenu();
    }
}

void MainMenu::RequestBack()
{
    if (backRequestPending)
    {
        return;
    }

    backRequestPending = true;
    lv_async_call(onBackAsync, this);
}

void MainMenu::RegisterFocusItem(lv_obj_t* obj)
{
    if (obj == nullptr || focusItemCount >= MENU_FOCUS_ITEM_MAX)
    {
        return;
    }

    focusItems[focusItemCount] = obj;
    settingActions[focusItemCount] = SETTING_ACTION_NONE;
    focusItemCount++;
}

bool MainMenu::IsFocusItem(lv_obj_t* obj)
{
    if (obj == nullptr)
    {
        return false;
    }

    for (int i = 0; i < focusItemCount; i++)
    {
        if (focusItems[i] == obj)
        {
            return true;
        }
    }

    return false;
}

void MainMenu::RefreshEncoderGroup()
{
    lv_group_t* group = lv_group_get_default();
    if (group == nullptr)
    {
        return;
    }

    lv_group_remove_all_objs(group);
    lv_group_set_focus_cb(group, nullptr);
    lv_group_set_wrap(group, true);
    lv_group_set_editing(group, false);

    for (int i = 0; i < focusItemCount; i++)
    {
        if (focusItems[i] != nullptr)
        {
            lv_group_add_obj(group, focusItems[i]);
        }
    }

    if (focusItemCount > 0 && focusItems[0] != nullptr)
    {
        MoveFocusHaloTo(focusItems[0], false);
        lv_group_focus_obj(focusItems[0]);
    }
}

void MainMenu::ClearEncoderGroup()
{
    lv_group_t* group = lv_group_get_default();
    if (group != nullptr)
    {
        lv_group_set_focus_cb(group, nullptr);
        lv_group_set_editing(group, false);

        for (int i = 0; i < focusItemCount; i++)
        {
            if (focusItems[i] != nullptr)
            {
                if (lv_obj_get_group(focusItems[i]) == group)
                {
                    lv_group_remove_obj(focusItems[i]);
                }
                ClearFocusState(focusItems[i]);
            }
        }
    }

    if (focusHalo != nullptr)
    {
        lv_anim_del(focusHalo, FocusHaloYAnimCb);
        lv_obj_add_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);
    }
}

void MainMenu::CancelEncoderClick()
{
    if (encoderClickTimer != nullptr)
    {
        lv_timer_del(encoderClickTimer);
        encoderClickTimer = nullptr;
    }

    encoderPendingAction = MENU_ACTION_NONE;
    encoderPendingSettingAction = false;
    encoderShortClickTick = 0;
    encoderShortClickObj = nullptr;
}

void MainMenu::HandleEncoderClick(int action, bool settingAction)
{
    if (encoderClickTimer != nullptr)
    {
        CancelEncoderClick();
        RequestBack();
        return;
    }

    encoderPendingAction = action;
    encoderPendingSettingAction = settingAction;
    uint32_t clickMs = (currentScreen == SCREEN_SUBPAGE && action == MENU_ACTION_NONE) ?
                       MENU_BACK_CLICK_MS : MENU_ENCODER_CLICK_MS;
    encoderClickTimer = lv_timer_create(onEncoderClickTimer, clickMs, this);
    if (encoderClickTimer != nullptr)
    {
        lv_timer_set_repeat_count(encoderClickTimer, 1);
    }
    else
    {
        CommitEncoderClick();
    }
}

void MainMenu::CommitEncoderClick()
{
    int action = encoderPendingAction;
    bool settingAction = encoderPendingSettingAction;

    encoderClickTimer = nullptr;
    encoderPendingAction = MENU_ACTION_NONE;
    encoderPendingSettingAction = false;

    if (settingAction)
    {
        OpenSettingAction(action);
    }
    else if (action != MENU_ACTION_NONE)
    {
        OpenAction(action);
    }
}

int MainMenu::FindActionByObj(lv_obj_t* obj)
{
    for (int i = 0; i < MENU_ITEM_COUNT; i++)
    {
        if (obj == itemButtons[i])
        {
            return i;
        }
    }

    return MENU_ACTION_NONE;
}

int MainMenu::FindSettingActionByObj(lv_obj_t* obj)
{
    for (int i = 0; i < focusItemCount; i++)
    {
        if (focusItems[i] == obj)
        {
            return settingActions[i];
        }
    }
    return SETTING_ACTION_NONE;
}

void MainMenu::MoveFocusHaloTo(lv_obj_t* obj, bool anim)
{
    if (focusHalo == nullptr || obj == nullptr)
    {
        return;
    }

    lv_obj_scroll_to_view(obj, LV_ANIM_OFF);
    lv_obj_move_foreground(focusHalo);

    lv_area_t objArea;
    lv_area_t rootArea;
    lv_obj_get_coords(obj, &objArea);
    lv_obj_get_coords(_root, &rootArea);

    lv_coord_t x = objArea.x1 - rootArea.x1 - MENU_FOCUS_PAD_X;
    lv_coord_t y = objArea.y1 - rootArea.y1 - MENU_FOCUS_PAD_Y;
    lv_coord_t w = lv_obj_get_width(obj) + MENU_FOCUS_PAD_X * 2;
    lv_coord_t h = lv_obj_get_height(obj) + MENU_FOCUS_PAD_Y * 2;
    bool wasHidden = lv_obj_has_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);

    lv_obj_clear_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);
    lv_obj_set_x(focusHalo, x);
    lv_obj_set_size(focusHalo, w, h);

    lv_anim_del(focusHalo, FocusHaloYAnimCb);
    if (anim && !wasHidden)
    {
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, focusHalo);
        lv_anim_set_exec_cb(&a, FocusHaloYAnimCb);
        lv_anim_set_values(&a, lv_obj_get_y(focusHalo), y);
        lv_anim_set_time(&a, MENU_FOCUS_ANIM_MS);
        lv_anim_set_path_cb(&a, lv_anim_path_ease_out);
        lv_anim_start(&a);
    }
    else
    {
        lv_obj_set_y(focusHalo, y);
    }
}

void MainMenu::onEncoderClickTimer(lv_timer_t* timer)
{
    MainMenu* instance = (MainMenu*)timer->user_data;
    if (instance != nullptr)
    {
        instance->CommitEncoderClick();
    }
}

void MainMenu::onBackAsync(void* userData)
{
    MainMenu* instance = (MainMenu*)userData;
    if (instance == nullptr)
    {
        return;
    }

    instance->backRequestPending = false;
    instance->OnBack();
}

void MainMenu::onEvent(lv_event_t* event)
{
    MainMenu* instance = (MainMenu*)lv_event_get_user_data(event);
    LV_ASSERT_NULL(instance);

    lv_obj_t* obj = lv_event_get_current_target(event);
    lv_event_code_t code = lv_event_get_code(event);

    if (code == LV_EVENT_FOCUSED)
    {
        if (instance->IsFocusItem(obj))
        {
            instance->MoveFocusHaloTo(obj, true);
        }
        else
        {
            ClearFocusState(obj);
        }
        return;
    }

    if (code == LV_EVENT_LEAVE)
    {
        instance->RequestBack();
        return;
    }

    if (code == LV_EVENT_GESTURE)
    {
        lv_indev_t* indev = lv_indev_get_act();
        lv_dir_t dir = lv_indev_get_gesture_dir(indev);
        if (dir == LV_DIR_LEFT || dir == LV_DIR_RIGHT)
        {
            instance->RequestBack();
        }
        return;
    }

    if (IsEncoderEvent())
    {
        if (code == LV_EVENT_SHORT_CLICKED || code == LV_EVENT_CLICKED)
        {
            if (code == LV_EVENT_CLICKED &&
                instance->encoderShortClickObj == obj &&
                lv_tick_elaps(instance->encoderShortClickTick) <= MENU_CONFIRM_DUP_MS)
            {
                instance->encoderShortClickObj = nullptr;
                instance->encoderShortClickTick = 0;
                return;
            }

            if (code == LV_EVENT_SHORT_CLICKED)
            {
                instance->encoderShortClickObj = obj;
                instance->encoderShortClickTick = lv_tick_get();
            }

            int action = instance->FindActionByObj(obj);
            if (instance->currentScreen == SCREEN_SUBPAGE)
            {
                int settingAction = instance->FindSettingActionByObj(obj);
                if (settingAction != SETTING_ACTION_NONE)
                {
                    instance->HandleEncoderClick(settingAction, true);
                }
                else if (instance->IsFocusItem(obj))
                {
                    instance->HandleEncoderClick(MENU_ACTION_NONE, false);
                }
            }
            else if (action != MENU_ACTION_NONE || instance->IsFocusItem(obj))
            {
                instance->HandleEncoderClick(action);
            }
        }
        return;
    }

    if (code != LV_EVENT_SHORT_CLICKED && code != LV_EVENT_CLICKED)
    {
        return;
    }

    if (obj == instance->_root || obj == instance->listCont || obj == instance->focusHalo)
    {
        return;
    }

    if (obj == instance->backButton)
    {
        instance->RequestBack();
        return;
    }

    for (int i = 0; i < MENU_ITEM_COUNT; i++)
    {
        if (obj == instance->itemButtons[i])
        {
            instance->OpenAction(i);
            return;
        }
    }

    if (instance->currentScreen == SCREEN_SUBPAGE && instance->IsFocusItem(obj))
    {
        int settingAction = instance->FindSettingActionByObj(obj);
        if (settingAction != SETTING_ACTION_NONE)
        {
            instance->OpenSettingAction(settingAction);
        }
        return;
    }
}
