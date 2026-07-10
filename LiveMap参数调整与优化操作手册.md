# LiveMap 参数调整与优化操作手册

**面向对象**:任何需要修改本项目地图导航参数、做性能调优的 agent/开发者。
本手册按"查表 → 改一个值 → 跑固定命令 → 按固定标准验证"编写,无需理解实现细节。
背景原理与踩坑链见《导航帧率优化全程复盘与踩坑手册.md》;编译/烧录权威流程见 `AGENTS.md`。

---

## 一、改参数的标准流程(四步,适用于本手册所有参数)

```
1. 用 Edit 修改参数(位置见下表)
2. 编译:   ./build_f435_and_simulator.bat --no-pause
           (只改固件侧时可用: powershell.exe -NoProfile -ExecutionPolicy Bypass
            -Command "& 'MDK-ARM_F435\build_f435.ps1' -AutoStale")
3. 烧录:   JLink.exe -Device AT32F435RGT7 -If SWD -Speed 1000 -AutoConnect 1
            -ExitOnError 1 -CommandFile <脚本>
           脚本内容: h → loadfile "<仓库绝对路径>\MDK-ARM_F435\Objects\X-Track.hex" → r → g → qc
           (偶发 "Failed to initialized DAP" 时等 3 秒重试一次即可)
4. 验证:   见"四、性能测量标准流程";或让用户看屏幕
```

**红线**:改完必须编译到 `armlink/fromelf exit code 0` 且报出 `Program Size` 行才算成功;
烧录后 RTT 控制块地址可能变化,必须重新从 `MDK-ARM_F435\Listings\X-Track.map` 查 `_SEGGER_RTT`。

---

## 二、参数总表

### 2.1 缩放与地图(`USER/App/Config/Config.h`)

| 参数 | 当前值 | 作用 | 怎么调 |
|---|---|---|---|
| `CONFIG_LIVE_MAP_LEVEL_DEFAULT` | 16 | 进入地图页的默认缩放级 | 12~18 任意;仅影响初值,slider 可再调 |
| `CONFIG_LIVE_MAP_ZOOM_EXTRA_LEVELS` | 2 | 超出 SD 数据的扩展显示级数(√2/级:17=1.41 倍、18=2 倍,存储零增长) | 0=关闭放大模式;1=只留 17 级;**勿 >2**(位图放大过糊) |

### 2.2 滚动平滑度(`USER/App/Config/Config.h`)

| 参数 | 当前值 | 作用 | 怎么调 |
|---|---|---|---|
| `CONFIG_LIVE_MAP_SCROLL_INTERP_ENABLE` | 1 | GPS 5Hz 大步 → 每刷新周期小步插值 | 0 关闭会回到 5Hz 跳动,一般不关 |
| `CONFIG_LIVE_MAP_SCROLL_INTERP_DIV` | 3 | 每周期走剩余距离的 1/DIV | 越大越平缓但滞后越大(2~5) |
| `CONFIG_LIVE_MAP_REFR_PERIOD`(ARDUINO 分支) | 32 | 地图刷新周期 ms,决定帧率软上限 31Hz | 降到 16 → 上限 62Hz(引擎实测可到 ~50FPS);升到 50+ 省电 |
| `CONFIG_GPS_REFR_PERIOD`(ARDUINO 分支) | 200 | GPS 位置更新周期 ms | 插值开启时**改它不提升帧率**,只减小显示滞后;<100 无意义 |

### 2.3 渲染模式(`USER/App/Config/Config.h`,三选一)

| 模式 | 开关组合 | 特点 |
|---|---|---|
| **视口快照(当前,推荐)** | `SNAPSHOT_ENABLE=1`(RECENTER 值被忽略) | 滚动帧 SD 读≈0,压测 24.5FPS,需 512KB SRAM |
| 周期 recenter | `SNAPSHOT_ENABLE=0` + `RECENTER_ENABLE=1` | 地图静止箭头动,平时 60FPS,周期性滑回中心 |
| 原始实时滚动 | `SNAPSHOT_ENABLE=0` + `RECENTER_ENABLE=0` | 每帧整屏读 SD,~15FPS,仅对照用 |

### 2.4 测试与调试开关

| 参数 | 位置 | 当前值 | 作用 |
|---|---|---|---|
| `CONFIG_RTT_DEBUG_CMD_ENABLE` | Config.h | 1 | RTT 下行命令(ping/livemap/dialplate/back/gpsreset)。**生产固件置 0** |
| `SIM_SPEED_MIN_KPH` / `SIM_SPEED_MAX_KPH` | `USER/HAL/HAL_GPS_Simulator.cpp` | 50/80 | GPS 模拟器速度。压测临时调 300/400,**测完必须改回** |
| `CONFIG_GPS_USE_SIMULATOR` | Config.h | 1 | 0=接真实 GPS 模块 |
| `CONFIG_SD_MULTIBLOCK_SELFTEST` | `USER/HAL/HAL_SD_CARD.cpp` | 0 | 开机 SD 多块读自检(诊断 SD 驱动问题时置 1) |

### 2.5 禁改区(改了会坏,列出防误触)

| 项 | 位置 | 原因 |
|---|---|---|
| `LV_MEM_SIZE (72U*1024U)` | `Simulator/LVGL.Simulator/lv_conf.h` | 固件与模拟器共用;曾因改动导致设备黑屏 |
| `XTRACK_IMG_LINE_CACHE_CNT 3` / `ROWS 16` | `Simulator/.../lv_img_decoder.c` | 16 行/条是实测拐点,32 行增益反转;扩条数是伪优化(LRU 悬崖) |
| `SNAPSHOT_W 256` / `SNAPSHOT_GRID_X 16` | `USER/App/Pages/LiveMap/LiveMap.cpp` | 16px 网格防 60 倍读放大;改小会拖死主循环 |
| ARM Compiler 版本 | Keil 工程 | 必须 AC5,禁切 AC6 |
| `sd_init` 末尾 CMD16(512) | `MDK-ARM_F435/Platform/Core/at32_sdio.c` | 全局前置条件,删除会使 SD 挂载失败白屏 |
| shadow_* / lv_draw_* 自绘 | 所有 UI 代码 | 历史崩溃根源,工程级禁用 |

---

## 三、常见任务食谱(想要 X → 做 Y)

- **想让地图更跟手(减小滞后)**:`SCROLL_INTERP_DIV` 3→2,或 `CONFIG_GPS_REFR_PERIOD` 200→100。
- **想冲更高帧率数字**:`CONFIG_LIVE_MAP_REFR_PERIOD` 32→16。注意 zoom16 慢速下体感无差
  (帧率被"像素速度"限制,见复盘手册"帧率三层限制")。
- **想再加一档缩放**:不要加 `ZOOM_EXTRA_LEVELS`(>2 太糊)。正确方向是给 SD 卡补更高级别
  瓦片数据,或做道路矢量叠加(见复盘手册"后续方向")。
- **出生产固件**:`CONFIG_RTT_DEBUG_CMD_ENABLE` 置 0;确认 `SIM_SPEED_*` 为 50/80;
  确认 `CONFIG_GPS_USE_SIMULATOR` 按需(真实 GPS 置 0);`CONFIG_SD_MULTIBLOCK_SELFTEST` 置 0。
- **压力测试(测渲染能力上限)**:`SIM_SPEED_MIN/MAX_KPH` 临时改 300/400 → 烧录 → 按第四节
  测量 → **改回 50/80 再烧一次**。日常速度测出的 5-8FPS 是内容变化率,不是能力值。
- **改了 lv_conf.h 或其他公共头**:必须 `-AutoStale` 全量增量(它会自动重编所有依赖),
  禁止仅重链或单文件编译。

---

## 四、性能测量标准流程(J-Link 全自动,不需要用户操作设备)

前置:用户的 RTT Viewer 必须关闭(会抢数据);J-Link 工具在 `C:\Users\SU\SEGGER\JLink_V818\`。
采集前先执行 `Stop-Process -Name JLinkRTTLogger -Force -ErrorAction SilentlyContinue`,避免残留 logger 抢 RTT 读指针。

```
1. 查 RTT 地址:  grep "_SEGGER_RTT  " MDK-ARM_F435/Listings/X-Track.map   → 记为 <RTT>
   推荐严格命令: Select-String -LiteralPath 'MDK-ARM_F435\Listings\X-Track.map' -Pattern '^\s*_SEGGER_RTT\s+'
   J-Link mem8 <RTT> 16 必须看到 53 45 47 47 45 52 20 52 54 54('SEGGER RTT')
2. 复位设备:     JLink 脚本 r → g → qc(设备名可用泛型 CORTEX-M4,Speed 1000)
3. 等 13 秒(启动动画),发 gpsreset 命令(防 GPS 模拟器残留在地图区外):
   - 读 down 描述符: mem32 <RTT>+0x60 4   → 第 2 个字 = pBuffer 地址
   - 逐字节 w1 写 "gpsreset\n" 到 pBuffer,再 w4 <RTT>+0x6C = 9
4. 等 2 秒,同法发 "livemap\n"(注意 down 缓冲 16 字节环形,第二条命令要按
   WrOff 续写;或读回 WrOff/Size/RdOff 计算环形偏移;若回显 unknown 'psreset',立即复位重读 descriptor)
5. 采集:timeout 30 JLinkRTTLogger.exe -Device CORTEX-M4 -If SWD -Speed 1000
        -RTTAddress <RTT> -RTTChannel 0 out.log
   采集结束后确认没有残留 JLinkRTTLogger;旧 RTT 地址、残留 logger、错误命令回显产出的日志一律作废重测
6. 判读 out.log 的每秒 stat 行:
   update reload lineHit lineMiss lineReadKB sdMs refrMs refrCnt refrPxK
```

**判读标准**:
- `refrPxK / 76.8` = 每秒整屏帧数(帧率)
- `sdMs` = 渲染内 SD 等待;快照模式正常值 0~30/s,大于 100 说明快照失效
- `refrMs` 接近 1000 = 渲染引擎吃满(能力上限);当前健康值:日常 ~140、压测 ~475
- `update` 掉到 20 以下 = 有东西拖死主循环
- **miss/sdMs 全 0 且地图应该有图** = GPS 出界或 SD 挂死(烧录打断 SDIO 所致),
  先发 gpsreset、再拔插 SD 卡,不要当渲染 bug 修
- 快照像素级检查:map 查 `snapshotBuf` 地址 → JLink `savebin` dump 160KB →
  Python 按 RGB565 256x320 转 PNG 直接看

---

## 五、故障速查

| 症状 | 第一步 | 大概率原因 |
|---|---|---|
| 地图整页白/空白 | 读 `SD_IsReady`(map 查地址,mem 读 1 字节) | =0:SD 挂死→拔插卡;=1:GPS 出界→gpsreset |
| **仅高级别空白、低级别正常** | 记住这个指纹:分界线=坐标幅值 | **整数溢出**!16 级像素坐标 1.3e7,`<<8` 超 int32(commit 30dab34);任何"级别 N 以上坏"都先查坐标算术的位宽 |
| 烧录后 SD 全挂 | 拔插 SD 卡 | 烧录 halt 打断 SDIO 传输,非代码 bug |
| 改了参数没生效 | 确认重新编译+烧录了,`Program Size` 行存在 | 忘记烧录/编译失败没看输出 |
| RTT 采不到数据 | 重新查 map 里 `_SEGGER_RTT` 地址 | 每次链接后地址漂移;或 RTT Viewer 抢数据 |
| LVGL 对象不显示 | 查父链尺寸(尤其容器高度是否为 0) | 可见性裁剪;绘制与 invalidate 共用裁剪 |
| 模拟器地图显示正常但要验证设备 | 模拟器只能验证显示链路 | SD/SDIO/行缓存路径必须设备实测 |

---

## 六、优化路线图(未做项,按收益排序;实施前读复盘手册对应背景)

1. **亚像素平滑滚动**(30km/h 低速跳格感的唯一解,三条技术路线):
   路线一 LVGL 变换(zoom=257+pivot):**已实测否决**(~70ms/帧,为预估 5 倍,
   commit b28a032);路线二 独立显示缓冲重采样:**RAM 不足否决**(差 ~57KB);
   **路线三 decoder 层相位混合:已探针否决**——2026-07-10 clean retry 阶段 0 实测 A(read_line memcpy)=26.10ms/帧、B(固定半像素双线性)=101.81ms/帧,远超 >35ms 终止线。不要继续在 M4 上做全屏亚像素位图混合;`CONFIG_LIVE_MAP_SUBPIXEL_ENABLE` 继续保持 0,实验实现已从 LiveMap 生产源码移除。
2. **REFR_PERIOD 32→16ms**:高倍缩放/高速场景可用(引擎有余量);
   低速下无意义(步进频率由像素速度决定)。
3. **路线/轨迹线烘焙进快照**:AA 线条当前每帧重画约 12ms,导航场景收益大;
   烘焙时机 = 快照重建/滚动后在新边条区补画。
4. **道路矢量叠加**(中期):高缩放级在放大底图上叠加矢量路网线,清晰度质变;
   需要 OSM 道路数据预处理工具链。
5. **完整矢量地图**(长期):Mapsforge 式一份数据全级别渲染,工程量数周,
   快照架构可直接作为矢量光栅化的宿主(滚动/边条/失效逻辑全部复用)。
