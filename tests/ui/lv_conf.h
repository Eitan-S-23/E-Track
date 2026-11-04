#ifndef P51_UI_TEST_CONF_H
#define P51_UI_TEST_CONF_H
/* Keep the simulator settings, substituting only a deterministic host clock. */
#ifdef _WIN32
#define P51_RESTORE_WIN32
#undef _WIN32
#endif
#ifdef __cplusplus
extern "C" {
#endif
#include "../../Simulator/LVGL.Simulator/lv_conf.h"
#ifdef __cplusplus
}
#endif
#ifdef P51_RESTORE_WIN32
#define _WIN32 1
#undef P51_RESTORE_WIN32
#endif
#endif
