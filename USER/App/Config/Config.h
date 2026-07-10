/*
 * MIT License
 * Copyright (c) 2021 _VIFEXTech
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
#ifndef __CONFIG_H
#define __CONFIG_H

/*=========================
   Application configuration
 *=========================*/

#define CONFIG_SYSTEM_SAVE_FILE_PATH          "/SystemSave.json"
#define CONFIG_SYSTEM_SAVE_FILE_BACKUP_PATH   "/.SystemSaveBackup.json"
#define CONFIG_SYSTEM_LANGUAGE_DEFAULT        "en-GB"
#define CONFIG_SYSTEM_TIME_ZONE_DEFAULT       8    // GMT+ 8
#define CONFIG_SYSTEM_SOUND_ENABLE_DEFAULT    true

#define CONFIG_WEIGHT_DEFAULT                 65   // kg

#ifdef ARDUINO
#  define CONFIG_GPS_REFR_PERIOD              200 // ms
#else
#  define CONFIG_GPS_REFR_PERIOD              30 // ms (调整从10ms→30ms以提高帧率)
#endif

/* GPS Simulator Configuration */
#ifndef CONFIG_GPS_USE_SIMULATOR
#define CONFIG_GPS_USE_SIMULATOR            1    // Set to 1 to enable GPS simulator
#endif

#define CONFIG_GPS_LONGITUDE_DEFAULT          116.391332f
#define CONFIG_GPS_LATITUDE_DEFAULT           39.907415f

#define CONFIG_TRACK_FILTER_OFFSET_THRESHOLD  2 // pixel
#define CONFIG_TRACK_RECORD_FILE_DIR_NAME     "Track"

#define CONFIG_MAP_USE_WGS84_DEFAULT          false
#define CONFIG_MAP_DIR_PATH_DEFAULT           "/MAP"

#ifndef CONFIG_MAP_EXT_NAME_DEFAULT
#define CONFIG_MAP_EXT_NAME_DEFAULT           "bin"
#endif

#ifndef CONFIG_MAP_IMG_PNG_ENABLE
#  define CONFIG_MAP_IMG_PNG_ENABLE           0
#endif

#define CONFIG_ARROW_THEME_DEFAULT            "default"

#define CONFIG_LIVE_MAP_LEVEL_DEFAULT         16
#define CONFIG_LIVE_MAP_TIMER_PERIOD          16 // ms

/* 导航地图渲染模式开关：
 * 1 = 周期性 recenter：地图平时静止、箭头在静止地图上移动，箭头偏离中心超过
 *     CONFIG_LIVE_MAP_RECENTER_MARGIN 才 recenter 一次。大多数帧只重绘箭头小区域，
 *     瓦片像素几乎全部命中行缓存、不再每帧读 SD，帧率高。归位过程用短动画平滑滑回
 *     中心（见 CONFIG_LIVE_MAP_RECENTER_ANIM_*），避免硬跳。
 * 0 = 原始实时渲染：箭头锁定屏幕中心、地图每帧平滑滚动。视觉平滑但每帧整屏重绘、
 *     且瓦片像素每帧从 SD 逐行重读，帧率低。 */
#define CONFIG_LIVE_MAP_RECENTER_ENABLE       0

/* 地图 recenter 阈值（像素），仅在 CONFIG_LIVE_MAP_RECENTER_ENABLE=1 时生效。
 * 两次 recenter 之间地图容器保持静止，箭头在静止地图上平滑移动（仅小区域重绘）；
 * 当箭头偏离屏幕中心超过该阈值时，触发一次平滑 recenter 使箭头滑回中心。
 * 值越大 recenter 越少、帧率越高，但箭头偏离中心越远（建议 32~80，须 < 120）。 */
#define CONFIG_LIVE_MAP_RECENTER_MARGIN       48

/* 平滑归位参数（仅 recenter 模式）：
 * 触发后，地图容器每个刷新周期按 (剩余距离 / DIV) 向目标逼近（指数缓动），
 * 剩余距离 <= SNAP 像素时直接吸附到位并结束动画、回到静止省电状态。
 * DIV 越大越慢越顺滑；SNAP 越小收尾越精确。归位期间会整屏重绘，但仅持续数百毫秒。 */
#define CONFIG_LIVE_MAP_RECENTER_ANIM_DIV     4
#define CONFIG_LIVE_MAP_RECENTER_ANIM_SNAP    3

/* 平滑滚动插值（仅 CONFIG_LIVE_MAP_RECENTER_ENABLE=0 的实时滚动模式生效）：
 * GPS 位置每 CONFIG_GPS_REFR_PERIOD 才更新一次（设备端 200ms），直接应用会使
 * 地图以 5Hz 大步跳动。开启后，显示坐标在每个地图刷新周期向 GPS 目标坐标
 * 指数逼近（每周期走剩余距离的 1/DIV，剩余 <=SNAP 像素时吸附），把低频大步
 * 拆成高频小步，滚动视觉连续。轨迹记录仍使用真实 GPS 坐标，不受插值影响。
 * 代价：显示位置滞后真实位置约 1~2 个 GPS 周期的行程；缓动期间持续整屏重绘。 */
#define CONFIG_LIVE_MAP_SCROLL_INTERP_ENABLE  1
#define CONFIG_LIVE_MAP_SCROLL_INTERP_DIV     3
#define CONFIG_LIVE_MAP_SCROLL_INTERP_SNAP    1
#ifdef ARDUINO
#  define CONFIG_LIVE_MAP_REFR_PERIOD         32 // ms
#else
#  define CONFIG_LIVE_MAP_REFR_PERIOD         30 // ms
#endif

#define CONFIG_LIVE_MAP_DEBUG_ENABLE          0
#if CONFIG_LIVE_MAP_DEBUG_ENABLE
#  define CONFIG_LIVE_MAP_VIEW_WIDTH          240
#  define CONFIG_LIVE_MAP_VIEW_HEIGHT         240
#else
#  define CONFIG_LIVE_MAP_VIEW_WIDTH          LV_HOR_RES
#  define CONFIG_LIVE_MAP_VIEW_HEIGHT         LV_VER_RES
#endif

/* 视口快照渲染（需 512KB SRAM，与 RECENTER 互斥、优先级更高）：
 * 地图可见窗口 240x320 像素整帧常驻 RAM（.sram_ext 段 150KB），滚动时
 * memmove 平移快照内容、仅从 SD 读新露出的边条（经瓦片行缓存，几乎全命中），
 * 瓦片渲染走 LVGL 内存图直拷路径。消除滚动帧的 SD 读与逐行解码两大耗时，
 * 帧率上限由 ~15FPS 提升到刷新周期上限。缩放级别切换时整帧重建（一次 ~40ms）。 */
#ifndef CONFIG_LIVE_MAP_SNAPSHOT_ENABLE
#  define CONFIG_LIVE_MAP_SNAPSHOT_ENABLE     1
#endif

/* 高等级放大显示（仅快照模式生效）：允许显示级别超过 SD 卡实际数据的
 * 最高级别 EXTRA 级，超出部分用最高数据级瓦片放大渲染，存储零增长。
 * 扩展级采用 √2/级 的平缓缩放阶梯——每 +1 级可视面积减半（数据 16 级时
 * 17 级 = 线性 1.41 倍/面积 1/2,18 级 = 线性 2 倍/面积 1/4），
 * 区别于标准整级的每级面积 1/4，缩放手感更细腻。
 * 放大后位图变模糊属预期；EXTRA=2（线性 2 倍）已是可用性上限，勿再加大。 */
#ifndef CONFIG_LIVE_MAP_ZOOM_EXTRA_LEVELS
#  define CONFIG_LIVE_MAP_ZOOM_EXTRA_LEVELS   2
#endif

/* 亚像素平滑滚动（实验已否决，勿开启）：
 * 路线一 LVGL 变换约 70ms/帧；路线二缺 150KB 级显示缓冲；路线三
 * decoder 层相位混合固定半像素实测 101.81ms/帧，超过 35ms 终止线。
 * 当前硬件保持整像素快照直拷；实验实现已从 LiveMap.cpp 移除。 */
#ifndef CONFIG_LIVE_MAP_SUBPIXEL_ENABLE
#  define CONFIG_LIVE_MAP_SUBPIXEL_ENABLE     0
#endif

#define CONFIG_MONKEY_TEST_ENABLE             0
#if CONFIG_MONKEY_TEST_ENABLE
#  define CONFIG_MONKEY_INDEV_TYPE            LV_INDEV_TYPE_ENCODER
#  define CONFIG_MONKEY_PERIOD_MIN            10
#  define CONFIG_MONKEY_PERIOD_MAX            100
#  define CONFIG_MONKEY_INPUT_RANGE_MIN       -5
#  define CONFIG_MONKEY_INPUT_RANGE_MAX       5
#endif

/* RTT 下行调试命令（仅设备端）：开启后创建 100ms 轮询定时器，读取 RTT
 * down channel 0 的行命令并执行（ping/livemap/dialplate/back），配合
 * J-Link 实现无人值守的页面控制与性能测量。生产固件置 0 整体移除。 */
#ifndef CONFIG_RTT_DEBUG_CMD_ENABLE
#  define CONFIG_RTT_DEBUG_CMD_ENABLE         1
#endif

#endif
