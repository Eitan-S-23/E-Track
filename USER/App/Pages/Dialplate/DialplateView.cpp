#include "DialplateView.h"
#include "Resource/ResourcePool.h"
#include <stdio.h>
#include <string.h>
#include <cmath>

#if DIALPLATE_HW_EFFECTS
#include "lv_port/lv_port.h"
#endif

using namespace Page;

/*=========================
 *  2.png 配色（叠加文本用）
 *=========================*/
#define COL_WHITE     lv_color_white()
#define COL_CYAN      lv_color_hex(0x1ad0e0)   /* 青色：标签（多由皮肤烘焙） */
#define COL_GREEN     lv_color_hex(0x5dff2e)   /* 霓虹绿：坡度 */
#define COL_GRAY      lv_color_hex(0x9fb3c0)   /* 灰色：单位 */
#define COL_ORANGE    lv_color_hex(0xff8a1e)   /* 橙色：CAL（高亮面板） */
#define COL_REC_RED   lv_color_hex(0xff2a2a)   /* REC 运行态 */
#define COL_PANEL_BG  lv_color_hex(0x081018)   /* 覆盖皮肤烘焙文字的小底色 */
#define COL_BLUE      lv_color_hex(0x24b8ff)
#define COL_YELLOW    lv_color_hex(0xf6db22)

#define SCR_W         240
#define SCR_H         320
#define ARROW_CENTER_X 119
#define ARROW_CENTER_Y 232
#define ARROW_PIVOT_X  8
#define ARROW_PIVOT_Y  11

#define MAX_LABEL_X   (-9)
#define MAX_TITLE_Y   236
#define MAX_VALUE_Y   246
#define MAX_VALUE_W   58
#define SPECTRUM_X    10
#define SPECTRUM_Y    161
#define SPECTRUM_W    25
#define SPECTRUM_H    72
#define SPECTRUM_MASK_X 10
#define SPECTRUM_MASK_Y 161
#define SPECTRUM_MASK_W 25
#define SPECTRUM_MASK_H 72
#define SPECTRUM_SEG_H 3
#define SPECTRUM_SEG_GAP 1
#define SPECTRUM_MIN_LEVEL_PCT 10
#define SPECTRUM_MAX_LEVEL_PCT 100
#define SPECTRUM_FULL_SPEED_KPH 50.0f

static const uint8_t spectrumFrames[][DialplateView::SPECTRUM_BAR_NUM] =
{
    { 2, 8, 16 },
    { 4, 16, 6 },
    { 12, 3, 15 },
    { 5, 14, 2 },
    { 16, 7, 11 },
    { 3, 10, 16 },
    { 9, 2, 13 },
    { 15, 5, 4 }
};

#define FONT(name)    ResourcePool::GetFont(name)
#define IMG(name)     ResourcePool::GetImage(name)

#define ICON_TURN_RIGHT     "\xEE\x98\xAB"  /* U+E62B iconfont: right turn */
#define ICON_TURN_LEFT      "\xEE\x98\xAC"  /* U+E62C iconfont: left turn */
#define ICON_TURN_STRAIGHT  "\xEE\x98\xBB"  /* U+E63B iconfont: straight */
#define ICON_MENU           "\xEE\x99\x91"  /* U+E651 iconfont: menu */
#define ICON_ALTITUDE       "\xEE\x9A\x9B"  /* U+E69B iconfont: altitude */
#define ICON_HEART_RATE     "\xEE\xA2\xBF"  /* U+E8BF iconfont: heart rate */
#define ICON_MAP            "\xEE\xA7\x80"  /* U+E9C0 iconfont: map */
#define ICON_CLIMB          "\xEE\x9B\xB2"  /* U+E6F2 iconfont: climb */

#define TXT_TURN_RIGHT      "\xE5\x8F\xB3" "\xE8\xBD\xAC"
#define TXT_TURN_LEFT       "\xE5\xB7\xA6" "\xE8\xBD\xAC"
#define TXT_TURN_STRAIGHT   "\xE7\x9B\xB4" "\xE8\xA1\x8C"
#define TXT_MAP             "\xE5\x9C\xB0" "\xE5\x9B\xBE"
#define TXT_MENU            "\xE8\x8F\x9C" "\xE5\x8D\x95"

static const char* const metricNumberFonts[] = { "bahnschrift_17", "agencyb_12", "montserrat_8" };
static const char* const metricTimeFonts[] = { "bahnschrift_17", "bahnschrift_13", "agencyb_12", "montserrat_8" };
static const char* const metricCalorieFonts[] = { "bahnschrift_24", "bahnschrift_17", "agencyb_12", "montserrat_8" };

struct DialplateMetricLayout
{
    lv_coord_t x;
    lv_coord_t y;
    lv_coord_t width;
    lv_coord_t height;
    lv_text_align_t align;
    const char* const* fonts;
    uint8_t fontCount;
};

static const DialplateMetricLayout metricLayouts[DialplateView::METRIC_NUM] =
{
    { 181, 94, 25, 16, LV_TEXT_ALIGN_RIGHT, metricNumberFonts, 3 },
    { 180, 137, 54, 20, LV_TEXT_ALIGN_CENTER, metricTimeFonts, 4 },
    { 181, 184, 26, 16, LV_TEXT_ALIGN_RIGHT, metricNumberFonts, 3 },
    { 180, 225, 54, 22, LV_TEXT_ALIGN_CENTER, metricCalorieFonts, 4 }
};

#if DIALPLATE_HW_EFFECTS
struct DialplateGlowPixel
{
    uint32_t index;
    uint8_t r;
    uint8_t g;
    uint8_t b;
};

struct DialplateGlowFrame
{
    const DialplateGlowPixel* pixels;
    uint16_t count;
};

struct DialplateGlowSegment
{
    lv_area_t area;
};

struct DialplateGlowSegmentFrame
{
    const DialplateGlowSegment* segments;
    uint16_t count;
};

#include "DialplateGlowData.inc"

enum { SPECTRUM_ROWS_PER_BLIT = 2 };
static lv_color_t effectBuffer[SPECTRUM_W * SPECTRUM_ROWS_PER_BLIT];
static_assert(DIALPLATE_GLOW_BLIT_MAX_PIXELS <= SPECTRUM_W * SPECTRUM_ROWS_PER_BLIT,
              "Sparse glow must fit the shared display scratch buffer");

static void SpectrumLevels(const uint8_t* frame, uint8_t level, uint8_t* lit)
{
    for(int bar = 0; bar < DialplateView::SPECTRUM_BAR_NUM; bar++)
    {
        lit[bar] = (uint8_t)(((uint16_t)frame[bar] * level + 99U) / 100U);
        if(lit[bar] == 0) lit[bar] = 1;
        if(lit[bar] > DialplateView::SPECTRUM_SEG_NUM) lit[bar] = DialplateView::SPECTRUM_SEG_NUM;
    }
}

static lv_color_t SpectrumColor(lv_coord_t x, lv_coord_t y, const uint8_t* lit)
{
    const lv_coord_t bar = x / 9;
    const lv_coord_t offset = SPECTRUM_H - 1 - y;
    const lv_coord_t segment = offset / (SPECTRUM_SEG_H + SPECTRUM_SEG_GAP);
    const bool isSegment = x % 9 < 7 &&
        offset % (SPECTRUM_SEG_H + SPECTRUM_SEG_GAP) < SPECTRUM_SEG_H &&
        bar < DialplateView::SPECTRUM_BAR_NUM && segment < lit[bar];
    return isSegment ? COL_CYAN : COL_PANEL_BG;
}
#endif

static lv_obj_t* OverlayLabel(lv_obj_t* par, const lv_font_t* font, lv_color_t color,
                              lv_coord_t x, lv_coord_t y, const char* text)
{
    lv_obj_t* label = lv_label_create(par);
    if(label == nullptr)
    {
        return nullptr;
    }
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, color, 0);
    lv_label_set_text(label, text);
    lv_obj_set_pos(label, x, y);
    lv_obj_clear_flag(label, LV_OBJ_FLAG_CLICKABLE);
    return label;
}

static lv_obj_t* OverlayBox(lv_obj_t* par, lv_coord_t x, lv_coord_t y,
                            lv_coord_t w, lv_coord_t h, lv_color_t color,
                            lv_opa_t opa = LV_OPA_COVER, lv_coord_t radius = 0)
{
    lv_obj_t* obj = lv_obj_create(par);
    if(obj == nullptr)
    {
        return nullptr;
    }
    lv_obj_remove_style_all(obj);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_size(obj, w, h);
    lv_obj_set_style_bg_color(obj, color, 0);
    lv_obj_set_style_bg_opa(obj, opa, 0);
    lv_obj_set_style_radius(obj, radius, 0);
    lv_obj_clear_flag(obj, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
    return obj;
}

static lv_obj_t* OverlayOutline(lv_obj_t* par, lv_coord_t x, lv_coord_t y,
                                lv_coord_t w, lv_coord_t h, lv_color_t color,
                                lv_coord_t radius = 0)
{
    lv_obj_t* obj = OverlayBox(par, x, y, w, h, color, LV_OPA_TRANSP, radius);
    if(obj == nullptr)
    {
        return nullptr;
    }
    lv_obj_set_style_border_width(obj, 1, 0);
    lv_obj_set_style_border_color(obj, color, 0);
    lv_obj_set_style_border_opa(obj, LV_OPA_COVER, 0);
    return obj;
}

static lv_obj_t* OverlayImg(lv_obj_t* par, const char* name, lv_color_t color,
                            lv_coord_t x, lv_coord_t y)
{
    lv_obj_t* img = lv_img_create(par);
    if(img == nullptr)
    {
        return nullptr;
    }
    const void* src = IMG(name);
    if(src == nullptr)
    {
        lv_obj_del(img);
        return nullptr;
    }
    lv_img_set_src(img, src);
    lv_obj_set_pos(img, x, y);
    lv_obj_set_style_img_recolor(img, color, 0);
    lv_obj_set_style_img_recolor_opa(img, LV_OPA_COVER, 0);
    lv_obj_clear_flag(img, LV_OBJ_FLAG_CLICKABLE);
    return img;
}

static void SetFixedLabelBox(lv_obj_t* label, lv_coord_t w, lv_coord_t h, lv_text_align_t align)
{
    if(label == nullptr)
    {
        return;
    }
    lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
    lv_obj_set_size(label, w, h);
    lv_obj_set_style_text_align(label, align, 0);
}

DialplateView::DialplateView()
{
    memset(&ui, 0, sizeof(ui));
    memset(&styleBtn, 0, sizeof(styleBtn));
    memset(&styleBtnFocus, 0, sizeof(styleBtnFocus));
}

void DialplateView::Create(lv_obj_t* root)
{
    memset(&ui, 0, sizeof(ui));
    ui.arrow.angle = -3600;
    if(root == nullptr)
    {
        return;
    }

    lv_obj_set_style_bg_color(root, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(root, LV_OPA_COVER, 0);

    /* —— 全屏皮肤底图：提供全部静态装饰 —— */
    lv_obj_t* skin = lv_img_create(root);
    if(skin == nullptr)
    {
        return;
    }
    lv_img_set_src(skin, IMG("dialplate_skin"));
    lv_obj_set_pos(skin, 0, 0);
    /* 不可点击/不滚动：让手势与点击穿透到 root（Dialplate 在 root 上识别左右滑） */
    lv_obj_clear_flag(skin, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(skin, LV_OBJ_FLAG_SCROLLABLE);
    ui.skin = skin;

    const void* arrowSrc = IMG("gps_arrow_light");
    if(arrowSrc != nullptr)
    {
        lv_obj_t* arrow = lv_img_create(root);
        if(arrow != nullptr)
        {
            lv_img_set_src(arrow, arrowSrc);
            lv_obj_set_pos(arrow, ARROW_CENTER_X - ARROW_PIVOT_X,
                           ARROW_CENTER_Y - ARROW_PIVOT_Y);
            lv_img_set_pivot(arrow, ARROW_PIVOT_X, ARROW_PIVOT_Y);
            lv_img_set_angle(arrow, 0);
            lv_obj_clear_flag(arrow, LV_OBJ_FLAG_CLICKABLE);
            lv_obj_clear_flag(arrow, LV_OBJ_FLAG_SCROLLABLE);
            ui.arrow.img = arrow;
            ui.arrow.angle = 0;
        }
    }

    /* —— 顶部：GPS / 蓝牙 / 心率 / 电量 / 坡度；海拔移到右侧 AVG 上方 —— */
    ui.status.labelHr    = Value_Create(root, FONT("bahnschrift_13"), COL_WHITE, LV_ALIGN_TOP_LEFT,   24,  52, "95");
    ui.status.labelAlt   = Value_Create(root, FONT("bahnschrift_13"), COL_WHITE, LV_ALIGN_TOP_LEFT,  198,  61, "532");
    SetFixedLabelBox(ui.status.labelAlt, 28, 14, LV_TEXT_ALIGN_RIGHT);
    ui.status.labelAltUnit = OverlayLabel(root, FONT("bahnschrift_13"), COL_GRAY, 226, 61, "m");
    ui.status.labelBattery = Value_Create(root, FONT("bahnschrift_13"), COL_WHITE, LV_ALIGN_TOP_LEFT, 212, 8, "100");
    SetFixedLabelBox(ui.status.labelBattery, 24, 14, LV_TEXT_ALIGN_LEFT);
    ui.status.labelSlope = Value_Create(root, FONT("bahnschrift_13"), COL_YELLOW, LV_ALIGN_TOP_RIGHT,  -9,  30, "3.2%");

    ui.status.imgGps = OverlayImg(root, "satellite", COL_GREEN, 7, 12);
    ui.status.labelGpsSat = Value_Create(root, FONT("bahnschrift_13"), COL_WHITE, LV_ALIGN_TOP_LEFT, 25, 11, "0");
    OverlayBox(root, 5, 28, 17, 16, lv_color_black(), LV_OPA_COVER, 0);
    ui.status.imgBt = OverlayImg(root, "bluetooth", COL_GRAY, 7, 28);
    OverlayBox(root, 4, 46, 19, 13, lv_color_black(), LV_OPA_COVER, 0);
    OverlayLabel(root, FONT("iconfont_20"), COL_REC_RED, 4, 45, ICON_HEART_RATE);
    SetBluetoothConnected(false);
    ui.status.imgBattery = OverlayImg(root, "battery", COL_BLUE, 201, 7);
    SetBattery(100, false);
    ui.status.labelAltIcon = OverlayLabel(root, FONT("iconfont_20"), COL_BLUE, 181, 56, ICON_ALTITUDE);
    SetAltitude(532);
    OverlayLabel(root, FONT("iconfont_16"), COL_YELLOW, 184, 29, ICON_CLIMB);

    /* —— 导航距离(占位)：大号数字(纯数字字库) + 小号单位 m(全字库) —— */
    ui.nav.labelDist = Value_Create(root, FONT("bahnschrift_24"), COL_WHITE, LV_ALIGN_TOP_LEFT, 99, 10, "320");
    ui.nav.labelDistUnit = lv_label_create(root);
    if (ui.nav.labelDistUnit)
    {
        lv_obj_set_style_text_font(ui.nav.labelDistUnit, FONT("bahnschrift_13"), 0);
        lv_obj_set_style_text_color(ui.nav.labelDistUnit, COL_GRAY, 0);
        lv_label_set_text(ui.nav.labelDistUnit, "m");
        lv_obj_set_pos(ui.nav.labelDistUnit, 142, 15);
        lv_obj_clear_flag(ui.nav.labelDistUnit, LV_OBJ_FLAG_CLICKABLE);
    }

    ui.nav.labelTurnIcon = OverlayLabel(root, FONT("iconfont_20"), COL_GREEN, 68, 18, ICON_TURN_RIGHT);
    ui.nav.labelTurnText = OverlayLabel(root, FONT("cn_16"), COL_GREEN, 104, 30, TXT_TURN_RIGHT);
    SetTurnDirection(TURN_RIGHT);

    /* —— 速度(真实)：左侧大号数字 —— */
    ui.speed.labelValue = Value_Create(root, FONT("bahnschrift_48"), COL_WHITE, LV_ALIGN_TOP_LEFT, 10, 91, "0.0");
    OverlayLabel(root, FONT("bahnschrift_13"), COL_CYAN, 11, 78, "SPEED");
    OverlayLabel(root, FONT("bahnschrift_17"), COL_CYAN, 10, 134, "KM/H");

    /* —— MAX 最高速(真实)：标题/数值均收进左下 MAX 框内 —— */
    Spectrum_Create(root);
    ui.maxBar.labelTitle = OverlayLabel(root, FONT("montserrat_8"), COL_CYAN, MAX_LABEL_X, MAX_TITLE_Y, "MAX");
    SetFixedLabelBox(ui.maxBar.labelTitle, MAX_VALUE_W, 9, LV_TEXT_ALIGN_CENTER);
    ui.maxBar.labelMax = Value_Create(root, FONT("agencyb_12"), COL_WHITE,
                                      LV_ALIGN_TOP_LEFT, MAX_LABEL_X, MAX_VALUE_Y, "0.0");
    SetFixedLabelBox(ui.maxBar.labelMax, MAX_VALUE_W, 11, LV_TEXT_ALIGN_CENTER);

    /* Keep number and unit slots separate; creation and updates share these bounds. */
    const lv_color_t  mcl[METRIC_NUM]  = { COL_WHITE, COL_WHITE, COL_WHITE, COL_WHITE };
    const char*       miv[METRIC_NUM]  = { "0.0", "0:00:00", "0.0", "0" };
    for (int i = 0; i < METRIC_NUM; i++)
    {
        const DialplateMetricLayout& layout = metricLayouts[i];
        ui.metrics.item[i].labelValue =
            Value_Create(root, FONT(layout.fonts[0]), mcl[i], LV_ALIGN_TOP_LEFT, layout.x, layout.y, miv[i]);
        SetMetricText((uint8_t)i, miv[i]);
    }
    OverlayOutline(root, 182, 82, 8, 8, COL_BLUE, 1);
    OverlayBox(root, 184, 87, 2, 2, COL_BLUE);
    OverlayBox(root, 188, 84, 2, 5, COL_BLUE);
    OverlayLabel(root, FONT("bahnschrift_13"), COL_BLUE, 194, 78, "AVG");
    OverlayLabel(root, FONT("bahnschrift_13"), COL_BLUE, 208, 94, "KPH");

    OverlayOutline(root, 182, 124, 8, 8, COL_BLUE, LV_RADIUS_CIRCLE);
    OverlayBox(root, 186, 125, 1, 4, COL_BLUE);
    OverlayBox(root, 187, 128, 3, 1, COL_BLUE);
    OverlayLabel(root, FONT("bahnschrift_13"), COL_BLUE, 194, 121, "TIME");

    OverlayBox(root, 182, 169, 3, 3, COL_BLUE, LV_OPA_COVER, LV_RADIUS_CIRCLE);
    OverlayBox(root, 187, 172, 3, 3, COL_BLUE, LV_OPA_COVER, LV_RADIUS_CIRCLE);
    OverlayBox(root, 183, 177, 7, 2, COL_BLUE, LV_OPA_COVER, 1);
    OverlayLabel(root, FONT("bahnschrift_13"), COL_BLUE, 194, 166, "TRIP");
    OverlayLabel(root, FONT("bahnschrift_13"), COL_BLUE, 214, 184, "KM");

    OverlayOutline(root, 182, 214, 8, 8, COL_YELLOW, LV_RADIUS_CIRCLE);
    OverlayBox(root, 185, 211, 2, 8, COL_YELLOW, LV_OPA_COVER, 1);
    OverlayLabel(root, FONT("bahnschrift_13"), COL_YELLOW, 194, 211, "CAL");
    lv_obj_t* calUnit = OverlayLabel(root, FONT("bahnschrift_13"), COL_YELLOW, 180, 247, "KCAL");
    SetFixedLabelBox(calUnit, 54, 14, LV_TEXT_ALIGN_CENTER);

    /* —— 路点标签(占位)：叠加在地图空白区，沿用 2.png 文案，待导航引擎/手机 App 更新 —— */
    Value_Create(root, FONT("bahnschrift_13"), COL_WHITE, LV_ALIGN_TOP_LEFT, 126, 73,  "SPRING");
    Value_Create(root, FONT("bahnschrift_13"), COL_GRAY,  LV_ALIGN_TOP_LEFT, 126, 85,  "2.4km");
    Value_Create(root, FONT("bahnschrift_13"), COL_WHITE, LV_ALIGN_TOP_LEFT, 62, 155, "BRIDGE");
    Value_Create(root, FONT("bahnschrift_13"), COL_GRAY,  LV_ALIGN_TOP_LEFT, 62, 167, "1.2km");

    /* —— 底部三按钮：透明可聚焦，叠加在皮肤烘焙按钮栏之上 —— */
    lv_style_init(&styleBtn);
    lv_style_set_bg_opa(&styleBtn, LV_OPA_TRANSP);
    lv_style_set_border_width(&styleBtn, 0);
    lv_style_set_radius(&styleBtn, 7);
    lv_style_set_pad_all(&styleBtn, 0);

    lv_style_init(&styleBtnFocus);
    lv_style_set_border_color(&styleBtnFocus, COL_CYAN);
    lv_style_set_border_width(&styleBtnFocus, 2);
    lv_style_set_border_opa(&styleBtnFocus, LV_OPA_COVER);
    lv_style_set_bg_opa(&styleBtnFocus, LV_OPA_20);
    lv_style_set_bg_color(&styleBtnFocus, COL_CYAN);

    ui.btnCont.btnMap  = Btn_Create(root, 8,   286, 72, 30);
    ui.btnCont.btnRec  = Btn_Create(root, 86,  286, 68, 30);
    ui.btnCont.btnMenu = Btn_Create(root, 160, 286, 72, 30);

    OverlayLabel(ui.btnCont.btnMap, FONT("iconfont_20"), COL_CYAN, 12, 5, ICON_MAP);
    OverlayLabel(ui.btnCont.btnMap, FONT("cn_16"), COL_CYAN, 32, 6, TXT_MAP);

    /* REC 文本/图标使用 LVGL 自绘，状态变化时只改变前置圆点颜色。 */
    ui.btnCont.recContent = lv_obj_create(ui.btnCont.btnRec);
    lv_obj_remove_style_all(ui.btnCont.recContent);
    lv_obj_set_size(ui.btnCont.recContent, 38, 14);
    lv_obj_center(ui.btnCont.recContent);
    lv_obj_clear_flag(ui.btnCont.recContent, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(ui.btnCont.recContent, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(ui.btnCont.recContent, COL_PANEL_BG, 0);
    lv_obj_set_style_bg_opa(ui.btnCont.recContent, LV_OPA_TRANSP, 0);
    lv_obj_set_style_radius(ui.btnCont.recContent, 5, 0);

    ui.btnCont.recDot = lv_obj_create(ui.btnCont.recContent);
    lv_obj_remove_style_all(ui.btnCont.recDot);
    lv_obj_set_size(ui.btnCont.recDot, 5, 5);
    lv_obj_set_pos(ui.btnCont.recDot, 2, 5);
    lv_obj_clear_flag(ui.btnCont.recDot, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(ui.btnCont.recDot, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_radius(ui.btnCont.recDot, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_opa(ui.btnCont.recDot, LV_OPA_COVER, 0);

    ui.btnCont.recLabel = lv_label_create(ui.btnCont.recContent);
    lv_obj_set_style_text_font(ui.btnCont.recLabel, FONT("bahnschrift_13"), 0);
    lv_obj_set_style_text_color(ui.btnCont.recLabel, COL_WHITE, 0);
    lv_label_set_text(ui.btnCont.recLabel, "REC");
    lv_obj_set_pos(ui.btnCont.recLabel, 11, 0);
    lv_obj_clear_flag(ui.btnCont.recLabel, LV_OBJ_FLAG_CLICKABLE);

    SetRecRecording(false);

    OverlayLabel(ui.btnCont.btnMenu, FONT("iconfont_20"), COL_BLUE, 12, 5, ICON_MENU);
    OverlayLabel(ui.btnCont.btnMenu, FONT("cn_16"), COL_BLUE, 32, 6, TXT_MENU);
}

void DialplateView::Delete()
{
#if DIALPLATE_HW_EFFECTS
    BorderGlow_SetActive(false);
#endif
    if(ui.maxBar.spectrumTimer != nullptr)
    {
        lv_timer_del(ui.maxBar.spectrumTimer);
        ui.maxBar.spectrumTimer = nullptr;
    }

    lv_style_reset(&styleBtn);
    lv_style_reset(&styleBtnFocus);
    memset(&ui, 0, sizeof(ui));
}

void DialplateView::AppearAnimStart(bool reverse)
{
    SetSpectrumActive(!reverse);

    /* 轻量淡入整页（皮肤+叠加层），reverse 时不处理（退场由页面管理器负责） */
    if (!reverse && ui.skin)
    {
        lv_obj_fade_in(lv_obj_get_parent(ui.skin), 250, 0);
    }
}

void DialplateView::SetSpectrumActive(bool active)
{
    if(ui.maxBar.spectrumTimer == nullptr)
    {
        return;
    }

    if(active)
    {
#if DIALPLATE_HW_EFFECTS
        BorderGlow_SetActive(true);
#endif
        lv_timer_resume(ui.maxBar.spectrumTimer);
        lv_timer_ready(ui.maxBar.spectrumTimer);
    }
    else
    {
        lv_timer_pause(ui.maxBar.spectrumTimer);
#if DIALPLATE_HW_EFFECTS
        BorderGlow_SetActive(false);
#endif
    }
}

void DialplateView::SetSpectrumSpeed(float speedKph)
{
    if(!std::isfinite(speedKph))
    {
        speedKph = 0.0f;
    }
    if(speedKph < 0.0f)
    {
        speedKph = -speedKph;
    }

    uint8_t level = SPECTRUM_MIN_LEVEL_PCT;
    if(speedKph >= SPECTRUM_FULL_SPEED_KPH)
    {
        level = SPECTRUM_MAX_LEVEL_PCT;
    }
    else
    {
        level = (uint8_t)(SPECTRUM_MIN_LEVEL_PCT +
                 speedKph * (SPECTRUM_MAX_LEVEL_PCT - SPECTRUM_MIN_LEVEL_PCT) / SPECTRUM_FULL_SPEED_KPH + 0.5f);
    }

    if(level < SPECTRUM_MIN_LEVEL_PCT)
    {
        level = SPECTRUM_MIN_LEVEL_PCT;
    }
    else if(level > SPECTRUM_MAX_LEVEL_PCT)
    {
        level = SPECTRUM_MAX_LEVEL_PCT;
    }

    ui.maxBar.spectrumLevelPct = level;
}

void DialplateView::SetMetricText(uint8_t index, const char* text)
{
    if(index >= METRIC_NUM || text == nullptr || ui.metrics.item[index].labelValue == nullptr)
    {
        return;
    }

    const DialplateMetricLayout& layout = metricLayouts[index];
    const lv_font_t* font = FONT(layout.fonts[layout.fontCount - 1]);
    bool fits = false;
    for(uint8_t i = 0; i < layout.fontCount; i++)
    {
        const lv_font_t* candidate = FONT(layout.fonts[i]);
        if(candidate == nullptr)
        {
            continue;
        }
        lv_point_t size;
        lv_txt_get_size(&size, text, candidate, 0, 0, LV_COORD_MAX, LV_TEXT_FLAG_NONE);
        if(size.x <= layout.width && size.y <= layout.height)
        {
            font = candidate;
            fits = true;
            break;
        }
    }
    if(font == nullptr)
    {
        return;
    }

    lv_obj_t* label = ui.metrics.item[index].labelValue;
    lv_obj_set_style_text_font(label, font, 0);
    lv_label_set_long_mode(label, fits ? LV_LABEL_LONG_CLIP : LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_label_set_text(label, text);
    lv_obj_set_size(label, layout.width, layout.height);
    lv_obj_set_style_text_align(label, layout.align, 0);
    lv_obj_align(label, LV_ALIGN_TOP_LEFT, layout.x, layout.y);
}

void DialplateView::SetArrowAngle(float deg)
{
    if(ui.arrow.img == nullptr || !std::isfinite(deg))
    {
        return;
    }

    deg = std::fmod(deg, 360.0f);
    if(deg < 0.0f)
    {
        deg += 360.0f;
    }
    int16_t angle = (int16_t)(deg * 10.0f + 0.5f);
    if(angle >= 3600)
    {
        angle -= 3600;
    }
    int16_t diff = angle - ui.arrow.angle;
    if(diff > 1800) diff -= 3600;
    else if(diff < -1800) diff += 3600;

    if(ui.arrow.angle < 0 || diff <= -10 || diff >= 10)
    {
        lv_img_set_angle(ui.arrow.img, angle);
        ui.arrow.angle = angle;
    }
}

void DialplateView::SetRecRecording(bool active)
{
    if(ui.btnCont.recDot == nullptr)
    {
        return;
    }

    lv_color_t dotColor = active ? COL_REC_RED : COL_WHITE;

    lv_obj_set_style_bg_color(ui.btnCont.recDot, dotColor, 0);
}

void DialplateView::SetBluetoothConnected(bool connected)
{
    if(ui.status.imgBt == nullptr)
    {
        return;
    }

    lv_color_t color = connected ? COL_BLUE : COL_GRAY;

    lv_obj_set_style_img_recolor(ui.status.imgBt, color, 0);
    lv_obj_set_style_img_recolor_opa(ui.status.imgBt, LV_OPA_COVER, 0);
}

void DialplateView::SetBattery(uint8_t usage, bool charging)
{
    if(ui.status.labelBattery == nullptr)
    {
        return;
    }

    if (usage > 100)
    {
        usage = 100;
    }

    lv_color_t color = charging ? COL_GREEN : (usage <= 20 ? COL_YELLOW : COL_BLUE);

    if(ui.status.imgBattery)
    {
        lv_obj_set_style_img_recolor(ui.status.imgBattery, color, 0);
        lv_obj_set_style_img_recolor_opa(ui.status.imgBattery, LV_OPA_COVER, 0);
    }
    lv_obj_set_style_text_color(ui.status.labelBattery, color, 0);
    lv_label_set_text_fmt(ui.status.labelBattery, "%u", (unsigned)usage);
    lv_obj_set_pos(ui.status.labelBattery, 212, 8);
}

void DialplateView::SetAltitude(int altitude)
{
    if(ui.status.labelAlt == nullptr)
    {
        return;
    }

    char text[16];
    snprintf(text, sizeof(text), "%d", altitude);

    lv_obj_set_style_text_font(ui.status.labelAlt, FONT("bahnschrift_13"), 0);
    lv_label_set_text(ui.status.labelAlt, text);
    lv_obj_set_pos(ui.status.labelAlt, 196, 61);
    if(ui.status.labelAltUnit)
    {
        lv_obj_set_pos(ui.status.labelAltUnit, 226, 61);
    }
    if(ui.status.labelAltIcon)
    {
        lv_obj_set_pos(ui.status.labelAltIcon, 181, 56);
    }
}

void DialplateView::SetTurnDirection(TurnDirection_t dir)
{
    const char* icon = ICON_TURN_RIGHT;
    const char* text = TXT_TURN_RIGHT;

    if (dir == TURN_LEFT)
    {
        icon = ICON_TURN_LEFT;
        text = TXT_TURN_LEFT;
    }
    else if (dir == TURN_STRAIGHT)
    {
        icon = ICON_TURN_STRAIGHT;
        text = TXT_TURN_STRAIGHT;
    }

    if(ui.nav.labelTurnIcon)
    {
        lv_label_set_text(ui.nav.labelTurnIcon, icon);
    }
    if(ui.nav.labelTurnText)
    {
        lv_label_set_text(ui.nav.labelTurnText, text);
    }
}

void DialplateView::Spectrum_Create(lv_obj_t* par)
{
    if(par == nullptr)
    {
        return;
    }

    ui.maxBar.spectrumMask = OverlayBox(par, SPECTRUM_MASK_X, SPECTRUM_MASK_Y,
                                        SPECTRUM_MASK_W, SPECTRUM_MASK_H,
                                        COL_PANEL_BG, LV_OPA_COVER, 0);

#if !DIALPLATE_HW_EFFECTS
    const lv_coord_t segW = 7;
    const lv_coord_t gap = 2;
    const lv_coord_t baseY = SPECTRUM_Y + SPECTRUM_H;
    for(int i = 0; i < SPECTRUM_BAR_NUM; i++)
    {
        for(int s = 0; s < SPECTRUM_SEG_NUM; s++)
        {
            lv_obj_t* seg = lv_obj_create(par);
            if(seg == nullptr)
            {
                continue;
            }

            lv_obj_remove_style_all(seg);
            lv_obj_set_size(seg, segW, SPECTRUM_SEG_H);
            lv_obj_set_pos(seg,
                           SPECTRUM_X + i * (segW + gap),
                           baseY - (s + 1) * SPECTRUM_SEG_H - s * SPECTRUM_SEG_GAP);
            lv_obj_set_style_bg_color(seg, COL_CYAN, 0);
            lv_obj_set_style_bg_opa(seg, LV_OPA_TRANSP, 0);
            lv_obj_set_style_radius(seg, 0, 0);
            lv_obj_clear_flag(seg, LV_OBJ_FLAG_CLICKABLE);
            lv_obj_clear_flag(seg, LV_OBJ_FLAG_SCROLLABLE);
            ui.maxBar.spectrumSegs[i][s] = seg;
        }
    }
#endif

    ui.maxBar.spectrumPhase = 0;
    ui.maxBar.spectrumLevelPct = SPECTRUM_MIN_LEVEL_PCT;
    for(int i = 0; i < SPECTRUM_BAR_NUM; i++)
    {
        ui.maxBar.spectrumLit[i] = 0xff;
    }
    Spectrum_Update();
    ui.maxBar.spectrumTimer = lv_timer_create(onSpectrumTimer, 50, this);
    if(ui.maxBar.spectrumTimer)
    {
        lv_timer_pause(ui.maxBar.spectrumTimer);
    }
}

void DialplateView::Spectrum_Update()
{
    const uint8_t frameCount = sizeof(spectrumFrames) / sizeof(spectrumFrames[0]);
    const uint8_t* frame = spectrumFrames[ui.maxBar.spectrumPhase % frameCount];

#if DIALPLATE_HW_EFFECTS
    if(EffectsCanBlit())
    {
        BorderGlow_Advance();
        Spectrum_Blit(frame);
    }
#endif

    if(ui.nav.labelTurnIcon != nullptr)
    {
        static const lv_opa_t pulse[] =
        {
            LV_OPA_70, LV_OPA_80, LV_OPA_90, LV_OPA_COVER,
            LV_OPA_COVER, LV_OPA_90, LV_OPA_80, LV_OPA_70
        };
        lv_obj_set_style_text_opa(ui.nav.labelTurnIcon,
            pulse[ui.maxBar.spectrumPhase % (sizeof(pulse) / sizeof(pulse[0]))], 0);
    }

#if !DIALPLATE_HW_EFFECTS
    for(int i = 0; i < SPECTRUM_BAR_NUM; i++)
    {
        uint8_t lit = (uint8_t)(((uint16_t)frame[i] * ui.maxBar.spectrumLevelPct + 99U) / 100U);
        if(lit == 0)
        {
            lit = 1;
        }
        if(lit > SPECTRUM_SEG_NUM)
        {
            lit = SPECTRUM_SEG_NUM;
        }
        if(ui.maxBar.spectrumLit[i] == lit)
        {
            continue;
        }
        ui.maxBar.spectrumLit[i] = lit;

        for(int s = 0; s < SPECTRUM_SEG_NUM; s++)
        {
            lv_obj_t* seg = ui.maxBar.spectrumSegs[i][s];
            if(seg == nullptr)
            {
                continue;
            }

            if(s < lit)
            {
                lv_obj_set_style_bg_opa(seg, (s + 1 == lit) ? LV_OPA_COVER : LV_OPA_80, 0);
            }
            else
            {
                lv_obj_set_style_bg_opa(seg, LV_OPA_TRANSP, 0);
            }
        }
    }
#endif

    ui.maxBar.spectrumPhase++;
}

#if DIALPLATE_HW_EFFECTS
bool DialplateView::EffectsCanBlit() const
{
    if(!ui.borderGlowActive || ui.skin == nullptr || !lv_obj_is_visible(ui.skin))
    {
        return false;
    }
    lv_obj_t* root = lv_obj_get_parent(ui.skin);
    if(root == nullptr || lv_obj_get_parent(root) != lv_scr_act() ||
       lv_obj_get_style_opa(root, 0) != LV_OPA_COVER)
    {
        return false;
    }
    lv_area_t bounds;
    lv_obj_get_coords(root, &bounds);
    if(bounds.x1 != 0 || bounds.y1 != 0 || bounds.x2 != SCR_W - 1 || bounds.y2 != SCR_H - 1)
    {
        return false;
    }

    /* Raw DMA bypasses LVGL z-order. Never paint over a modal or a newer page. */
    lv_obj_t* top = lv_layer_top();
    for(uint32_t i = 0; i < lv_obj_get_child_cnt(top); i++)
    {
        if(lv_obj_is_visible(lv_obj_get_child(top, (int32_t)i)))
        {
            return false;
        }
    }
    lv_obj_t* screen = lv_scr_act();
    for(uint32_t i = lv_obj_get_index(root) + 1; i < lv_obj_get_child_cnt(screen); i++)
    {
        if(lv_obj_is_visible(lv_obj_get_child(screen, (int32_t)i)))
        {
            return false;
        }
    }
    return true;
}

void DialplateView::Spectrum_Blit(const uint8_t* frame)
{
    if(frame == nullptr)
    {
        return;
    }
    uint8_t lit[SPECTRUM_BAR_NUM];
    SpectrumLevels(frame, ui.maxBar.spectrumLevelPct, lit);
    for(lv_coord_t y = 0; y < SPECTRUM_H; y += SPECTRUM_ROWS_PER_BLIT)
    {
        const lv_coord_t rows = SPECTRUM_H - y < SPECTRUM_ROWS_PER_BLIT ?
                                SPECTRUM_H - y : SPECTRUM_ROWS_PER_BLIT;
        for(lv_coord_t row = 0; row < rows; row++)
        {
            for(lv_coord_t x = 0; x < SPECTRUM_W; x++)
            {
                effectBuffer[row * SPECTRUM_W + x] = SpectrumColor(x, y + row, lit);
            }
        }
        const lv_area_t area = { SPECTRUM_X, (lv_coord_t)(SPECTRUM_Y + y),
                                SPECTRUM_X + SPECTRUM_W - 1, (lv_coord_t)(SPECTRUM_Y + y + rows - 1) };
        lv_port_disp_blit_blocking(&area, effectBuffer);
    }
}

void DialplateView::Spectrum_Compose(const lv_area_t* area, lv_color_t* colors)
{
    const lv_coord_t x1 = area->x1 > SPECTRUM_X ? area->x1 : SPECTRUM_X;
    const lv_coord_t y1 = area->y1 > SPECTRUM_Y ? area->y1 : SPECTRUM_Y;
    const lv_coord_t x2 = area->x2 < SPECTRUM_X + SPECTRUM_W - 1 ? area->x2 : SPECTRUM_X + SPECTRUM_W - 1;
    const lv_coord_t y2 = area->y2 < SPECTRUM_Y + SPECTRUM_H - 1 ? area->y2 : SPECTRUM_Y + SPECTRUM_H - 1;
    if(x2 < x1 || y2 < y1)
    {
        return;
    }
    /* Update advances the phase after painting; compose the last displayed frame. */
    const uint8_t phase = (uint8_t)(ui.maxBar.spectrumPhase - 1U);
    const uint8_t frameCount = sizeof(spectrumFrames) / sizeof(spectrumFrames[0]);
    uint8_t lit[SPECTRUM_BAR_NUM];
    SpectrumLevels(spectrumFrames[phase % frameCount], ui.maxBar.spectrumLevelPct, lit);
    const lv_coord_t areaWidth = area->x2 - area->x1 + 1;
    for(lv_coord_t y = y1; y <= y2; y++)
    {
        for(lv_coord_t x = x1; x <= x2; x++)
        {
            colors[(y - area->y1) * areaWidth + x - area->x1] =
                SpectrumColor(x - SPECTRUM_X, y - SPECTRUM_Y, lit);
        }
    }
}

void DialplateView::BorderGlow_SetActive(bool active)
{
    if(!active && ui.borderGlowActive)
    {
        BorderGlow_BlitFrame(ui.borderGlowPhase, false);
    }
    if(active && !ui.borderGlowActive)
    {
        ui.borderGlowPhase = 0;
    }
    ui.borderGlowActive = active;
    lv_port_disp_set_overlay_cb(active ? onDisplayOverlay : nullptr, active ? this : nullptr);
}

void DialplateView::BorderGlow_Advance()
{
    const uint8_t oldPhase = ui.borderGlowPhase % DIALPLATE_GLOW_FRAME_COUNT;
    BorderGlow_BlitFrame(oldPhase, false);
    ui.borderGlowPhase = (uint8_t)((oldPhase + 1U) % DIALPLATE_GLOW_FRAME_COUNT);
    BorderGlow_BlitFrame(ui.borderGlowPhase, true);
}

void DialplateView::BorderGlow_BlitFrame(uint8_t phase, bool glow)
{
    if(!EffectsCanBlit())
    {
        return;
    }
    const lv_img_dsc_t* skin = (const lv_img_dsc_t*)lv_img_get_src(ui.skin);
    if(skin == nullptr || skin->data == nullptr || skin->header.w != SCR_W ||
       skin->header.h != SCR_H || skin->header.cf != LV_IMG_CF_TRUE_COLOR ||
       skin->data_size < SCR_W * SCR_H * sizeof(lv_color_t))
    {
        return;
    }

    lv_color_t* buffer = effectBuffer;
    const lv_color_t* base = (const lv_color_t*)skin->data;
    const DialplateGlowFrame& glowFrame = kDialplateGlowFrames[phase % DIALPLATE_GLOW_FRAME_COUNT];
    const DialplateGlowSegmentFrame& segmentFrame = kDialplateGlowSegmentFrames[phase % DIALPLATE_GLOW_FRAME_COUNT];
    for(uint16_t segmentIndex = 0; segmentIndex < segmentFrame.count; segmentIndex++)
    {
        const lv_area_t& area = segmentFrame.segments[segmentIndex].area;
        const lv_coord_t width = area.x2 - area.x1 + 1;
        const lv_coord_t height = area.y2 - area.y1 + 1;
        if(width <= 0 || height <= 0 || width * height > DIALPLATE_GLOW_BLIT_MAX_PIXELS ||
           area.x1 < 0 || area.y1 < 0 || area.x2 >= SCR_W || area.y2 >= SCR_H)
        {
            continue;
        }
        for(lv_coord_t row = 0; row < height; row++)
        {
            memcpy(&buffer[row * width], &base[(area.y1 + row) * SCR_W + area.x1],
                   (size_t)width * sizeof(lv_color_t));
        }
        if(glow)
        {
            for(uint16_t pixelIndex = 0; pixelIndex < glowFrame.count; pixelIndex++)
            {
                const DialplateGlowPixel& pixel = glowFrame.pixels[pixelIndex];
                const lv_coord_t x = (lv_coord_t)(pixel.index % SCR_W);
                const lv_coord_t y = (lv_coord_t)(pixel.index / SCR_W);
                if(x >= area.x1 && x <= area.x2 && y >= area.y1 && y <= area.y2)
                {
                    buffer[(y - area.y1) * width + (x - area.x1)] =
                        lv_color_make(pixel.r, pixel.g, pixel.b);
                }
            }
        }
        lv_port_disp_blit_blocking(&area, buffer);
    }
}

void DialplateView::onDisplayOverlay(const lv_area_t* area, lv_color_t* color_p, void* userData)
{
    DialplateView* instance = (DialplateView*)userData;
    if(instance == nullptr || area == nullptr || color_p == nullptr || !instance->EffectsCanBlit())
    {
        return;
    }
    const DialplateGlowFrame& frame =
        kDialplateGlowFrames[instance->ui.borderGlowPhase % DIALPLATE_GLOW_FRAME_COUNT];
    const lv_coord_t width = area->x2 - area->x1 + 1;
    for(uint16_t i = 0; i < frame.count; i++)
    {
        const DialplateGlowPixel& pixel = frame.pixels[i];
        const lv_coord_t x = (lv_coord_t)(pixel.index % SCR_W);
        const lv_coord_t y = (lv_coord_t)(pixel.index / SCR_W);
        if(x >= area->x1 && x <= area->x2 && y >= area->y1 && y <= area->y2)
        {
            color_p[(y - area->y1) * width + (x - area->x1)] = lv_color_make(pixel.r, pixel.g, pixel.b);
        }
    }
    /* Full and partial LVGL repaints must retain the direct spectrum too. */
    instance->Spectrum_Compose(area, color_p);
}
#endif

void DialplateView::onSpectrumTimer(lv_timer_t* timer)
{
    if(timer == nullptr || timer->user_data == nullptr)
    {
        return;
    }

    DialplateView* instance = (DialplateView*)timer->user_data;
    instance->Spectrum_Update();
}

/*=========================
 *  叠加数值标签
 *=========================*/
lv_obj_t* DialplateView::Value_Create(lv_obj_t* par, const lv_font_t* font, lv_color_t color,
                                      lv_align_t align, lv_coord_t x, lv_coord_t y, const char* init)
{
    lv_obj_t* label = lv_label_create(par);
    if(label == nullptr)
    {
        return nullptr;
    }
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, color, 0);
    lv_label_set_text(label, init);
    lv_obj_align(label, align, x, y);
    return label;
}

/*=========================
 *  透明可聚焦按钮
 *=========================*/
lv_obj_t* DialplateView::Btn_Create(lv_obj_t* par, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h)
{
    lv_obj_t* obj = lv_obj_create(par);
    if(obj == nullptr)
    {
        return nullptr;
    }
    lv_obj_remove_style_all(obj);
    lv_obj_set_size(obj, w, h);
    lv_obj_set_pos(obj, x, y);
    lv_obj_clear_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_style(obj, &styleBtn, 0);
    lv_obj_add_style(obj, &styleBtnFocus, LV_STATE_FOCUSED);
    return obj;
}
