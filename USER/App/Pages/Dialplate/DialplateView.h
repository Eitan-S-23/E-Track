#ifndef __DIALPLATE_VIEW_H
#define __DIALPLATE_VIEW_H

#include "../Page.h"

namespace Page
{

/*
 * DialplateView —— 复刻 generated-images/2.png 的赛博 HUD 默认表盘。
 * 竖屏 240x320。策略：全屏烘焙皮肤底图 img_src_dialplate_skin（RGB565 Flash 常量，
 * 由 image2 生成、清空全部动态数值槽位与小字号文字图标）提供静态装饰——地图纹理 /
 * 切角面板 / 霓虹路线 / 底部按钮外观。本类只负责：
 *   1) 在皮肤的空数值槽位上叠加动态文本（speed/max/avg/time/trip/cal/altitude 真实数据，
 *      心率/坡度/导航距离为占位，默认沿用 2.png，待手机 App 更新）；
 *   2) 用 LVGL 自绘标题、单位、小图标和底部 MAP/REC/MENU 内容，避免图片缩放发糊；
 *   3) 在底部按钮栏上叠加可交互、可聚焦的透明按钮。
 * 皮肤为 TRUE_COLOR 常量，直接从 Flash 逐区块渲染，无 PNG 解码、无全屏 RAM 帧缓冲；
 * 仅动态文本所在的小区域随刷新重绘，帧率影响有限。
 */
class DialplateView
{
public:
    /* 右栏指标项：仅持有数值标签，名称/图标/单位由 LVGL 叠加绘制 */
    typedef struct
    {
        lv_obj_t* labelValue;
    } MetricItem_t;

    /* 指标项数：AVG / TIME / TRIP / CAL */
    enum { METRIC_NUM = 4 };
    enum { SPECTRUM_BAR_NUM = 3, SPECTRUM_SEG_NUM = 16 };

    typedef enum
    {
        TURN_LEFT,
        TURN_RIGHT,
        TURN_STRAIGHT
    } TurnDirection_t;

public:
    DialplateView();

    struct
    {
        lv_obj_t* skin;       /* 全屏皮肤底图 */

        /* 顶部状态：心率(占位) / 海拔(真实) / 坡度(占位) */
        struct
        {
            lv_obj_t* imgGps;
            lv_obj_t* imgBt;
            lv_obj_t* imgBattery;
            lv_obj_t* labelHr;
            lv_obj_t* labelAlt;
            lv_obj_t* labelAltUnit;
            lv_obj_t* labelBattery;
            lv_obj_t* labelSlope;
            lv_obj_t* labelGpsSat;
            lv_obj_t* labelAltIcon;
        } status;

        /* 导航距离(占位)：大号数字 + 小号单位 */
        struct
        {
            lv_obj_t* labelDist;
            lv_obj_t* labelDistUnit;
            lv_obj_t* labelTurnIcon;
            lv_obj_t* labelTurnText;
        } nav;

        /* 速度(真实) */
        struct
        {
            lv_obj_t* labelValue;
        } speed;

        /* MAX 最高速(真实) */
        struct
        {
            lv_obj_t* spectrumMask;
            lv_obj_t* spectrumSegs[SPECTRUM_BAR_NUM][SPECTRUM_SEG_NUM];
            lv_timer_t* spectrumTimer;
            uint8_t spectrumPhase;
            uint8_t spectrumLevelPct;
            uint8_t spectrumLit[SPECTRUM_BAR_NUM];
            lv_obj_t* labelTitle;
            lv_obj_t* labelMax;
        } maxBar;

        /* 右栏指标(真实)：AVG / TIME / TRIP / CAL */
        struct
        {
            MetricItem_t item[METRIC_NUM];
        } metrics;

        /* 底部按钮：透明可聚焦，叠加在皮肤烘焙按钮栏之上 */
        struct
        {
            lv_obj_t* btnMap;
            lv_obj_t* btnRec;
            lv_obj_t* btnMenu;
            lv_obj_t* recContent;
            lv_obj_t* recDot;    /* REC 前置录制点，自绘圆形；运行录制时变红 */
            lv_obj_t* recLabel;
        } btnCont;
    } ui;

    void Create(lv_obj_t* root);
    void Delete();
    void AppearAnimStart(bool reverse = false);
    void SetSpectrumActive(bool active);
    void SetSpectrumSpeed(float speedKph);

    /* 当前位置三角由皮肤提供；接口保留给 Presenter 调用。 */
    void SetArrowAngle(float deg);
    void SetRecRecording(bool active);
    void SetBluetoothConnected(bool connected);
    void SetBattery(uint8_t usage, bool charging);
    void SetAltitude(int altitude);
    void SetTurnDirection(TurnDirection_t dir);

private:
    /* 创建一个叠加数值标签：font/颜色/对齐/偏移/初值 */
    lv_obj_t* Value_Create(lv_obj_t* par, const lv_font_t* font, lv_color_t color,
                           lv_align_t align, lv_coord_t x, lv_coord_t y, const char* init);
    /* 创建一个透明可聚焦按钮（聚焦时描青色边框辉光） */
    lv_obj_t* Btn_Create(lv_obj_t* par, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h);
    void Spectrum_Create(lv_obj_t* par);
    void Spectrum_Update();
    static void onSpectrumTimer(lv_timer_t* timer);

private:
    lv_style_t styleBtn;        /* 按钮常态：全透明 */
    lv_style_t styleBtnFocus;   /* 按钮聚焦：青色描边辉光 */
};

}

#endif // !__DIALPLATE_VIEW_H
