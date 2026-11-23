#ifndef LV_PORT_H
#define LV_PORT_H

#include "lvgl/lvgl.h"

typedef void (*lv_port_disp_overlay_cb_t)(const lv_area_t* area, lv_color_t* color_p, void* user_data);

void lv_port_init(void);
void lv_port_disp_init(void);
/* UI-thread only. Direct HUD transfers do not complete an LVGL flush. */
void lv_port_disp_set_overlay_cb(lv_port_disp_overlay_cb_t cb, void* user_data);
void lv_port_disp_blit_blocking(const lv_area_t* area, const lv_color_t* color_p);
void lv_port_indev_init(void);
void lv_port_fs_init(void);

#endif
