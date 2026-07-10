# 仪表盘 LVGL 对象调整指南

本文档说明当前仪表盘页面中每个 LVGL 对象的属性如何调整。对应源码主要在：

- `USER/App/Pages/Dialplate/DialplateView.cpp`
- `USER/App/Pages/Dialplate/DialplateView.h`
- `USER/App/Pages/Dialplate/Dialplate.cpp`
- `USER/App/Resource/ResourcePool.cpp`

本文只覆盖当前仪表盘页 `DialplateView`。其他页面的 LVGL 对象不在本文范围内。

## 基本规则

坐标系为 240 x 320 竖屏，左上角是 `(0, 0)`，`x` 向右增加，`y` 向下增加。

常用创建函数：

| 函数 | 用途 | 主要可调参数 |
|---|---|---|
| `OverlayLabel(parent, font, color, x, y, text)` | 创建静态文字或 iconfont 图标 | `font` 字号/字体，`color` 颜色，`x/y` 位置，`text` 文本或图标 |
| `Value_Create(parent, font, color, align, x, y, init)` | 创建动态数值标签 | `font` 字号/字体，`color` 颜色，`align` 对齐方式，`x/y` 偏移，`init` 初始值 |
| `OverlayImg(parent, name, color, x, y)` | 创建图片资源并重染色 | `name` 图片资源名，`color` 重染色，`x/y` 位置 |
| `OverlayBox(parent, x, y, w, h, color, opa, radius)` | 创建实心矩形/圆点/遮罩 | `x/y` 位置，`w/h` 尺寸，`color` 颜色，`opa` 透明度，`radius` 圆角 |
| `OverlayOutline(parent, x, y, w, h, color, radius)` | 创建描边框或圆 | `x/y` 位置，`w/h` 尺寸，`color` 描边颜色，`radius` 圆角 |
| `Btn_Create(parent, x, y, w, h)` | 创建透明点击按钮 | `x/y` 位置，`w/h` 点击区域 |

颜色统一在 `DialplateView.cpp` 顶部修改：

| 宏 | 当前用途 |
|---|---|
| `COL_WHITE` | 主要动态数值 |
| `COL_CYAN` | 左侧/底部青色 HUD 标签、MAX、频谱 |
| `COL_GREEN` | 导航、坡度、爬升图标 |
| `COL_GRAY` | 单位或弱信息 |
| `COL_BLUE` | 右栏 AVG/TIME/TRIP、海拔、电池 |
| `COL_YELLOW` | CAL 区域 |
| `COL_REC_RED` | 心率图标和录制红点 |
| `COL_PANEL_BG` | 遮罩背景 |

注意：此前模拟器和固件曾因 LVGL 阴影/复杂绘制路径出问题。仪表盘页里不要随意加 `shadow_*`、`LV_EVENT_DRAW_POST`、`lv_draw_*` 或 mask 事件绘制。优先用普通 label、image、box。

## 全局常量

这些常量在 `DialplateView.cpp` 顶部，主要控制 MAX 和频谱区域：

| 常量 | 当前值 | 用途 |
|---|---:|---|
| `MAX_LABEL_X` | `-9` | MAX 标题和数值的左上 x |
| `MAX_TITLE_Y` | `236` | MAX 标题 y |
| `MAX_VALUE_Y` | `246` | MAX 数值 y |
| `MAX_VALUE_W` | `58` | MAX 标题和数值固定宽度 |
| `SPECTRUM_X` | `10` | MAX 上方频谱第 1 列 x |
| `SPECTRUM_Y` | `170` | 频谱区域顶部 y |
| `SPECTRUM_W` | `25` | 频谱逻辑宽度 |
| `SPECTRUM_H` | `63` | 频谱逻辑高度 |
| `SPECTRUM_MASK_X/Y/W/H` | `10/170/25/63` | 频谱背景遮罩位置和尺寸 |
| `SPECTRUM_SEG_H` | `3` | 每个小矩形段的高度 |
| `SPECTRUM_SEG_GAP` | `1` | 每个小矩形段之间的垂直间距 |

频谱列数和段数在 `DialplateView.h`：

| 常量 | 当前值 | 用途 |
|---|---:|---|
| `SPECTRUM_BAR_NUM` | `3` | 频谱柱数量 |
| `SPECTRUM_SEG_NUM` | `16` | 每个柱子的最大段数 |

## 全屏皮肤对象

| 对象 | 创建位置 | 当前属性 | 如何调整 |
|---|---|---|---|
| `ui.skin` | `lv_img_create(root)` | `src=IMG("dialplate_skin")`，位置 `(0,0)` | 换底图改 `IMG("dialplate_skin")` 对应资源；移动整张皮肤改 `lv_obj_set_pos(skin, 0, 0)` |

皮肤图片资源是 `USER/App/Resource/Image/img_src_dialplate_skin.c`。若需要改静态背景或烘焙元素，优先改 `.claude/fix_dialplate_skin.py` 后重新生成皮肤 C 数组。

## 顶部状态区对象

| 对象 | 当前创建/更新方式 | 当前位置/尺寸 | 当前颜色/字体 | 调整方法 |
|---|---|---:|---|---|
| `ui.status.labelHr` 心率数值 | `Value_Create` | `(24,52)` | `COL_WHITE`, `bahnschrift_13` | 改创建行的 `x/y/font/color/init` |
| `ui.status.labelAlt` 海拔数值 | `Value_Create`，后续 `SetAltitude()` 更新 | 创建 `(198,61)`，`SetAltitude()` 里设 `(196,61)`，固定框 `28x14` | `COL_WHITE`, `bahnschrift_13` | 改创建行和 `SetAltitude()` 中的 `lv_obj_set_pos(ui.status.labelAlt, 196, 61)` |
| `ui.status.labelAltUnit` 海拔单位 m | `OverlayLabel`，后续 `SetAltitude()` 更新 | `(226,61)` | `COL_GRAY`, `bahnschrift_13` | 改创建行和 `SetAltitude()` 中的单位位置 |
| `ui.status.labelBattery` 电量数值 | `Value_Create`，后续 `SetBattery()` 更新 | `(212,8)`，固定框 `24x14` | 初始 `COL_WHITE`, `bahnschrift_13`，运行时随电量/充电变色 | 改创建行位置；改 `SetBattery()` 里的颜色逻辑和 `lv_obj_set_pos(ui.status.labelBattery, 212, 8)` |
| `ui.status.labelSlope` 坡度数值 | `Value_Create` | `LV_ALIGN_TOP_RIGHT, x=-9, y=30` | `COL_GREEN`, `bahnschrift_13` | 改创建行。注意 `LV_ALIGN_TOP_RIGHT` 的 `x` 是相对右边缘的偏移 |
| `ui.status.imgGps` GPS 图标 | `OverlayImg` | `(7,12)` | 图片 `satellite` 重染 `COL_GREEN` | 改 `OverlayImg(root, "satellite", COL_GREEN, 7, 12)` |
| `ui.status.labelGpsSat` GPS 星数 | `Value_Create` | `(25,11)` | `COL_WHITE`, `bahnschrift_13` | 改创建行 |
| 蓝牙遮罩 1 | `OverlayBox` | `(5,28,17,16)` | 黑色不透明 | 改 `OverlayBox(root, 5, 28, 17, 16, lv_color_black(), ...)` |
| `ui.status.imgBt` 蓝牙图标 | `OverlayImg`，后续 `SetBluetoothConnected()` 更新 | `(7,28)` | 初始 `COL_GRAY`，连接时 `COL_BLUE` | 改创建行位置；改 `SetBluetoothConnected()` 颜色逻辑 |
| 心率遮罩 | `OverlayBox` | `(4,46,19,13)` | 黑色不透明 | 改对应 `OverlayBox` |
| 心率图标 | `OverlayLabel` | `(4,45)` | `COL_REC_RED`, `iconfont_20`, `ICON_HEART_RATE` | 改 `OverlayLabel(root, FONT("iconfont_20"), COL_REC_RED, 4, 45, ICON_HEART_RATE)` |
| `ui.status.imgBattery` 电池图标 | `OverlayImg`，后续 `SetBattery()` 更新 | `(201,7)` | 图片 `battery` 重染 `COL_BLUE`，运行时变色 | 改创建行位置；改 `SetBattery()` 中 `imgBattery` 重染色 |
| `ui.status.labelAltIcon` 海拔图标 | `OverlayLabel`，后续 `SetAltitude()` 更新 | 创建 `(181,56)`，`SetAltitude()` 里设 `(181,56)` | `COL_BLUE`, `iconfont_20`, `ICON_ALTITUDE` | 改创建行和 `SetAltitude()` 中的位置 |
| 爬升图标 | `OverlayLabel` | `(184,29)` | `COL_GREEN`, `iconfont_16`, `ICON_CLIMB` | 改 `OverlayLabel(root, FONT("iconfont_16"), COL_GREEN, 184, 29, ICON_CLIMB)`。颜色改 `COL_GREEN`，大小改字体名，位置改 `184,29` |

爬升图标来自 `Tools/图标/font_5t5ay47raff`，码点是 `U+E6F2`，UTF-8 写法为 `"\xEE\x9B\xB2"`。如果更新图标包，需要重新运行：

```bat
Tools\图标\convert_iconfont.bat --no-pause font_5t5ay47raff USER\App\Resource\Font\font_iconfont_16.c 16 4
Tools\图标\convert_iconfont.bat --no-pause font_5t5ay47raff USER\App\Resource\Font\font_iconfont_20.c 20 4
```

## 顶部导航区对象

| 对象 | 当前创建/更新方式 | 当前位置 | 当前颜色/字体 | 调整方法 |
|---|---|---:|---|---|
| `ui.nav.labelDist` 导航距离数字 | `Value_Create` | `(99,10)` | `COL_WHITE`, `bahnschrift_24` | 改创建行 |
| `ui.nav.labelDistUnit` 单位 m | `lv_label_create` | `(142,15)` | `COL_GRAY`, `bahnschrift_13` | 改 `lv_obj_set_pos(ui.nav.labelDistUnit, 142, 15)` |
| `ui.nav.labelTurnIcon` 转向图标 | `OverlayLabel`，后续 `SetTurnDirection()` 更新文本 | `(68,18)` | `COL_GREEN`, `iconfont_20` | 改创建行位置/颜色/字体；改 `SetTurnDirection()` 可替换具体图标 |
| `ui.nav.labelTurnText` 转向文字 | `OverlayLabel`，后续 `SetTurnDirection()` 更新文本 | `(104,30)` | `COL_GREEN`, `cn_16` | 改创建行位置/颜色/字体；改 `TXT_TURN_*` 可改文字内容 |

`SetTurnDirection()` 会根据方向更新 `labelTurnIcon` 和 `labelTurnText`。如果创建位置改了，运行时不会被该函数覆盖；如果文本/图标码点改了，需要改 `ICON_TURN_*` 或 `TXT_TURN_*`。

## 速度区对象

| 对象 | 当前创建方式 | 当前位置 | 当前颜色/字体 | 调整方法 |
|---|---|---:|---|---|
| `ui.speed.labelValue` 当前速度数值 | `Value_Create` | `(10,91)` | `COL_WHITE`, `bahnschrift_48` | 改创建行位置/字体/颜色 |
| `SPEED` 标题 | `OverlayLabel` | `(11,78)` | `COL_CYAN`, `bahnschrift_13` | 改创建行 |
| `KM/H` 单位 | `OverlayLabel` | `(10,134)` | `COL_CYAN`, `bahnschrift_17` | 改创建行 |

速度数值内容由 `Dialplate.cpp` 的数据刷新逻辑更新，`DialplateView` 只负责创建标签和样式。

## MAX 和频谱动画对象

| 对象 | 当前创建/更新方式 | 当前属性 | 调整方法 |
|---|---|---|---|
| `ui.maxBar.spectrumMask` 频谱背景遮罩 | `OverlayBox` | `x=10, y=170, w=25, h=63`，`COL_PANEL_BG` | 改 `SPECTRUM_MASK_X/Y/W/H` 和颜色 |
| `ui.maxBar.spectrumSegs[i][s]` 频谱小矩形段 | `Spectrum_Create()` 循环创建 | 3 列 x 16 段，每段 `7x3`，段间距 `1`，颜色 `COL_CYAN` | 列数改 `SPECTRUM_BAR_NUM`，段数改 `SPECTRUM_SEG_NUM`；宽度改 `segW=7`；高度/间距改 `SPECTRUM_SEG_H/GAP`；颜色改 `lv_obj_set_style_bg_color(seg, COL_CYAN, 0)` |
| `ui.maxBar.spectrumTimer` 动画定时器 | `lv_timer_create(onSpectrumTimer, 80, this)` | 80 ms 一帧 | 改 `80` 调整速度 |
| `ui.maxBar.labelTitle` MAX 标题 | `OverlayLabel` | `x=MAX_LABEL_X(-9), y=MAX_TITLE_Y(236), w=58, h=9` | 改 `MAX_LABEL_X/MAX_TITLE_Y/MAX_VALUE_W`，字体 `montserrat_8`，颜色 `COL_CYAN` |
| `ui.maxBar.labelMax` MAX 数值 | `Value_Create` | `x=MAX_LABEL_X(-9), y=MAX_VALUE_Y(246), w=58, h=11` | 改 `MAX_LABEL_X/MAX_VALUE_Y/MAX_VALUE_W`，字体 `agencyb_12`，颜色 `COL_WHITE` |

频谱动画高度由 `Spectrum_Update()` 中 `frames` 控制：

```cpp
static const uint8_t frames[][SPECTRUM_BAR_NUM] =
{
    { 2, 8, 16 },
    { 4, 16, 6 },
    ...
};
```

每个数字表示该列点亮多少段。当前最大为 `16/16`，最小为 `2/16`。如果要最低约 10%，保持最小值 `2`；如果要完全熄灭，使用 `0`；如果最高不变，最大仍保持 `16`。

## 右侧 AVG/TIME/TRIP/CAL 数值对象

四个右栏数值通过循环创建：

```cpp
const lv_coord_t my[METRIC_NUM] = { 93, 138, 183, 226 };
const char* mft[METRIC_NUM] = { "bahnschrift_24", "bahnschrift_17", "bahnschrift_24", "bahnschrift_17" };
Value_Create(root, FONT(mft[i]), ..., LV_ALIGN_TOP_MID, 204 - SCR_CX, my[i], ...);
```

| 索引 | 对象 | 当前 y | 当前字体 | 初始值 | 调整方法 |
|---:|---|---:|---|---|---|
| `0` | AVG 数值 | `93` | `bahnschrift_24` | `0.0` | 改 `my[0]`、`mft[0]`、初始值数组 |
| `1` | TIME 数值 | `138` | `bahnschrift_17` | `0:00:00` | 改 `my[1]`、`mft[1]`、初始值数组 |
| `2` | TRIP 数值 | `183` | `bahnschrift_24` | `0.0` | 改 `my[2]`、`mft[2]`、初始值数组 |
| `3` | CAL 数值 | `226` | `bahnschrift_17` | `0` | 改 `my[3]`、`mft[3]`、初始值数组 |

右栏数值统一以屏幕水平中心对齐，`x=204-SCR_CX`。要整体左移/右移，改 `204`。

## 右侧 AVG/TIME/TRIP/CAL 图标和标签对象

| 区域 | 对象 | 当前属性 | 调整方法 |
|---|---|---|---|
| AVG | `OverlayOutline(root, 182,82,8,8,COL_BLUE,1)` | AVG 小图标外框 | 改 `x/y/w/h/color/radius` |
| AVG | `OverlayBox(root, 184,87,2,2,COL_BLUE)` | AVG 图标点 | 改对应 box |
| AVG | `OverlayBox(root, 188,84,2,5,COL_BLUE)` | AVG 图标柱 | 改对应 box |
| AVG | `AVG` 标签 | `(194,78)`, `COL_BLUE`, `bahnschrift_13` | 改 `OverlayLabel` |
| AVG | `KM/H` 单位 | `(205,114)`, `COL_BLUE`, `bahnschrift_13` | 改 `OverlayLabel` |
| TIME | `OverlayOutline(root,182,127,8,8,COL_BLUE,LV_RADIUS_CIRCLE)` | 时间小圆 | 改 `x/y/w/h/color` |
| TIME | `OverlayBox(root,186,128,1,4,COL_BLUE)` | 时针 | 改对应 box |
| TIME | `OverlayBox(root,187,131,3,1,COL_BLUE)` | 分针 | 改对应 box |
| TIME | `TIME` 标签 | `(194,123)`, `COL_BLUE`, `bahnschrift_13` | 改 `OverlayLabel` |
| TIME | `H:M:S` 单位 | `(205,159)`, `COL_BLUE`, `bahnschrift_13` | 改 `OverlayLabel` |
| TRIP | `OverlayBox(root,182,173,3,3,COL_BLUE,circle)` | 小点 1 | 改对应 box |
| TRIP | `OverlayBox(root,187,176,3,3,COL_BLUE,circle)` | 小点 2 | 改对应 box |
| TRIP | `OverlayBox(root,183,181,7,2,COL_BLUE)` | 横线 | 改对应 box |
| TRIP | `TRIP` 标签 | `(194,168)`, `COL_BLUE`, `bahnschrift_13` | 改 `OverlayLabel` |
| TRIP | `KM` 单位 | `(210,204)`, `COL_BLUE`, `bahnschrift_13` | 改 `OverlayLabel` |
| CAL | `OverlayOutline(root,182,218,8,8,COL_YELLOW,circle)` | CAL 小圆 | 改对应 outline |
| CAL | `OverlayBox(root,185,215,2,8,COL_YELLOW)` | CAL 火苗/竖线 | 改对应 box |
| CAL | `CAL` 标签 | `(194,213)`, `COL_YELLOW`, `bahnschrift_13` | 改 `OverlayLabel` |
| CAL | `KCAL` 单位 | `(205,248)`, `COL_YELLOW`, `bahnschrift_13` | 改 `OverlayLabel` |

## 地图路点标签对象

| 对象 | 当前创建方式 | 当前位置 | 当前颜色/字体 | 调整方法 |
|---|---|---:|---|---|
| `SPRING` | `Value_Create` | `(126,73)` | `COL_WHITE`, `bahnschrift_13` | 改创建行 |
| `2.4km` | `Value_Create` | `(126,85)` | `COL_GRAY`, `bahnschrift_13` | 改创建行 |
| `BRIDGE` | `Value_Create` | `(62,155)` | `COL_WHITE`, `bahnschrift_13` | 改创建行 |
| `1.2km` | `Value_Create` | `(62,167)` | `COL_GRAY`, `bahnschrift_13` | 改创建行 |

这些目前是占位文本，不在 `ui` 结构里保存。如果未来需要运行时更新，需要把返回的 `lv_obj_t*` 保存到 `DialplateView.h` 的 `ui` 结构中。

## 底部按钮对象

按钮样式：

| 样式 | 当前属性 | 调整方法 |
|---|---|---|
| `styleBtn` 常态 | 透明背景、无边框、圆角 `7`、无 padding | 改 `lv_style_set_*(&styleBtn, ...)` |
| `styleBtnFocus` 聚焦态 | `COL_CYAN` 边框，宽 `2`，背景 `LV_OPA_20` | 改 `lv_style_set_*(&styleBtnFocus, ...)` |

按钮本体：

| 对象 | 当前创建方式 | 当前位置/尺寸 | 调整方法 |
|---|---|---:|---|
| `ui.btnCont.btnMap` | `Btn_Create` | `(8,286,72,30)` | 改创建行 |
| `ui.btnCont.btnRec` | `Btn_Create` | `(86,286,68,30)` | 改创建行 |
| `ui.btnCont.btnMenu` | `Btn_Create` | `(160,286,72,30)` | 改创建行 |

按钮内文字和图标：

| 对象 | 父对象 | 当前属性 | 调整方法 |
|---|---|---|---|
| MAP 图标 | `btnMap` | `(12,5)`, `COL_CYAN`, `iconfont_20`, `ICON_MAP` | 改 `OverlayLabel(ui.btnCont.btnMap, ...)` |
| MAP 文字 | `btnMap` | `(32,6)`, `COL_CYAN`, `cn_16`, `TXT_MAP` | 改对应 `OverlayLabel` |
| `ui.btnCont.recContent` | `btnRec` | `38x14`，居中，背景透明 | 改 `lv_obj_set_size` 或改为 `lv_obj_set_pos` |
| `ui.btnCont.recDot` | `recContent` | `5x5`，位置 `(2,5)`，圆形 | 改 `lv_obj_set_size` 和 `lv_obj_set_pos` |
| `ui.btnCont.recLabel` | `recContent` | `"REC"`，位置 `(11,0)`，`COL_WHITE`, `bahnschrift_13` | 改字体/颜色/文本/位置 |
| MENU 图标 | `btnMenu` | `(12,5)`, `COL_BLUE`, `iconfont_20`, `ICON_MENU` | 改对应 `OverlayLabel` |
| MENU 文字 | `btnMenu` | `(32,6)`, `COL_BLUE`, `cn_16`, `TXT_MENU` | 改对应 `OverlayLabel` |

录制状态由 `SetRecRecording(bool active)` 更新，只改 `recDot` 颜色：录制时 `COL_REC_RED`，非录制时 `COL_WHITE`。

## 动态更新函数

| 函数 | 会修改的对象 | 当前行为 | 调整方法 |
|---|---|---|---|
| `SetSpectrumActive(bool active)` | `ui.maxBar.spectrumTimer` | 进入页面启动/退出暂停频谱动画 | 改启动/暂停逻辑 |
| `SetRecRecording(bool active)` | `ui.btnCont.recDot` | 改录制点颜色 | 改 `dotColor` 或 dot 样式 |
| `SetBluetoothConnected(bool connected)` | `ui.status.imgBt` | 蓝牙图标灰/蓝切换 | 改 `color` 逻辑 |
| `SetBattery(uint8_t usage, bool charging)` | `ui.status.imgBattery`, `ui.status.labelBattery` | 电池图标和数字改色、数字刷新 | 改颜色阈值、文本格式、位置 |
| `SetAltitude(int altitude)` | `ui.status.labelAlt`, `labelAltUnit`, `labelAltIcon` | 海拔数字和位置刷新 | 改文本格式或三者位置 |
| `SetTurnDirection(TurnDirection_t dir)` | `ui.nav.labelTurnIcon`, `ui.nav.labelTurnText` | 改转向图标和文字 | 改 `ICON_TURN_*` 或 `TXT_TURN_*` |
| `Spectrum_Update()` | `ui.maxBar.spectrumSegs` | 按 `frames` 显示/隐藏小矩形段 | 改 `frames`、透明度或颜色 |

## 字体、图标和资源

当前常用字体注册在 `ResourcePool.cpp`：

| 资源名 | 用途 |
|---|---|
| `montserrat_8`, `montserrat_10` | 小号英文/符号 |
| `bahnschrift_13`, `17`, `24`, `32`, `48`, `65` | 数字和英文字体 |
| `cn_16` | 中文标签 |
| `iconfont_16` | 小号图标，例如爬升 |
| `iconfont_20` | 常规图标 |
| `agencyb_12`, `agencyb_36` | MAX 等数字样式 |

如果新增字体：

1. 生成 `USER/App/Resource/Font/font_xxx.c`。
2. 在 `ResourcePool.cpp` 加 `IMPORT_FONT(xxx)`。
3. 在 `Simulator/LVGL.Simulator/LVGL.Simulator.vcxproj` 和 `.filters` 加入源文件。
4. 在 `MDK-ARM_F435/proj.uvprojx` 加入源文件。
5. 固件手动增量构建时，如果 dep/lnp 还没有新文件，用 `build_f435.ps1 -NewSources` 和 `-ExtraLinkObjs`。

## 修改后的验证流程

修改仪表盘对象后，建议至少做一次模拟器验证：

```powershell
& 'D:\vs2019\MSBuild\Current\Bin\MSBuild.exe' 'Simulator\LVGL.Simulator.sln' /m /p:Configuration=Debug /p:Platform=x64 /v:minimal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .claude\cap.ps1
```

模拟器截图输出在：

```text
.claude\sim_new.png
```

确认无问题后再构建 F435 固件。项目当前使用 AC5，优先使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\MDK-ARM_F435\build_f435.ps1' -Sources @('..\USER\App\Pages\Dialplate\DialplateView.cpp','..\USER\App\Resource\ResourcePool.cpp')"
```

如果新增字体源或图片源，按 `AGENTS.md` 中的 `-NewSources` / `-ExtraLinkObjs` 方式处理，不要手写 ARMCC 参数。
