#ifndef __STARTUP_VIEW_H
#define __STARTUP_VIEW_H

#include "../Page.h"

/* ===================== 开机动画播放速度（只改这一个值即可）=====================
 * 百分比：100 = 默认；小于 100 更快（例如 50 = 2 倍速）；大于 100 更慢（例如 200 = 半速）。
 * 它同时缩放“电路光点流动”“像素字揭示”“跳转仪表盘延时”，三者自动保持同步。 */
#define STARTUP_ANIM_SPEED   150

/* —— 以下节奏均随 STARTUP_ANIM_SPEED 缩放，一般无需改动 —— */
#define STARTUP_PULSE_TIME    ((uint32_t)(900UL * STARTUP_ANIM_SPEED / 100))   /* 单条光点流完一条走线 */
#define STARTUP_PULSE_STAGGER ((uint32_t)( 55UL * STARTUP_ANIM_SPEED / 100))   /* 8 条走线光点错开间隔 */
/* 整段动画总时长：电路光点与像素字都在 [0, STARTUP_ANIM_TOTAL] 内“同起同收” */
#define STARTUP_ANIM_TOTAL    (STARTUP_PULSE_STAGGER * 7 + STARTUP_PULSE_TIME)
#define STARTUP_FADE_MS       ((uint32_t)(300UL * STARTUP_ANIM_SPEED / 100))   /* 末尾淡出时长 */
/* 动画总播放时长(ms)：控制器据此定时跳转（= 动画 + 淡出） */
#define STARTUP_PLAY_MS       (STARTUP_ANIM_TOTAL + STARTUP_FADE_MS)

namespace Page
{

class StartupView
{
public:
    StartupView();

    void Create(lv_obj_t* root);
    void Delete();

public:
    struct
    {
        lv_obj_t* cont;
        lv_obj_t* labelLogo;

        lv_anim_timeline_t* anim_timeline;
    } ui;

private:
};

}

#endif // !__VIEW_H
