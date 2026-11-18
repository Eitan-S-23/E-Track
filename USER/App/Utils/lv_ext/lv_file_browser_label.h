#ifndef LV_FILE_BROWSER_LABEL_H
#define LV_FILE_BROWSER_LABEL_H

#include "lvgl/lvgl.h"

namespace FileBrowserLabel
{
inline void SetFocused(lv_obj_t* row, bool focused)
{
    if (row == nullptr || lv_obj_get_child_cnt(row) < 2u)
    {
        return;
    }
    lv_obj_t* label = lv_obj_get_child(row, 1);
    /* LVGL restores its DOT-modified display buffer before changing mode.
     * Never use the displayed (possibly dotted) text as the file identity. */
    lv_label_set_long_mode(label, focused ? LV_LABEL_LONG_SCROLL
                                          : LV_LABEL_LONG_DOT);
}

inline void OnFocus(lv_event_t* event)
{
    SetFocused(lv_event_get_current_target(event),
               lv_event_get_code(event) == LV_EVENT_FOCUSED);
}

inline void Configure(lv_obj_t* row, lv_obj_t* label, lv_coord_t width,
                      const lv_font_t* font)
{
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_size(label, width, lv_font_get_line_height(font));
    lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
    lv_obj_add_event_cb(row, OnFocus, LV_EVENT_FOCUSED, nullptr);
    lv_obj_add_event_cb(row, OnFocus, LV_EVENT_DEFOCUSED, nullptr);
}
}

#endif
