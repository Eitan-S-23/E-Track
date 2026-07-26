# P0-5 QSPI API 安全化 + JEDEC 判定 — research + 实现记录

> 卡:`PLAN-OTA-EXEC.md` P0-5。契约只读依据:`docs/ota-binary-contracts.md`
> §0.4(EXT_SELFTEST=0x7F0000 64KB 永久避让)、§0.7(JEDEC 白名单)。
> 认领:Claude(实现 agent) / 2026-07-25。

## 1. 目标拆解(卡文)

1. `qspi_cmd_send`/`qspi_busy_check` 等**全部加超时与错误返回**(现为无超时忙等,
   `qspi_cmd_send:462` `while(...==RESET);`),失败 **fail-closed**。
2. `CONFIG_QSPI_SELFTEST_ENABLE` 默认 0,自检区 `0x7F0000-0x7FFFFF` 永久避让。
3. 开机读 JEDEC ID 按白名单(`EF4018/1C4018/1C4017/EF4017`,契约 §0.7)判定,
   不识别 → 置 OTA 禁用旗标(既有功能不受影响)。

红线:遵守 AGENTS.md SDIO/LiveMap 防坑清单;**不触碰 SDIO 驱动与中断结构**。

验收:真机压测 1000 次读/写/擦零错(RTT 留证);注错(探测超时路径)返回错误码而非死循环。

## 2. 现状分析(编码前读码)

### 2.1 相似实现(≥3)与可复用模式
- `Libraries/W25Q128/qspi_cmd_en25qh128a.cpp`:全部 QSPI 命令原语。
  - `qspi_cmd_send`(:456) = kick + `while(CMDSTS==RESET);` 无超时。
  - `qspi_busy_check`(:436) = kick RDSR(硬件 auto-poll WIP),等 CMDSTS,无超时。
  - `qspi_write_enable`(:446)、`qspi_set_qe_bit`(:472)、`qspi_erase`(:420)。
  - `qspi_data_write`(:273) 内含 4 处忙等:TXFIFORDY(CPU 模式 :298)、
    EDMA EN 位(:323/:370)、DMA done(:347/:394)、CMDSTS(:407)。
- `USER/HAL/HAL_EEPROM.cpp`(P0-4)= **超时+错误返回+RTT 压测**的项目内范式:
  ACK polling ≤10ms 超时、`WriteBufferSafe` 返回 bool、`CONFIG_EEPROM_BCB_STRESS`
  默认 0、压测输出 `SEGGER_RTT_printf(0,...)`(Serial5 UART RTT logger 抓不到)。
  → 本卡完全沿用此范式(超时用 `millis()`、RTT 输出、开关默认 0、真机验收取证)。
- `USER/HAL/HAL_W25Q128.cpp::HAL::Qspi_Init`(:66)= QSPI 初始化 + **无条件**开机
  自检(擦/写/校验 16 扇区 @ `0x7F0000`,已在自检区)。校验用 XIP memcpy。

### 2.2 超时时基可用性
- `millis()`(`MDK-ARM_F435/Platform/Core/delay.c`)由 SysTick 1ms 提供;
  `Delay_Init` 在 `mcu_core.c` 于 main 之前执行,`HAL_Init` 阶段 `millis()` 可用
  (P0-4 EEPROM ACK polling 已依赖同一时基,真机验证过)。
- `qspi_cmd_en25qh128a.cpp` 与 `HAL_W25Q128.cpp` 均 `#include "HAL/HAL.h"`,
  经其传递可见 `millis()`(delay.h)。

### 2.3 调用点(改签名影响面)
- `qspi_data_write/qspi_erase/en25qh128a_qspi_xip_init` 被
  `Libraries/USB_MSC/msc_diskio.cpp` 本地 `void` 声明并调用,但整段在
  `#elif defined(MSC_USE_QSPI_FLASH)` 内;当前 `msc_diskio.h:50` 启用
  `MSC_USE_SD_CARD`,QSPI 后端**未编译**。改返回值不影响现役构建;
  按"颠覆式破坏更改"原则,同步把该段本地声明改为新签名以防将来切后端撞 UB。
- 其余调用仅在本 .cpp 内部与 `HAL_W25Q128.cpp::Qspi_Init`。

### 2.4 JEDEC 读法(命令口,XIP 关)
- RDID 指令 `0x9F`,无地址,读 3B:manufacturer/mem-type/capacity。
- 命令口读数据:kick(data_counter=N,write_data_enable=FALSE)→逐字节
  等 `QSPI_RXFIFORDY_FLAG` 后 `qspi_byte_read` →等 `CMDSTS`。
- 24bit = `(b0<<16)|(b1<<8)|b2`;白名单 `{0xEF4018,0x1C4018,0x1C4017,0xEF4017}`
  = manufacturer 0xEF/0x1C + type 0x40 + capacity 0x18(16MiB)/0x17(8MiB)。
- 读 JEDEC 必须在 `qspi_xip_enable(FALSE)` 命令口态,置于 `Qspi_Init` 早期。

## 3. 设计(实现方案)

### 3.1 错误码(qspi_cmd_en25qh128a.h)
```c
typedef enum {
    QSPI_OK          = 0,
    QSPI_ERR_TIMEOUT = -1,   // 忙等超时(fail-closed)
    QSPI_ERR_PARAM   = -2,   // 参数非法
    QSPI_ERR_VERIFY  = -3,   // 读回比对不符(压测用)
    QSPI_ERR_JEDEC   = -4,   // JEDEC 白名单外
} qspi_status_t;
```

### 3.2 超时常量
```c
#define QSPI_TIMEOUT_CMD_MS   100u    // 命令/FIFO/传输完成
#define QSPI_TIMEOUT_WIP_MS  1200u    // WIP 忙等(含 4KB 扇区擦除最坏 ~400ms)
```

### 3.3 超时封装(替换裸 while)
- `qspi_wait_cmd_done(timeout)`:等 CMDSTS,到点返回 `QSPI_ERR_TIMEOUT`,否则清标志返回 OK。
- `qspi_wait_flag(flag,timeout)`:等 TXFIFORDY/RXFIFORDY/EDMA EN 位;不清标志。
- DMA done:`while(qspi_dma_transfer_done==0)` 加 `millis()` 超时,超时禁 stream+返错。

### 3.4 签名改造(全部原语返回 qspi_status_t)
`qspi_cmd_send / qspi_busy_check / qspi_write_enable / qspi_set_qe_bit /
qspi_erase / qspi_data_write / en25qh128a_qspi_xip_init` 由 `void`→`int`
(qspi_status_t)。任一子忙等超时立即 fail-closed 返回,不再死循环。
新增命令口读:`qspi_data_read(addr,len,buf)`、`qspi_read_jedec_id(&id24)`。

### 3.5 自检区避让 + 开关
- 常量入头:`QSPI_SELFTEST_ADDR=0x7F0000`、`QSPI_SELFTEST_SIZE=0x10000`(契约 §0.4)。
- `CONFIG_QSPI_SELFTEST_ENABLE` 默认 0(HAL_Config.h),`Qspi_Init` 开机自检
  改为 gated;自检/压测仅落 `0x7F0000` 保留区,永不碰 OTA 槽(0..0x4FFFFF)与
  文件系统区。默认发货 0 → 开机不做破坏性写。

### 3.6 JEDEC 判定 + OTA 禁用旗标
- `Qspi_Init` 早期(XIP 关)读 JEDEC → 命中白名单 `s_ota_allowed=true`,否则
  `false`+RTT/串口告警;无论命中与否**继续** XIP 初始化(既有功能不受影响)。
- 暴露 `HAL::Qspi_OtaAllowed()`、`HAL::Qspi_GetJedecId()`(P2/P3 BLE BEGIN 以
  §5.7 `ERR_OTA_DISABLED` 拒绝时消费)。

### 3.7 压测入口(验收取证,RTT)
- `CONFIG_QSPI_SELFTEST_ENABLE=1` 时 `Qspi_Init` 末尾跑 `Qspi_SelfTestRun(1000)`:
  1000 次 `擦→写 4KB→命令口读回→memcmp`(轮转 16 个自检扇区),
  全程 `SEGGER_RTT_printf(0,...)` 输出 `QSPISELFTEST: start/done ok=/fail=`。
- **注错子测**:`qspi_wait_cmd_done(5ms)` 在未 kick 命令(CMDSTS 恒 RESET)时必须
  ~5ms 返回 `QSPI_ERR_TIMEOUT` 而非死循环 → RTT 打 `QSPISELFTEST: inject timeout rc=-1 (PASS)`。
- 命令口读回:新增 `qspi_data_read`(指令 0x03,mode111),避免每轮 XIP 切换。

## 4. 红线遵守
- 不改 SDIO 驱动/中断结构(仅动 QSPI/EDMA1 既有链路,超时只加不改传输逻辑)。
- 不动 EEPROM 0x55 魔数(本卡不涉及)。
- include 一律 POSIX 正斜杠(GCC CI 可移植,PRE-4 教训)。
- 头文件断言用负数组下标(AC5 `--c99` 无 `_Static_assert`)——本卡无新结构体尺寸断言需求。
- 契约文档与 PLAN-OTA.md 不动;不 commit/push(留主会话);不自验收置完成。

## 5. 验证计划
- AC5/Keil `build_f435.ps1 -AutoStale`:默认(selftest=0)与 selftest=1 双侧
  0E0W + Program Size 留证。
- GCC 可移植:新增/改动 include 反斜杠 grep=0。
- 真机(非实现会话):selftest=1 烧录 → RTT 取 `QSPISELF: done pass=16 fail=0`
  + JEDEC 命中行;采后恢复 0 重建默认固件。

---

## 6. 实现记录(as-built,2026-07-25)

> §3 设计为编码前草案;最终实现与之有若干差异(错误码取正数、命名细化、
> 自检为 1000 次“擦→写→XIP 读回比对”轮转 16 扇区 + 注错超时子测)。
> 以下为实际落地内容,以此为准。

### 6.1 实际改动文件
- `Libraries/W25Q128/qspi_cmd_en25qh128a.h`:错误码/超时/容量/自检区/JEDEC
  常量 + 全部原语新签名 + `qspi_read_jedec_id`/`qspi_jedec_is_whitelisted`/
  `qspi_data_write_selftest`/`qspi_erase_selftest` 声明。
- `Libraries/W25Q128/qspi_cmd_en25qh128a.cpp`:`#include` 自身头;新增
  `qspi_wait_flag`/`qspi_wait_dma_done`/`qspi_wait_stream_disabled`(均 `millis()`
  超时,fail-closed)、`qspi_range_ok`(生产:拒越界+拒自检区相交)、
  `qspi_range_selftest_ok`(自检:必须完整落在自检区内);
  写/擦拆 `*_core`(无策略)+ public(生产区间策略)+ `*_selftest`(自检区间策略);
  所有裸 `while(...==RESET);` 换成带超时等待;新增 `qspi_read_jedec_id`(RDID 0x9F
  命令口 3B 读)、`qspi_jedec_is_whitelisted`。
- `USER/HAL/HAL_Config.h`:`CONFIG_QSPI_SELFTEST_ENABLE` 默认 0。
- `USER/HAL/HAL_W25Q128.cpp`:`Qspi_Init` 早期(XIP 关)读 JEDEC → 白名单置
  `g_qspi_ota_disabled`(默认 true=fail-closed);selftest gated(仅动
  `0x7F0000` 保留区,走 `*_selftest` API);始终 `en25qh128a_qspi_xip_init()`
  收尾保证既有 XIP 读功能不受影响;`HAL::Qspi_IsOtaDisabled/Qspi_GetJedecId` 暴露。
  `Qspi_SelfTest` = 注错超时子测(`qspi_probe_timeout(5ms)` 必返 ERR_TIMEOUT)+
  1000 次轮转 16 扇区“擦→写(内容含迭代号)→XIP 读回 memcmp→回命令口”,
  全程 `SEGGER_RTT_printf(0,...)` 输出 `QSPISELF: inject.../start.../done ok=/fail=`。
- `USER/App/Common/HAL/HAL.h`:`Qspi_IsOtaDisabled()`/`Qspi_GetJedecId()` 声明。
- `Libraries/USB_MSC/msc_diskio.cpp`:QSPI 后端分支(当前未编译)本地 `void`
  声明改为 `#include "W25Q128/qspi_cmd_en25qh128a.h"`,防将来切后端签名撞 UB。

### 6.2 关键实现口径
- 错误码取正数 `QSPI_OK=0/ERR_TIMEOUT=1/ERR_PARAM=2/ERR_REGION=3/ERR_VERIFY=4`。
- 超时:`QSPI_CMD_TIMEOUT_MS=100`、`QSPI_FIFO_TIMEOUT_MS=100`、
  `QSPI_DMA_TIMEOUT_MS=1000`、`QSPI_BUSY_TIMEOUT_MS=2000`(RDSR 自动轮询覆盖
  扇区擦除最坏耗时,取 2s 余量)。
- 容量 `QSPI_FLASH_CAPACITY=8MB`;自检区 `QSPI_SELFTEST_ADDR=0x7F0000`/
  `QSPI_SELFTEST_SIZE=0x10000`(契约 §0.4)。生产写/擦区间与自检区**相交即拒**
  `QSPI_ERR_REGION`;自检写/擦区间**必须完整落在自检区内**否则拒。
- JEDEC 白名单 `{0xEF4018,0x1C4018,0x1C4017,0xEF4017}`(契约 §0.7);读失败或
  白名单外 → `g_qspi_ota_disabled=true`(既有功能不受影响)。
- DMA done 超时兜底:停 stream + 关 QSPI DMA 再返错,避免残留 DMA 打断后续外设。

### 6.3 自检/压测入口(`CONFIG_QSPI_SELFTEST_ENABLE=1`,gated)
- `Qspi_SelfTest`(`HAL_W25Q128.cpp`):**1000 次**(`QSPI_SELFTEST_ITERS`)
  迭代,轮转 16 个自检扇区(`n % 16`),每轮 `擦(qspi_erase_selftest)→
  写 4KB(qspi_data_write_selftest,内容含迭代号 n 防残留误判)→ XIP 读回
  memcmp → 回命令口`;任一步失败计 fail 并打 RTT 行。
- **注错子测**:`qspi_probe_timeout(5ms)`(不 kick 命令等 CMDSTS)必须返回
  `QSPI_ERR_TIMEOUT`,RTT 打 `QSPISELF: inject timeout rc=1 (PASS)` —— 证明
  fail-closed 生效、绝不死循环。
- RTT 标记:`QSPISELF: start 1000 iters ...` → `QSPISELF: done ok=1000 fail=0 / 1000`。
  输出全走 `SEGGER_RTT_printf(0,...)`(Serial5 UART logger 抓不到,沿用 P0-4 惯例)。

### 6.4 验证证据(实现会话,AC5/Keil `build_f435.ps1 -AutoStale`)
- 默认(selftest=0)构建:armlink/fromelf exit 0,**0 Error 0 Warning**,
  `Program Size: Code=263500 RO-data=288308 RW-data=1244 ZI-data=453392`;
  产物 `X-Track.axf/hex Track.bin` mtime 2026-07-25 20:21。
- selftest=1 构建(仅证明 1000 迭代自检路径可链接):exit 0 0E0W,
  `Program Size: Code=264972 RO-data=288308 RW-data=1244 ZI-data=461584`
  (ZI 增 ~8KB = 两个 4KB 自检静态缓冲);采证后已恢复 flag=0 并重建默认固件
  (Code=263500 ZI=453392,与基线逐字一致)。
- GCC/Linux CI 可移植:改动文件 include 反斜杠 grep = **0**(POSIX 正斜杠)。
- `git diff --check`:无空白错误(仅 LF→CRLF 提示)。
- 未新增源文件 → 无需改 `proj.uvprojx`/`cmake-generated/CMakeLists.txt`。

### 6.5 OTA 规约遵守
- 契约文档与 PLAN-OTA.md 未动;未 commit/push(留主会话);不自验收置完成。
- 真机 1000 次压测/注错超时路径取证 = **验收项**,留非实现会话按 AGENTS.md
  J-Link 流程执行(selftest=1 `-AutoStale` 重编+烧录 → RTT 取
  `QSPISELF: done ok=1000 fail=0 / 1000` + `inject timeout rc=1 (PASS)` +
  `Qspi_Init` 的 JEDEC 命中行;采后恢复 flag=0 重建默认固件并回刷)。

---

## 7. 验收打回整改(2026-07-25,应 `P0-5-acceptance-2026-07-25.md`)

### 7.1 打回结论
真机复验:注错超时 `inject timeout rc=1 (PASS)` 与 1000 次擦写读回
`ok=1000 fail=0` **通过**;但 **JEDEC 阻断**——运行态 `g_qspi_jedec_id=0x000000`、
`g_qspi_ota_disabled=1`(未命中白名单),且 JEDEC 日志错走 `CONFIG_DEBUG_SERIAL`
(=Serial5 UART,RTT logger 抓不到),违反 AGENTS.md “验收判定输出必须走 RTT” 红线。

### 7.2 两处根因与修法
1. **RDID 读到 0x000000(读序错)**:`Qspi_Init` 在读 JEDEC 之前**未复位 flash**。
   暖复位(J-Link NRST)只复位 MCU 侧 QSPI 控制器寄存器,**外部 flash 芯片仍保持
   上一轮 `en25qh128a_qspi_xip_init` 设置的连续读/XIP 模式**;此时发 1-1-1 RDID
   (0x9F)不被识别,读回 0x000000。原代码把 RSTEN(0x66)+RST(0x99) 复位序列放在
   `en25qh128a_qspi_xip_init` 里、在 JEDEC 读**之后**才执行。
   - 修:新增 `qspi_flash_reset()`(命令口态发 RSTEN+RST + `delay_us(100)` tRST),
     `Qspi_Init` 改为 **先 `qspi_flash_reset()` 再 `qspi_read_jedec_id()`**。
2. **JEDEC 日志走 Serial5**:两条 `CONFIG_DEBUG_SERIAL.printf` 改为
   `SEGGER_RTT_printf(0,...)`(与 P0-4 BCBSTRESS、App.cpp RTTCMD 惯例一致)。

### 7.3 整改后构建证据(AC5/Keil `-AutoStale`,armlink/fromelf exit 0)
- selftest=1(整改路径可编):0E0W,
  `Program Size: Code=265024 RO-data=288312 RW-data=1244 ZI-data=461584`;
  mtime 2026-07-25 21:40。
- 默认发货态(selftest=0):0E0W,
  `Program Size: Code=263552 RO-data=288312 RW-data=1244 ZI-data=453392`
  (较基线 +52B = `qspi_flash_reset` 新函数);mtime 2026-07-25 21:53;
  已复位 flag=0。
- include 反斜杠 grep=0;未新增源文件。

### 7.4 待非实现会话复验
selftest=1 重编+烧录 → RTT 应得:①`QSPI: JEDEC=0x{EF4018|1C4018|...}
whitelisted, OTA enabled`(走 RTT);②运行态 `g_qspi_ota_disabled=0`;
③`inject timeout rc=1 (PASS)`;④`QSPISELF: done ok=1000 fail=0 / 1000`。
采后恢复 flag=0 重建默认固件并回刷。

---

## 8. 第二次验收打回整改(2026-07-25,应 `P0-5-acceptance-2026-07-25.md` §6)

### 8.1 第二次打回结论
§7 整改后复验:JEDEC 日志已走 RTT(红线满足),注错与 1000 次擦写读回仍通过;
但真机 RDID **仍读 `0x000000`**,运行态 `g_qspi_ota_disabled=1`。
`qspi_flash_reset()` 未解决问题 → 证明**不是读序,而是命令口读取路径本身错**。

### 8.2 根因(命令口小数据读的 rxfifordy 阈值陷阱)
- 本项目此前只做过命令口**写**(擦/写/QE)与 **XIP 读**;从未走过命令口
  **RX FIFO 读回**。§6 原实现逐字节等 `QSPI_RXFIFORDY_FLAG` 再 `qspi_byte_read`。
- 查 vendor 寄存器模型:RX FIFO 阈值枚举**最小档 = `WORD08`(8 word = 32B)**
  (`at32f435_437_qspi.h` `qspi_dma_fifo_thod_type` 无小于 8 word 选项);
  `rxfifordy` 是**阈值触发**标志(FIFO 内 ≥ 阈值字节才置位)。
- RDID 只读 **3 字节**,永远达不到 8 word 阈值 → `rxfifordy` 不置位 →
  逐字节等待在第 0 字节即超时 → `id` 保持 0。(而写路径逐字节等 `txfifordy`
  能工作,因为 txfifordy 语义是“FIFO 有空位”,上电即真,与阈值无关。)
- 这与 §7 的“读序/复位”是**两个独立问题**;§7 修的复位仍有必要(退连续读模式),
  但小数据读的 FIFO 取数方式才是 JEDEC=0 的直接原因。

### 8.3 修法(CMDSTS 完成后直接连续取数,不依赖阈值触发)
`qspi_read_jedec_id` 改为:kick → **先等 `QSPI_CMDSTS_FLAG` 命令完成**(硬件此时
已把全部 `dcnt`=3 字节搬入 RX FIFO;CMDSTS 全项目在用、确证可靠、带超时 fail-closed)
→ 再**连续** `qspi_byte_read` 取 3 字节(不再 poll 阈值触发的 `rxfifordy`)→
清 CMDSTS。诊断:`Qspi_Init` 捕获 `qspi_read_jedec_id` 的 rc 并入 RTT 行
(`JEDEC=0x.. rc=%d`),便于区分“读超时(rc=1)”与“读到全零(rc=0,id=0)”。

### 8.4 整改后构建证据(AC5/Keil `-AutoStale`,armlink/fromelf exit 0)
- 默认发货态(selftest=0):0E0W,
  `Program Size: Code=263556 RO-data=288308 RW-data=1244 ZI-data=453392`;
  mtime 2026-07-25 23:08;已复位 flag=0。
- selftest=1(整改路径可编):0E0W,
  `Program Size: Code=265028 RO-data=288308 RW-data=1244 ZI-data=461584`;
  mtime 2026-07-25 23:05。
- include 反斜杠 grep=0;未新增源文件。

### 8.5 待非实现会话复验(同 §7.4,附诊断口径)
- 命中:RTT `QSPI: JEDEC=0x{EF4018|1C4018|1C4017|EF4017} whitelisted, OTA enabled`
  + 运行态 `g_qspi_ota_disabled=0`。
- 若仍失败,看 rc:`rc=1` = CMDSTS 超时(命令口/复位链问题);`rc=0 但 id=0` =
  命令完成但读到全零(需查 flash 是否真在命令口态、片选/时钟或 dcnt 语义)。
- 注错 `inject timeout rc=1 (PASS)` 与 `QSPISELF: done ok=1000 fail=0 / 1000` 应持续通过。
- 采后恢复 flag=0 重建默认固件并回刷。
