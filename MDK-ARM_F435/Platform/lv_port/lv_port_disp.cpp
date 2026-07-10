#include "lv_port/lv_port.h"
#include "lvgl/lvgl.h"
#include "HAL/HAL.h"

#define SCREEN_BUFFER_SIZE (CONFIG_SCREEN_HOR_RES * (CONFIG_SCREEN_VER_RES / 2) )

static lv_disp_drv_t* disp_drv_p = NULL;

/* 刷新耗时统计：monitor_cb 在每个刷新周期（渲染全部脏区+flush）结束时被 LVGL 调用，
 * time 为该周期总耗时（含渲染、行缓存内嵌的 SD 读、半屏 flush 等待）。
 * 上层每秒读取并复位，与 SD 等待计时相减即可拆分"纯渲染"与"SD 等待"。 */
static volatile uint32_t disp_refr_time_sum = 0;
static volatile uint32_t disp_refr_cnt = 0;
static volatile uint32_t disp_refr_px_sum = 0;

static void disp_monitor_cb(lv_disp_drv_t* disp_drv, uint32_t time, uint32_t px)
{
    (void)disp_drv;
    disp_refr_time_sum += time;
    disp_refr_cnt++;
    disp_refr_px_sum += px;
}

void lv_port_disp_get_refr_stats(uint32_t* timeMs, uint32_t* cnt, uint32_t* px)
{
    if (timeMs) *timeMs = disp_refr_time_sum;
    if (cnt) *cnt = disp_refr_cnt;
    if (px) *px = disp_refr_px_sum;
}

void lv_port_disp_reset_refr_stats(void)
{
    disp_refr_time_sum = 0;
    disp_refr_cnt = 0;
    disp_refr_px_sum = 0;
}

static void disp_flush_cb(lv_disp_drv_t* disp, const lv_area_t* area, lv_color_t* color_p)
{
    disp_drv_p = disp;

    const lv_coord_t w = (area->x2 - area->x1 + 1);
    const lv_coord_t h = (area->y2 - area->y1 + 1);
    const uint32_t len = w * h;

    HAL::Display_SetAddrWindow(area->x1, area->y1, area->x2, area->y2);

    HAL::Display_SendPixels((uint16_t*)color_p, len);
}

static void disp_send_finish_callback()
{
    lv_disp_flush_ready(disp_drv_p);
}

static void disp_wait_cb(lv_disp_drv_t* disp_drv)
{
    __wfi();
}

void lv_port_disp_init()
{
    HAL::Display_SetSendFinishCallback(disp_send_finish_callback);

    static lv_color_t lv_disp_buf1[SCREEN_BUFFER_SIZE];
    static lv_color_t lv_disp_buf2[SCREEN_BUFFER_SIZE];

    static lv_disp_draw_buf_t disp_buf;
    lv_disp_draw_buf_init(&disp_buf, lv_disp_buf1, lv_disp_buf2, SCREEN_BUFFER_SIZE);

    /*Initialize the display*/
    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = CONFIG_SCREEN_HOR_RES;
    disp_drv.ver_res = CONFIG_SCREEN_VER_RES;
    disp_drv.flush_cb = disp_flush_cb;
    disp_drv.wait_cb = disp_wait_cb;
    disp_drv.monitor_cb = disp_monitor_cb;
    disp_drv.draw_buf = &disp_buf;
    lv_disp_drv_register(&disp_drv);
}
