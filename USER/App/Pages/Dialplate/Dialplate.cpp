#include "Dialplate.h"
#include <stdio.h>
#include <string.h>

using namespace Page;

#define REC_LONG_PRESS_MS      900
#define TURN_COURSE_THRESHOLD  4.0f
#define MAX_SPEED_TEXT_W       50

#define TXT_NAV_APPROACH    "\xE5\x89\x8D\xE5\xBE\x80\xE8\xB7\xAF\xE7\xBA\xBF"
#define TXT_NAV_OFF_ROUTE   "\xE5\x81\x8F\xE7\xA6\xBB\xE8\xB7\xAF\xE7\xBA\xBF"
#define TXT_NAV_REVERSE     "\xE6\x96\xB9\xE5\x90\x91\xE7\x9B\xB8\xE5\x8F\x8D"
#define TXT_NAV_FINISH      "\xE5\x88\xB0\xE8\xBE\xBE\xE7\xBB\x88\xE7\x82\xB9"
#define TXT_NAV_LEFT        "\xE5\xB7\xA6\xE8\xBD\xAC"
#define TXT_NAV_RIGHT       "\xE5\x8F\xB3\xE8\xBD\xAC"
#define TXT_NAV_SHARP_LEFT  "\xE6\x80\xA5\xE5\xB7\xA6\xE8\xBD\xAC"
#define TXT_NAV_SHARP_RIGHT "\xE6\x80\xA5\xE5\x8F\xB3\xE8\xBD\xAC"
#define TXT_NAV_STRAIGHT    "\xE7\x9B\xB4\xE8\xA1\x8C"

static void ClearFocusState(lv_obj_t* obj)
{
    if (obj == nullptr)
    {
        return;
    }

    lv_obj_clear_state(obj, (lv_state_t)(LV_STATE_FOCUSED | LV_STATE_EDITED | LV_STATE_FOCUS_KEY));
}

static float NormalizeCourseDiff(float diff)
{
    while (diff > 180.0f) diff -= 360.0f;
    while (diff < -180.0f) diff += 360.0f;
    return diff;
}

static void SetSpeedLabel(lv_obj_t* label, float speed)
{
    if (label == nullptr)
    {
        return;
    }

    char text[16];
    snprintf(text, sizeof(text), "%0.1f", speed);

    float absSpeed = speed < 0.0f ? -speed : speed;
    const char* fontName = "bahnschrift_48";
    lv_coord_t y = 91;

    if (absSpeed >= 100.0f || strlen(text) > 4)
    {
        fontName = "bahnschrift_24";
        y = 108;
    }
    else if (absSpeed >= 10.0f || strlen(text) > 3)
    {
        fontName = "bahnschrift_32";
        y = 102;
    }

    lv_obj_set_style_text_font(label, ResourcePool::GetFont(fontName), 0);
    lv_label_set_text(label, text);
    lv_obj_align(label, LV_ALIGN_TOP_LEFT, 10, y);
}

static void SetCalorieLabel(lv_obj_t* label, int calorie)
{
    if (label == nullptr)
    {
        return;
    }

    char text[16];
    snprintf(text, sizeof(text), "%d", calorie);

    const bool compact = (calorie >= 10000 || calorie <= -1000 || strlen(text) > 4);
    lv_obj_set_style_text_font(label, ResourcePool::GetFont(compact ? "bahnschrift_13" : "bahnschrift_17"), 0);
    lv_label_set_text(label, text);
    lv_obj_align(label, LV_ALIGN_TOP_MID, 84, compact ? 229 : 226);
}

static void SetMaxSpeedLabel(lv_obj_t* label, float speed)
{
    if (label == nullptr)
    {
        return;
    }

    char text[16];
    float absSpeed = speed < 0.0f ? -speed : speed;
    if (absSpeed >= 1000.0f)
    {
        snprintf(text, sizeof(text), "%0.0f", speed);
    }
    else
    {
        snprintf(text, sizeof(text), "%0.1f", speed);
    }

    const lv_font_t* font = ResourcePool::GetFont("agencyb_12");
    lv_point_t textSize;
    lv_txt_get_size(&textSize, text, font, 0, 0, LV_COORD_MAX, LV_TEXT_FLAG_NONE);
    if (textSize.x > MAX_SPEED_TEXT_W)
    {
        snprintf(text, sizeof(text), "%0.0f", speed);
    }

    lv_obj_set_style_text_font(
        label,
        font,
        0
    );
    lv_label_set_text(label, text);
}

static DialplateView::TurnDirection_t NavTurnDirection(DataProc::Navigation_TurnType_t turnType)
{
    switch (turnType)
    {
    case DataProc::NAV_TURN_LEFT:
    case DataProc::NAV_TURN_SHARP_LEFT:
        return DialplateView::TURN_LEFT;
    case DataProc::NAV_TURN_RIGHT:
    case DataProc::NAV_TURN_SHARP_RIGHT:
        return DialplateView::TURN_RIGHT;
    default:
        return DialplateView::TURN_STRAIGHT;
    }
}

static DialplateView::TurnDirection_t NavApproachDirection(const DataProc::Navigation_Info_t* info, const HAL::GPS_Info_t* gps)
{
    if (info == nullptr || gps == nullptr || !info->approachTargetValid || !gps->isVaild)
    {
        return NavTurnDirection(info ? info->turnType : DataProc::NAV_TURN_STRAIGHT);
    }

    if (info->state != DataProc::NAV_STATE_APPROACHING_ROUTE &&
        info->state != DataProc::NAV_STATE_OFF_ROUTE)
    {
        return NavTurnDirection(info->turnType);
    }

    float diff = NormalizeCourseDiff((float)info->approachBearingDeg - gps->course);
    if (diff > 25.0f)
    {
        return DialplateView::TURN_RIGHT;
    }
    if (diff < -25.0f)
    {
        return DialplateView::TURN_LEFT;
    }
    return DialplateView::TURN_STRAIGHT;
}


static const char* NavText(const DataProc::Navigation_Info_t* info)
{
    switch (info->state)
    {
    case DataProc::NAV_STATE_APPROACHING_ROUTE:
        return TXT_NAV_APPROACH;
    case DataProc::NAV_STATE_OFF_ROUTE:
        return TXT_NAV_OFF_ROUTE;
    case DataProc::NAV_STATE_REVERSE_DIRECTION:
        return TXT_NAV_REVERSE;
    case DataProc::NAV_STATE_FINISHED:
        return TXT_NAV_FINISH;
    default:
        break;
    }

    switch (info->turnType)
    {
    case DataProc::NAV_TURN_LEFT:
        return TXT_NAV_LEFT;
    case DataProc::NAV_TURN_RIGHT:
        return TXT_NAV_RIGHT;
    case DataProc::NAV_TURN_SHARP_LEFT:
        return TXT_NAV_SHARP_LEFT;
    case DataProc::NAV_TURN_SHARP_RIGHT:
        return TXT_NAV_SHARP_RIGHT;
    case DataProc::NAV_TURN_FINISH:
        return TXT_NAV_FINISH;
    default:
        return TXT_NAV_STRAIGHT;
    }
}

static void SetNavDistanceLabel(lv_obj_t* value, lv_obj_t* unit, uint32_t distanceM)
{
    if (value == nullptr || unit == nullptr)
    {
        return;
    }

    if (distanceM >= 1000)
    {
        lv_label_set_text_fmt(value, "%u.%u", (unsigned)(distanceM / 1000), (unsigned)((distanceM % 1000) / 100));
        lv_label_set_text(unit, "km");
    }
    else
    {
        lv_label_set_text_fmt(value, "%u", (unsigned)distanceM);
        lv_label_set_text(unit, "m");
    }
}

Dialplate::Dialplate()
    : timer(nullptr)
    , recState(RECORD_STATE_READY)
    , lastFocus(nullptr)
    , courseFiltered(0.0f)
    , turnCourseLast(0.0f)
    , turnCourseValid(false)
    , recPressTick(0)
    , recPressing(false)
    , recLongHandled(false)
{
}

Dialplate::~Dialplate()
{
}

void Dialplate::onCustomAttrConfig()
{
    SetCustomLoadAnimType(PageManager::LOAD_ANIM_NONE);
}

void Dialplate::onViewLoad()
{
    Model.Init();
    View.Create(_root);

    AttachEvent(_root);
    AttachEvent(View.ui.btnCont.btnMap);
    AttachEvent(View.ui.btnCont.btnRec);
    AttachEvent(View.ui.btnCont.btnMenu);
}

void Dialplate::onViewDidLoad()
{

}

void Dialplate::onViewWillAppear()
{
    turnCourseValid = false;
    ClearFocusState(View.ui.btnCont.btnMap);
    ClearFocusState(View.ui.btnCont.btnRec);
    ClearFocusState(View.ui.btnCont.btnMenu);

    lv_indev_t* indev = lv_indev_get_act();
    if(indev)
    {
        lv_indev_wait_release(indev);
    }
    lv_group_t* group = lv_group_get_default();
    LV_ASSERT_NULL(group);
    if (group == nullptr)
    {
        return;
    }

    lv_group_remove_all_objs(group);
    lv_group_set_focus_cb(group, nullptr);
    lv_group_set_wrap(group, true);
    lv_group_set_editing(group, false);

    if (View.ui.btnCont.btnMap)  lv_group_add_obj(group, View.ui.btnCont.btnMap);
    if (View.ui.btnCont.btnRec)  lv_group_add_obj(group, View.ui.btnCont.btnRec);
    if (View.ui.btnCont.btnMenu) lv_group_add_obj(group, View.ui.btnCont.btnMenu);

    ClearFocusState(View.ui.btnCont.btnMap);
    ClearFocusState(View.ui.btnCont.btnRec);
    ClearFocusState(View.ui.btnCont.btnMenu);

    lv_obj_t* focus = lastFocus;
    if (focus != View.ui.btnCont.btnMap &&
        focus != View.ui.btnCont.btnRec &&
        focus != View.ui.btnCont.btnMenu)
    {
        focus = View.ui.btnCont.btnRec ? View.ui.btnCont.btnRec : View.ui.btnCont.btnMap;
    }

    if (focus)
    {
        lv_group_focus_obj(focus);
        lv_obj_add_state(focus, LV_STATE_FOCUSED);
        lastFocus = focus;
    }

    Model.SetStatusBarStyle(DataProc::STATUS_BAR_STYLE_TRANSP);
    /* 皮肤自带状态行，隐藏全局状态栏避免顶部重叠 */
    Model.SetStatusBarAppear(false);

    Update();

    View.AppearAnimStart();
}

void Dialplate::onViewDidAppear()
{
    View.SetSpectrumActive(true);

    if (timer != nullptr)
    {
        lv_timer_del(timer);
        timer = nullptr;
    }

    timer = lv_timer_create(onTimerUpdate, 1000, this);
}

void Dialplate::onViewWillDisappear()
{
    View.SetSpectrumActive(false);

    /* 恢复全局状态栏供其他页面使用 */
    Model.SetStatusBarAppear(true);

    lv_group_t* group = lv_group_get_default();
    LV_ASSERT_NULL(group);
    if (group == nullptr)
    {
        lastFocus = nullptr;
        if (timer != nullptr)
        {
            lv_timer_del(timer);
            timer = nullptr;
        }
        return;
    }
    lv_obj_t* focused = lv_group_get_focused(group);
    if (focused == View.ui.btnCont.btnMap ||
        focused == View.ui.btnCont.btnRec ||
        focused == View.ui.btnCont.btnMenu)
    {
        lastFocus = focused;
    }
    else
    {
        lastFocus = nullptr;
    }
    lv_group_set_editing(group, false);
    lv_group_remove_all_objs(group);
    ClearFocusState(View.ui.btnCont.btnMap);
    ClearFocusState(View.ui.btnCont.btnRec);
    ClearFocusState(View.ui.btnCont.btnMenu);
    if (timer != nullptr)
    {
        lv_timer_del(timer);
        timer = nullptr;
    }
    //View.AppearAnimStart(true);
}

void Dialplate::onViewDidDisappear()
{
}

void Dialplate::onViewUnload()
{
    if (timer != nullptr)
    {
        lv_timer_del(timer);
        timer = nullptr;
    }

    ClearFocusState(View.ui.btnCont.btnMap);
    ClearFocusState(View.ui.btnCont.btnRec);
    ClearFocusState(View.ui.btnCont.btnMenu);
    lastFocus = nullptr;
    Model.Deinit();
    View.Delete();
}

void Dialplate::onViewDidUnload()
{

}

void Dialplate::AttachEvent(lv_obj_t* obj)
{
    if (obj == nullptr)
    {
        return;
    }

    lv_obj_add_event_cb(obj, onEvent, LV_EVENT_ALL, this);
}

void Dialplate::Update()
{
    char buf[16];
    float speed = Model.GetSpeed();
    SetSpeedLabel(View.ui.speed.labelValue, speed);
    View.SetSpectrumSpeed(speed);
    View.SetBluetoothConnected(Model.GetBluetoothConnected());
    HAL::Power_Info_t powerInfo;
    if (Model.GetPowerInfo(&powerInfo))
    {
        View.SetBattery(powerInfo.usage, powerInfo.isCharging);
    }
    /* MAX 标题与数值由视图层叠加在左下框内，此处只刷新数值。 */
    if (View.ui.maxBar.labelMax)
    {
        SetMaxSpeedLabel(View.ui.maxBar.labelMax, Model.GetMaxSpeed());
    }
		
    if (View.ui.metrics.item[0].labelValue)
    {
        lv_label_set_text_fmt(View.ui.metrics.item[0].labelValue, "%0.1f", Model.GetAvgSpeed());
    }
    if (View.ui.metrics.item[1].labelValue)
    {
        lv_label_set_text(
            View.ui.metrics.item[1].labelValue,
            DataProc::MakeTimeString(Model.sportStatusInfo.singleTime, buf, sizeof(buf))
        );
    }
    if (View.ui.metrics.item[2].labelValue)
    {
        lv_label_set_text_fmt(View.ui.metrics.item[2].labelValue, "%0.1f",
            Model.sportStatusInfo.singleDistance / 1000);
    }
    SetCalorieLabel(View.ui.metrics.item[3].labelValue, int(Model.sportStatusInfo.singleCalorie));

    bool navGuidanceActive = false;
    DataProc::Navigation_Info_t navInfo;
    if (Model.GetNavigationInfo(&navInfo) &&
        navInfo.active &&
        navInfo.routeStatus == DataProc::NAV_ROUTE_STATUS_VALID)
    {
        uint32_t navDistance = navInfo.distanceToTurnM ? navInfo.distanceToTurnM : navInfo.distanceToFinishM;
        SetNavDistanceLabel(View.ui.nav.labelDist, View.ui.nav.labelDistUnit, navDistance);
        HAL::GPS_Info_t navGps;
        DATA_PROC_INIT_STRUCT(navGps);
        bool navGpsValid = Model.GetGPSInfo(&navGps);
        View.SetTurnDirection(navGpsValid ? NavApproachDirection(&navInfo, &navGps) : NavTurnDirection(navInfo.turnType));
        if (View.ui.nav.labelTurnText)
        {
            lv_label_set_text(View.ui.nav.labelTurnText, NavText(&navInfo));
        }
        navGuidanceActive = true;
    }

    /* GPS：海拔 + 当前位置三角朝向 */
    HAL::GPS_Info_t gps;
    if (Model.GetGPSInfo(&gps))
    {
        View.SetAltitude(int(gps.altitude));
        if (View.ui.status.labelGpsSat)
        {
            lv_label_set_text_fmt(View.ui.status.labelGpsSat, "%d", int(gps.satellites));
            lv_obj_set_style_text_color(
                View.ui.status.labelGpsSat,
                gps.satellites >= 7 ? lv_color_hex(0x5dff2e) :
                (gps.satellites >= 3 ? lv_color_hex(0xf6db22) : lv_color_hex(0x9fb3c0)),
                0
            );
        }

        /* 评审⑬：低速冻结朝向，避免静止时 course 抖动乱转；
           运动时对 course 一阶低通滤波，跨 0/360 边界归一化。 */
        if (gps.speed >= 2.0f)
        {
            float diff = NormalizeCourseDiff(gps.course - courseFiltered);
            courseFiltered += 0.3f * diff;
            if (courseFiltered < 0.0f)    courseFiltered += 360.0f;
            if (courseFiltered >= 360.0f) courseFiltered -= 360.0f;
            View.SetArrowAngle(courseFiltered);

            if (!navGuidanceActive && turnCourseValid)
            {
                float turnDiff = NormalizeCourseDiff(gps.course - turnCourseLast);
                if (turnDiff > TURN_COURSE_THRESHOLD)
                {
                    View.SetTurnDirection(DialplateView::TURN_RIGHT);
                }
                else if (turnDiff < -TURN_COURSE_THRESHOLD)
                {
                    View.SetTurnDirection(DialplateView::TURN_LEFT);
                }
                else
                {
                    View.SetTurnDirection(DialplateView::TURN_STRAIGHT);
                }
            }
            turnCourseLast = gps.course;
            turnCourseValid = true;
        }
        else
        {
            if (!navGuidanceActive)
            {
                View.SetTurnDirection(DialplateView::TURN_STRAIGHT);
            }
            turnCourseValid = false;
        }
    }
    else
    {
        if (View.ui.status.labelGpsSat)
        {
            lv_label_set_text(View.ui.status.labelGpsSat, "--");
            lv_obj_set_style_text_color(View.ui.status.labelGpsSat, lv_color_hex(0x9fb3c0), 0);
        }
        if (!navGuidanceActive)
        {
            View.SetTurnDirection(DialplateView::TURN_STRAIGHT);
        }
        turnCourseValid = false;
    }
}

void Dialplate::onTimerUpdate(lv_timer_t* timer)
{
    if (timer == nullptr || timer->user_data == nullptr)
    {
        return;
    }

    Dialplate* instance = (Dialplate*)timer->user_data;

    instance->Update();
}

void Dialplate::onBtnClicked(lv_obj_t* btn)
{
    if (btn == View.ui.btnCont.btnMap)
    {
        _Manager->Push("Pages/LiveMap");
    }
    else if (btn == View.ui.btnCont.btnMenu)
    {
        _Manager->Push("Pages/MainMenu");
    }
}

void Dialplate::onRecord(bool longPress)
{
    switch (recState)
    {
    case RECORD_STATE_READY:
        if (longPress)
        {
            if (!Model.GetGPSReady())
            {
                LV_LOG_WARN("GPS has not ready, can't start record");
                Model.PlayMusic("Error");
                return;
            }

            Model.PlayMusic("Connect");
            Model.RecorderCommand(Model.REC_START);
            View.SetRecRecording(true);
            recState = RECORD_STATE_RUN;
        }
        break;
    case RECORD_STATE_RUN:
        if (!longPress)
        {
            Model.PlayMusic("UnstableConnect");
            Model.RecorderCommand(Model.REC_PAUSE);
            View.SetRecRecording(false);
            recState = RECORD_STATE_PAUSE;
        }
        break;
    case RECORD_STATE_PAUSE:
        if (longPress)
        {
            Model.PlayMusic("NoOperationWarning");
            View.SetRecRecording(false);
            Model.RecorderCommand(Model.REC_READY_STOP);
            recState = RECORD_STATE_STOP;
        }
        else
        {
            Model.PlayMusic("Connect");
            Model.RecorderCommand(Model.REC_CONTINUE);
            View.SetRecRecording(true);
            recState = RECORD_STATE_RUN;
        }
        break;
    case RECORD_STATE_STOP:
        if (longPress)
        {
            Model.PlayMusic("Disconnect");
            Model.RecorderCommand(Model.REC_STOP);
            View.SetRecRecording(false);
            recState = RECORD_STATE_READY;
        }
        else
        {
            Model.PlayMusic("Connect");
            Model.RecorderCommand(Model.REC_CONTINUE);
            View.SetRecRecording(true);
            recState = RECORD_STATE_RUN;
        }
        break;
    default:
        break;
    }
}

void Dialplate::onEvent(lv_event_t* event)
{
    Dialplate* instance = (Dialplate*)lv_event_get_user_data(event);
    LV_ASSERT_NULL(instance);

    lv_obj_t* obj = lv_event_get_current_target(event);
    lv_event_code_t code = lv_event_get_code(event);

    if (code == LV_EVENT_GESTURE)
    {
        if (obj != instance->_root)
        {
            return;
        }

        lv_indev_t* indev = lv_indev_get_act();
        lv_dir_t dir = lv_indev_get_gesture_dir(indev);

        if (dir == LV_DIR_LEFT)
        {
            instance->_Manager->Push("Pages/MainMenu");
        }
        else if (dir == LV_DIR_RIGHT)
        {
            instance->_Manager->Push("Pages/LiveMap");
        }
        return;
    }

    if (code == LV_EVENT_SHORT_CLICKED && obj != instance->View.ui.btnCont.btnRec)
    {
        instance->onBtnClicked(obj);
    }

    if (obj == instance->View.ui.btnCont.btnRec)
    {
        if (code == LV_EVENT_PRESSED)
        {
            instance->recPressTick = lv_tick_get();
            instance->recPressing = true;
            instance->recLongHandled = false;
        }
        else if (code == LV_EVENT_LONG_PRESSED)
        {
            if (!instance->recLongHandled)
            {
                instance->onRecord(true);
                instance->recLongHandled = true;
            }
        }
        else if (code == LV_EVENT_RELEASED)
        {
            uint32_t pressTime = instance->recPressing ? lv_tick_elaps(instance->recPressTick) : 0;
            if (!instance->recLongHandled)
            {
                instance->onRecord(pressTime >= REC_LONG_PRESS_MS);
            }
            instance->recPressing = false;
            instance->recLongHandled = false;
        }
    }
}
