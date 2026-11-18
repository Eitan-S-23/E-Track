#ifndef COMPANION_TEST_LV_CONF_H
#define COMPANION_TEST_LV_CONF_H
#define LV_CONF_H

#include <stdlib.h>
#define LV_COLOR_DEPTH 16
#define LV_COLOR_16_SWAP 1
#define LV_MEM_CUSTOM 0
#define LV_MEM_SIZE (128U * 1024U)
#define LV_TICK_CUSTOM 0
#define LV_USE_LOG 0
#define LV_USE_ASSERT_NULL 1
#define LV_USE_ASSERT_MALLOC 1
#define LV_USE_ASSERT_OBJ 1
#define LV_ASSERT_HANDLER abort();
#define LV_USE_THEME_DEFAULT 1
#define LV_USE_PERF_MONITOR 0
#define LV_USE_MEM_MONITOR 0

#endif
