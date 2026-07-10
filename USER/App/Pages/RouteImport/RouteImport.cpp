#include "RouteImport.h"

#include <stdio.h>
#include <string.h>

using namespace Page;

#define TXT_TITLE      "\xE5\xAF\xBC\xE5\x85\xA5\xE8\xB7\xAF\xE7\xBA\xBF"
#define TXT_IMPORTING  "\xE6\xAD\xA3\xE5\x9C\xA8\xE5\xAF\xBC\xE5\x85\xA5"
#define TXT_DONE       "\xE5\xAF\xBC\xE5\x85\xA5\xE5\xAE\x8C\xE6\x88\x90"
#define TXT_FAIL       "\xE5\xAF\xBC\xE5\x85\xA5\xE5\xA4\xB1\xE8\xB4\xA5"
#define TXT_SYNC       "GPX SYNC"
#define TXT_START      "\xE5\xA7\x8B\xE7\x82\xB9"
#define TXT_END        "\xE7\xBB\x88\xE7\x82\xB9"
#define TXT_FILE_FMT   "\xE6\x96\x87\xE4\xBB\xB6\xE6\xA0\xBC\xE5\xBC\x8F"
#define TXT_FILE_NAME  "\xE6\x96\x87\xE4\xBB\xB6\xE5\x90\x8D"

namespace
{
    lv_obj_t* CreateBar(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_color_t color, lv_opa_t opa)
    {
        lv_obj_t* obj = lv_obj_create(parent);
        lv_obj_remove_style_all(obj);
        lv_obj_set_pos(obj, x, y);
        lv_obj_set_size(obj, w, h);
        lv_obj_set_style_bg_color(obj, color, 0);
        lv_obj_set_style_bg_opa(obj, opa, 0);
        lv_obj_set_style_radius(obj, h / 2, 0);
        lv_obj_clear_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_clear_flag(obj, LV_OBJ_FLAG_CLICKABLE);
        return obj;
    }

    lv_obj_t* CreateLabel(lv_obj_t* parent, const char* text, const char* font, lv_color_t color)
    {
        lv_obj_t* label = lv_label_create(parent);
        lv_obj_set_style_text_font(label, ResourcePool::GetFont(font), 0);
        lv_obj_set_style_text_color(label, color, 0);
        lv_label_set_text(label, text);
        return label;
    }

    lv_obj_t* CreateRing(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t size, lv_color_t border, lv_color_t bg)
    {
        lv_obj_t* obj = lv_obj_create(parent);
        lv_obj_remove_style_all(obj);
        lv_obj_set_pos(obj, x, y);
        lv_obj_set_size(obj, size, size);
        lv_obj_set_style_radius(obj, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(obj, bg, 0);
        lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
        lv_obj_set_style_border_width(obj, 4, 0);
        lv_obj_set_style_border_color(obj, border, 0);
        lv_obj_clear_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_clear_flag(obj, LV_OBJ_FLAG_CLICKABLE);
        return obj;
    }

    void CreateFileIcon(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, const char* text)
    {
        lv_obj_t* doc = lv_obj_create(parent);
        lv_obj_remove_style_all(doc);
        lv_obj_set_pos(doc, x, y);
        lv_obj_set_size(doc, 28, 24);
        lv_obj_set_style_bg_opa(doc, LV_OPA_TRANSP, 0);
        lv_obj_set_style_border_width(doc, 2, 0);
        lv_obj_set_style_border_color(doc, lv_color_hex(0x8d9397), 0);
        lv_obj_set_style_radius(doc, 4, 0);
        lv_obj_clear_flag(doc, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_clear_flag(doc, LV_OBJ_FLAG_CLICKABLE);

        lv_obj_t* fold = lv_obj_create(doc);
        lv_obj_remove_style_all(fold);
        lv_obj_set_pos(fold, 18, 0);
        lv_obj_set_size(fold, 8, 8);
        lv_obj_set_style_bg_color(fold, lv_color_hex(0x12181a), 0);
        lv_obj_set_style_bg_opa(fold, LV_OPA_COVER, 0);
        lv_obj_set_style_border_width(fold, 1, 0);
        lv_obj_set_style_border_color(fold, lv_color_hex(0x8d9397), 0);
        lv_obj_clear_flag(fold, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_clear_flag(fold, LV_OBJ_FLAG_CLICKABLE);

        if (text)
        {
            lv_obj_t* tag = CreateLabel(doc, text, "bahnschrift_13", lv_color_hex(0x20e8f0));
            lv_obj_align(tag, LV_ALIGN_CENTER, 0, 4);
        }
        else
        {
            for (int i = 0; i < 3; i++)
            {
                CreateBar(doc, 7, 8 + i * 6, 14, 2, lv_color_hex(0x8d9397), LV_OPA_COVER);
            }
        }
    }
}

RouteImport::RouteImport()
    : account(nullptr),
      timer(nullptr),
      titleLabel(nullptr),
      statusLabel(nullptr),
      fileLabel(nullptr),
      progressArc(nullptr),
      percentValueLabel(nullptr),
      percentUnitLabel(nullptr),
      done(false),
      lastProgressPct(0)
{
    memset(routeSegs, 0, sizeof(routeSegs));
    memset(headerSegs, 0, sizeof(headerSegs));
}

RouteImport::~RouteImport()
{
}

void RouteImport::onViewLoad()
{
    account = new Account("RouteImport", DataProc::Center(), 0, this);
    account->Subscribe("Navigation");
    CreateUI();
    lv_obj_add_event_cb(_root, onEvent, LV_EVENT_ALL, this);
}

void RouteImport::onViewDidAppear()
{
    timer = lv_timer_create(onTimer, 80, this);
}

void RouteImport::onViewWillDisappear()
{
    if (timer)
    {
        lv_timer_del(timer);
        timer = nullptr;
    }
}

void RouteImport::onViewUnload()
{
    if (timer)
    {
        lv_timer_del(timer);
        timer = nullptr;
    }
    if (account)
    {
        delete account;
        account = nullptr;
    }
}

void RouteImport::CreateUI()
{
    lv_obj_remove_style_all(_root);
    lv_obj_set_size(_root, LV_HOR_RES, LV_VER_RES);
    lv_obj_set_style_bg_color(_root, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(_root, LV_OPA_COVER, 0);
    lv_obj_clear_flag(_root, LV_OBJ_FLAG_SCROLLABLE);

    CreateMapTexture();
    CreateFrame();
    CreateHeaderPanel();
    CreateRoutePreview();
    CreateProgressCard();
    UpdateProgress(0);
}

void RouteImport::CreateFrame()
{
    CreateBar(_root, 0, 25, LV_HOR_RES, 1, lv_color_hex(0x2a2f32), LV_OPA_COVER);
    CreateBar(_root, 8, 310, LV_HOR_RES - 16, 1, lv_color_hex(0x161d20), LV_OPA_COVER);
}

void RouteImport::CreateMapTexture()
{
    for (int i = 0; i < 22; i++)
    {
        lv_coord_t x = 12 + (i * 53) % 214;
        lv_coord_t y = 42 + (i * 37) % 255;
        CreateBar(_root, x, y, 1, 1, lv_color_hex(0x142326), LV_OPA_80);
    }

    for (int i = 0; i < 6; i++)
    {
        CreateBar(_root, 18 + i * 36, 124, 18, 1, lv_color_hex(0x071316), LV_OPA_COVER);
        CreateBar(_root, 8 + i * 40, 178, 22, 1, lv_color_hex(0x071316), LV_OPA_COVER);
    }
}

void RouteImport::CreateHeaderPanel()
{
    titleLabel = lv_label_create(_root);
    lv_obj_set_style_text_font(titleLabel, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(titleLabel, lv_color_white(), 0);
    lv_label_set_text(titleLabel, TXT_TITLE);
    lv_obj_align(titleLabel, LV_ALIGN_TOP_MID, 0, 34);

    CreateBar(_root, 15, 47, 55, 2, lv_color_hex(0x00d6e8), LV_OPA_80);
    CreateBar(_root, 70, 47, 9, 2, lv_color_hex(0x00d6e8), LV_OPA_80);
    CreateBar(_root, 161, 47, 9, 2, lv_color_hex(0x00d6e8), LV_OPA_80);
    CreateBar(_root, 170, 47, 55, 2, lv_color_hex(0x00d6e8), LV_OPA_80);

    for (int i = 0; i < HEADER_SEG_COUNT; i++)
    {
        headerSegs[i] = CreateBar(_root, 74 + i * 9, 60, 6, 3, lv_color_hex(0x33383a), LV_OPA_COVER);
    }
}

void RouteImport::CreateRoutePreview()
{
    const lv_coord_t path[ROUTE_SEG_COUNT][2] =
    {
        { 20, 111 }, { 34, 106 }, { 48, 100 }, { 62, 103 }, { 76, 95 }, { 90, 100 },
        { 104, 83 }, { 118, 74 }, { 132, 86 }, { 146, 80 }, { 160, 72 }, { 174, 88 },
        { 188, 96 }, { 202, 88 }, { 214, 72 }, { 224, 66 }, { 231, 54 }, { 235, 46 }
    };

    CreateRing(_root, 12, 105, 18, lv_color_hex(0x57f34a), lv_color_hex(0x12381d));
    lv_obj_t* startText = CreateLabel(_root, TXT_START, "cn_16", lv_color_hex(0x57f34a));
    lv_obj_set_pos(startText, 6, 122);

    for (int i = 0; i < ROUTE_SEG_COUNT; i++)
    {
        routeSegs[i] = CreateBar(_root, path[i][0], path[i][1], 8, 5, lv_color_hex(0x3a4244), LV_OPA_COVER);
    }

    CreateRing(_root, 224, 38, 16, lv_color_hex(0x57f34a), lv_color_black());
    lv_obj_t* endText = CreateLabel(_root, TXT_END, "cn_16", lv_color_hex(0x57f34a));
    lv_obj_align(endText, LV_ALIGN_TOP_RIGHT, -2, 58);
}

void RouteImport::CreateProgressCard()
{
    progressArc = lv_arc_create(_root);
    lv_obj_remove_style_all(progressArc);
    lv_obj_set_size(progressArc, 122, 122);
    lv_obj_set_pos(progressArc, 59, 116);
    lv_arc_set_range(progressArc, 0, 100);
    lv_arc_set_value(progressArc, 0);
    lv_obj_set_style_arc_width(progressArc, 10, LV_PART_MAIN);
    lv_obj_set_style_arc_color(progressArc, lv_color_hex(0x2e3436), LV_PART_MAIN);
    lv_obj_set_style_arc_opa(progressArc, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_arc_width(progressArc, 10, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(progressArc, lv_color_hex(0x20e8f0), LV_PART_INDICATOR);
    lv_obj_set_style_arc_opa(progressArc, LV_OPA_COVER, LV_PART_INDICATOR);
    lv_obj_set_style_bg_opa(progressArc, LV_OPA_TRANSP, LV_PART_KNOB);
    lv_obj_clear_flag(progressArc, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t* arcCore = lv_obj_create(_root);
    lv_obj_remove_style_all(arcCore);
    lv_obj_set_size(arcCore, 92, 92);
    lv_obj_set_pos(arcCore, 74, 131);
    lv_obj_set_style_bg_color(arcCore, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(arcCore, LV_OPA_80, 0);
    lv_obj_set_style_radius(arcCore, LV_RADIUS_CIRCLE, 0);

    percentValueLabel = lv_label_create(arcCore);
    lv_obj_set_style_text_font(percentValueLabel, ResourcePool::GetFont("bahnschrift_48"), 0);
    lv_obj_set_style_text_color(percentValueLabel, lv_color_white(), 0);
    lv_label_set_text(percentValueLabel, "0");
    lv_obj_align(percentValueLabel, LV_ALIGN_CENTER, -11, -8);

    percentUnitLabel = lv_label_create(arcCore);
    lv_obj_set_style_text_font(percentUnitLabel, ResourcePool::GetFont("bahnschrift_17"), 0);
    lv_obj_set_style_text_color(percentUnitLabel, lv_color_white(), 0);
    lv_label_set_text(percentUnitLabel, "%");
    lv_obj_align_to(percentUnitLabel, percentValueLabel, LV_ALIGN_OUT_RIGHT_BOTTOM, 2, -9);

    statusLabel = lv_label_create(arcCore);
    lv_obj_set_style_text_font(statusLabel, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(statusLabel, lv_color_hex(0x20e8f0), 0);
    lv_label_set_text(statusLabel, TXT_IMPORTING);
    lv_obj_align(statusLabel, LV_ALIGN_BOTTOM_MID, 0, -12);

    lv_obj_t* card = lv_obj_create(_root);
    lv_obj_remove_style_all(card);
    lv_obj_set_pos(card, 7, 238);
    lv_obj_set_size(card, 226, 66);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x070b0d), 0);
    lv_obj_set_style_bg_opa(card, LV_OPA_80, 0);
    lv_obj_set_style_border_width(card, 2, 0);
    lv_obj_set_style_border_color(card, lv_color_hex(0x4a5054), 0);
    lv_obj_set_style_radius(card, 13, 0);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_CLICKABLE);

    CreateFileIcon(card, 13, 6, "GPX");
    CreateFileIcon(card, 13, 38, nullptr);
    CreateBar(card, 8, 33, 210, 1, lv_color_hex(0x3c4245), LV_OPA_COVER);
    CreateBar(card, 130, 8, 1, 21, lv_color_hex(0x9aa0a3), LV_OPA_COVER);
    CreateBar(card, 130, 40, 1, 19, lv_color_hex(0x9aa0a3), LV_OPA_COVER);

    lv_obj_t* fmtLabel = CreateLabel(card, TXT_FILE_FMT, "cn_16", lv_color_hex(0xc8cbcd));
    lv_obj_set_pos(fmtLabel, 55, 10);
    lv_obj_t* fmtValue = CreateLabel(card, "GPX", "bahnschrift_17", lv_color_white());
    lv_obj_set_pos(fmtValue, 151, 9);

    lv_obj_t* nameLabel = CreateLabel(card, TXT_FILE_NAME, "cn_16", lv_color_hex(0xc8cbcd));
    lv_obj_set_pos(nameLabel, 55, 42);

    fileLabel = lv_label_create(card);
    lv_obj_set_style_text_font(fileLabel, ResourcePool::GetFont("bahnschrift_17"), 0);
    lv_obj_set_style_text_color(fileLabel, lv_color_white(), 0);
    lv_label_set_long_mode(fileLabel, LV_LABEL_LONG_DOT);
    lv_obj_set_width(fileLabel, 70);
    lv_label_set_text(fileLabel, TXT_SYNC);
    DataProc::Navigation_Info_t info;
    DATA_PROC_INIT_STRUCT(info);
    if (account && account->Pull("Navigation", &info, sizeof(info)) == Account::RES_OK && info.routeName[0])
    {
        lv_label_set_text(fileLabel, info.routeName);
    }
    lv_obj_set_pos(fileLabel, 151, 40);
}

void RouteImport::UpdateProgress(uint8_t pct)
{
    if (pct > 100)
    {
        pct = 100;
    }
    lastProgressPct = pct;

    if (percentValueLabel)
    {
        lv_label_set_text_fmt(percentValueLabel, "%d", (int)pct);
        lv_obj_align(percentValueLabel, LV_ALIGN_CENTER, -8, -4);
    }
    if (percentUnitLabel && percentValueLabel)
    {
        lv_obj_align_to(percentUnitLabel, percentValueLabel, LV_ALIGN_OUT_RIGHT_BOTTOM, 3, -2);
    }

    int routeActive = (pct * ROUTE_SEG_COUNT + 99) / 100;
    int headerActive = (pct * HEADER_SEG_COUNT + 99) / 100;
    if (progressArc)
    {
        lv_arc_set_value(progressArc, pct);
    }

    for (int i = 0; i < ROUTE_SEG_COUNT; i++)
    {
        lv_color_t color = lv_color_hex(0x18aebd);
        if (i < routeActive)
        {
            color = (i >= routeActive - 4) ? lv_color_hex(0xffdf35) : lv_color_hex(0x22e7f2);
        }
        lv_obj_set_style_bg_color(routeSegs[i], color, 0);
    }

    for (int i = 0; i < HEADER_SEG_COUNT; i++)
    {
        lv_obj_set_style_bg_color(
            headerSegs[i],
            i < headerActive ? lv_color_hex(0x57f34a) : lv_color_hex(0x33383a),
            0
        );
    }
}

void RouteImport::Tick()
{
    if (account == nullptr || done)
    {
        return;
    }

    DataProc::Navigation_CmdInfo_t cmd;
    DATA_PROC_INIT_STRUCT(cmd);
    cmd.cmd = DataProc::NAV_CMD_IMPORT_STEP;
    account->Notify("Navigation", &cmd, sizeof(cmd));

    DataProc::Navigation_Info_t info;
    DATA_PROC_INIT_STRUCT(info);
    if (account->Pull("Navigation", &info, sizeof(info)) != Account::RES_OK)
    {
        return;
    }

    UpdateProgress(info.importProgressPct);
    if (info.routeStatus == DataProc::NAV_ROUTE_STATUS_VALID)
    {
        UpdateProgress(100);
        lv_label_set_text(statusLabel, TXT_DONE);
        done = true;
        lv_timer_t* closeTimer = lv_timer_create([](lv_timer_t* t)
        {
            RouteImport* instance = (RouteImport*)t->user_data;
            lv_timer_del(t);
            if (instance)
            {
                instance->_Manager->Pop();
            }
        }, 700, this);
        lv_timer_set_repeat_count(closeTimer, 1);
    }
    else if (info.routeStatus == DataProc::NAV_ROUTE_STATUS_ERROR)
    {
        lv_label_set_text(statusLabel, info.errorText[0] ? info.errorText : TXT_FAIL);
        done = true;
    }
}

void RouteImport::Cancel()
{
    if (account)
    {
        DataProc::Navigation_CmdInfo_t cmd;
        DATA_PROC_INIT_STRUCT(cmd);
        cmd.cmd = DataProc::NAV_CMD_CANCEL_IMPORT;
        account->Notify("Navigation", &cmd, sizeof(cmd));
    }
    _Manager->Pop();
}

void RouteImport::onTimer(lv_timer_t* timer)
{
    RouteImport* instance = (RouteImport*)timer->user_data;
    if (instance)
    {
        instance->Tick();
    }
}

void RouteImport::onEvent(lv_event_t* event)
{
    RouteImport* instance = (RouteImport*)lv_event_get_user_data(event);
    if (instance == nullptr)
    {
        return;
    }
    lv_event_code_t code = lv_event_get_code(event);
    if (code == LV_EVENT_LEAVE || code == LV_EVENT_GESTURE)
    {
        instance->Cancel();
    }
}
