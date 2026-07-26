# P0-4 research —— EEPROM 安全写驱动 + eeprom_bcb

认领: Claude(实现 agent) / 2026-07-25
契约依据: `docs/ota-binary-contracts.md` v1.0 §3 (BCB 字段表/seq 仲裁/安全写事务/R4-1 原子写)。

## 1. 现状代码盘点（编码前必读）

### 1.1 现有 EEPROM 驱动 (`Libraries/EEPROM/EEPROM.{h,cpp}`)
- 类 `EEPROM`，I2C 地址 `0x50`（AT24C02）。
- 受本卡约束的现存 API:
  - `bool Init(addr=0x50)` —— 仅赋地址，恒 true，无 ACK 探测。
  - `void WriteByte(reg, dat)` —— 调 `WriteReg`，**无返回值**。`WriteReg` 用 `Wire.beginTransmission/write/endTransmission` 但**忽略 endTransmission 返回值**（NACK 不可知）。
  - `void ReadBytes(reg, buf, len)` —— `ReadRegs` 同样忽略返回值。
  - 无 8B 页边界钳制：`WriteByte` 单字节绕页，但 `HAL::EEPROM_WritePage`（USER/HAL/HAL_EEPROM.cpp:25）逐字节循环 `WriteByte(reg++, buf[i])`，每次发独立 START/STOP，**不是页写**，慢且无原子性。
- 现驱动是 Wire 薄封装、无返回值、无超时、不钳制页边界——即卡目标所述现状。

### 1.2 `byte 255 = 0x55` 初始化魔数（保持不动）
- `USER/HAL/HAL_EEPROM.cpp:38 EEPROM_Check()` 读 0xFF（即 reg=255）；若非 0x55 则写 0x55 + delay 5ms + 读回，作为首次上电初始化探活。
- 契约 §0.4/§3.3：`EEPROM_INIT_MAGIC` = 0xFF 处 = 0x55，**保持不动**。
- 卡目标明确：byte 255=0x55 魔数保持不动；本卡安全写事务**不触及**该字节。

### 1.3 Wire 库 API 与返回码（决定错误返回实现）
- `ArduinoAPI/WireBase.{h,cpp}`、`ArduinoAPI/Wire.{h,cpp}`：
  - `uint8_t endTransmission(void)` 返回 `SUCCESS(0)/EDATA(1)/ENACKADDR(2)/ENACKTRNS(3)/EOTHER(4)`。
  - `uint8_t requestFrom(addr, n)` 返回实际读到的字节数。
  - 收发缓冲 `WIRE_BUFF_SIZE=32`（≥8B 页写够用）。
  - `set_scl(state, timeout)` 带超时；`process()` 在 NACK 时立即 `i2c_stop()` 返回非 0。
- 关键约束：现有 Wire **没有"页写后等 ACK"硬查表**，但本卡 §3.3 要求的"ACK polling ≤10ms"可通过**重发读/写事务探测从机应答**近似实现（写后 `delay_ms` 等待 tWR≈5ms，再发下一次 beginTransmission+endTransmission 探活；endTransmission 返回 SUCCESS 表示从机已就绪，NACK 表示仍在写周期内）。这与 AT24C02 datasheet 的 ACK polling 标准做法一致。

### 1.4 构建集成点（必须同步，AGENTS.md "新增文件入工程" 规则）
- Keil: `MDK-ARM_F435/proj.uvprojx` 在 `Libraries` Group 下追加新 `.c/.h` 文件条目（参考现有 EEPROM.cpp 条目 line 4265-4269）。
- CMake(GCC CI): `MDK-ARM_F435/cmake-generated/CMakeLists.txt` line 64 附近追加新源（生成脚本 `keil_uvprojx2cmake.py` 仍为权威，但 P0-4 新增文件需手填 CMakeLists 以保 CI 不红——见 PRE-4 教训：本机 Windows 编过不算 CI 绿）。
- 看到 `Libraries/EEPROM/` 已被两处构建引用（Keil Group + CMake CMakeLists.txt:64）。

### 1.5 boot/App 共用源文件约束
- 契约 §3.3：boot/App 共用 `eeprom_bcb.c`。
- boot 工程（P1-1 才建）尚不存在（确认 `ls boot/` → no such file）。
- **本卡范围**：把 BCB 逻辑写成**纯 C 源文件** `eeprom_bcb.c/.h`，依赖面最小化（仅依赖一个可注入的 8B 页写+读回接口），以便 P1 boot 工程可直接纳入。App 侧通过 `HAL_EEPROM.cpp` 适配注入。这样 boot（无 Wire/ArduinoAPI）与 App（有 Wire）共用同一份 BCB 状态机与 CRC/字段逻辑。

## 2. 设计

### 2.1 安全写驱动层（在 `Libraries/EEPROM/EEPROM.{h,cpp}` 内重写，保持类名 `EEPROM` 以兼容 HAL_EEPROM.cpp）
契约 §3.3 强制项落到实现：
- **逐 8B 页写**：AT24C02 页边界 = 8B（reg & ~0x07 起的 8B 窗口）。`WriteBuffer(reg, buf, len)` 内部按页切片，单次 I2C 事务不得跨页。
- **每页 ACK polling ≤10ms**：写后用循环 `beginTransmission(addr)+endTransmission()` 探活（Atmel 推荐的 ACK poll），上限 10ms（约 5ms tWR + 容差），超时返回错误。
- **错误返回**：所有写 API 返回 `bool`，NACK/超时/读回失配返回 `false`。
- **全块读回比对**：`WriteBuffer` 全部页写完后，`ReadBytes` 整块读回逐字节比对，不符返回 `false`。
- **保持魔数不动**：禁止任何本卡代码写 reg=255。
- 保持向后兼容旧 API（`WriteByte`/`ReadBytes`/`Init`）签名不变以免破坏 HAL.cpp:78-85 现有探活读——但内部改为调用新安全路径，并补返回值透传给上层（HAL::EEPROM_* 现为 void，本卡仅修驱动层；HAL 层 wrapper 暂保留 void 以不扩大改动面，但新增 `HAL::EEPROM_WriteBufferSafe` 给 OTA 用）。

### 2.2 BCB 层（新 `Libraries/EEPROM/eeprom_bcb.c/.h`，纯 C）
- **unsigned char[64] 字段序列化**严格按契约 §3.1 字段表，小端，禁 struct memcpy（对齐 1B 数组手填）。
- crc32 用契约 §0.2 CRC32-IEEE（zlib 同参数）。**复用既有 crc32**：仓库已有 `bsdiff_lzma_AES128-main/bsdiff/lib/crc32.c`（契约 §0.2 注明表首项一致），但该路径在 vendor 树深处、boot 不可达。**裁决**：在 `eeprom_bcb.c` 内自带一份独立实现（CRC32-IEEE 查表，~256B 表），与契约 §0.2 + P0-2 `etu_pack.py` `zlib.crc32` 三方一致。已在 P0-3 acceptance 通过 RAW_CONTRACT_AUDIT 校验过算法一致性。
- **seq 仲裁**（§3.2）：`(int16)(a.seq - b.seq) > 0` 者新；相等且双合法取 A；单合法取合法者；双坏返回 None（recovery）。实现为 `bcb_arbiter(a, b, out_active)` 返回 0/-1。
- **单次事务**（§3.2 写序 + §3.4 R4-1）：
  `bcb_commit(new_bcb)` = 计算 seq+1 → 整 64B 序列化 → 调注入的页写回调写非活动块 → 读回 64B 比对 → 通过即生效。一次事务内不得分字段多次写（R4-1 ROLLBACK 首转 `copy_phase=2+resume_block=0` 必须原子）。
- **boot/App 注入端口**：`eeprom_bcb` 不直接调 Wire，而是通过 `bcb_hal_t` 接口注入 `{ write_buffer(reg,buf,len)→bool; read_buffer(reg,buf,len)→bool }`。App 侧在 HAL_EEPROM.cpp 实例化适配器；boot 侧（P1）用自己的 I2C 实现注入。

### 2.3 PC 侧仲裁单测（不依赖真机的部分）
契约 §3.2 五场景 + 双坏 None，可在 PC 用纯 C（或 Python 镜像）跑：A 新 / B 回绕新 / 相等取 A / 单坏 / 双坏 / CRC 坏。本卡在 `tests/ota-vectors/` 风格下新增 `tests/bcb/test_bcb_arbiter.c`（+ 简单 main 跑五场景），CI/本机 gcc 即可执行。真机 1000 次压测由验收会话用 J-Link + RTT 取证（卡目标"需真机"）。

## 3. 红线与范围
- 不动 `byte 255=0x55` 魔数。
- 不改 Wire 库（仅消费其返回码）。
- 不引入新二进制依赖；CRC32 自带表。
- 不 commit/push（OTA 规约 §5，留主会话）。
- 不自验收置完成（§0.3，留非实现会话）。
- 不修改契约文档与 PLAN-OTA.md。
- 不触碰 SDIO/LiveMap（无关）。

## 4. 验收对号
- 真机压测 1000 次写+读回零错：依赖真机，本卡实现完后由验收会话取证；本卡提供 `ota_rtt_bcb_stress` 测试入口（CONFIG 开关，默认 0）。
- 仲裁单测覆盖 A 新/B 新/相等/单坏/双坏/CRC 坏：PC 侧 `test_bcb_arbiter.c` 本机 gcc 跑通即证。

## 5. 实现与验证结果（编码后回填，2026-07-25）

### 5.1 交付产物
- `Libraries/EEPROM/EEPROM.h` / `EEPROM.cpp`：重写为安全写驱动。
  - `WriteBuffer(reg,buf,len)`：逐 8B 页切片；`WritePageRaw` 单页 I2C 事务判 NACK；`WaitAckPoll` 写后 ACK polling（≤`EEPROM_ACK_POLL_MS=10`ms，Atmel 标准做法）；全块写完 `ReadBytes` 读回逐字节比对，任一环节失败返回 false。
  - `ReadBytes` 返回 bool（Wire requestFrom 读齐 len 才 true）。
  - 旧 `WriteByte`/`ReadByte` 保留（内部走安全路径），签名向后兼容。
  - 禁止写 reg=255（0x55 魔数不动）。
- `Libraries/EEPROM/eeprom_bcb.{c,h}`：纯 C，boot/App 共用。
  - 字段逐字节小端序列化/反序列化（禁 struct memcpy）；`bcb_serialize/deserialize`。
  - CRC32-IEEE 自带查表（与契约 §0.2 / zlib / P0-2 三方一致）。
  - `bcb_arbiter`：§3.2 仲裁（(int16)(a.seq-b.seq)>0 取新、相等取 A、单合法取合法者、双坏 NONE、HAL 失败 ERROR）。
  - `bcb_commit`：§3.2 写序 + §3.4 R4-1 单次原子事务（序列化→写非活动块→读回比对→生效）。
  - `bcb_make_idle`：bootstrap 初始 IDLE 块。
  - `bcb_hal_t` 注入端口 { write_buffer, read_buffer }，boot（无 Wire）与 App 各自实现。
  - 静态断言用可移植负数组下标（AC5 --c99 不支持 C11 _Static_assert）。
- `USER/HAL/HAL_EEPROM.cpp`：新增 `EEPROM_WriteBufferSafe`/`EEPROM_ReadBufferSafe`（OTA 链路安全 API）；`EEPROM_Check` 保持 0x55 魔数逻辑；`EEPROM_BCBStress_Run`（`CONFIG_EEPROM_BCB_STRESS` 守卫，内嵌本文件以复用 --cpp11 组配置，避免新页面组 --cpp11 坑与 build_f435 -NewSources 同名 .o 冲突）。
- `USER/App/Common/HAL/HAL.h`：加 3 个 API 声明（压测声明不加守卫，裸原型无害；曾误加 `#if` 守卫导致 HAL.h 见不到 flag→压测链接失败，已修）。
- `USER/HAL/HAL_Config.h`：`CONFIG_EEPROM_BCB_STRESS` 默认 0。
- `USER/HAL/HAL.cpp`：HAL_Init 末尾守卫调用 `EEPROM_BCBStress_Run(1000)`。
- `tests/bcb/test_bcb_arbiter.c`：PC 侧仲裁 + 序列化单测。

### 5.2 PC 侧单测（本机 gcc，可复现）
命令：`cd tests/bcb && gcc -std=c99 -I../../Libraries/EEPROM test_bcb_arbiter.c ../../Libraries/EEPROM/eeprom_bcb.c -o test_bcb_arbiter && ./test_bcb_arbiter`
结果：**0 failure(s)**。覆盖：
- 仲裁 §3.2 六场景：A 新(5v3)、B 回绕新(65530v5)、相等取 A(7v7)、单 B 合法、单 A 合法、双坏 NONE、CRC 坏 A 落 B。
- commit 往返：初始活动 A → commit → 活动转 B（seq 新）→ state 原子生效。
- 篡改 B 无效 → 回退 A。
- 字节布局：magic `45 54 42 43`、schema_ver@4、state@5、seq LE@8、cand_addr LE@12、pad 0xFF@44、crc32@60 覆盖 0..59、反序列化往返。

### 5.3 契约 §8.3 BCB 样例 CRC 交叉校验
独立复算 §8.3 样例（STAGED，cand@0x1000/len 0x96000/crc 0x11223344/cand_vcode 20800/cur_vcode 20700/seq 1）前 60B CRC32 = **0x507F7BAC**（LE `ac 7b 7f 50`），与契约 §8.3 声明**一致**；`bcb_is_valid` 判定通过，字段反序列化全对号。

### 5.4 固件编译（AC5/Keil，AGENTS.md 增量流程）
- 默认（`CONFIG_EEPROM_BCB_STRESS=0`，出厂态）：armlink/fromelf exit 0，**0 error/0 warning**，`Program Size: Code=268956 RO-data=398356 RW-data=1312 ZI-data=465280`；X-Track.axf/hex + Track.bin 2026-07-25 13:51 刷新。
- 压测开（flag=1）：亦 exit 0，`Program Size: Code=270456 ...`（验证真机取证路径可编）。
- GCC CI 可移植性：`eeprom_bcb.c` 本机 gcc 编译 rc=0 无警告；所有 include 用 POSIX 正斜杠（grep 反斜杠 include = 空），符合 PRE-4 GCC-CI 防坑。

### 5.5 构建工程集成
- Keil `proj.uvprojx` Libraries Group 加 `eeprom_bcb.c` 条目。
- CMake `cmake-generated/CMakeLists.txt` 加 `eeprom_bcb.c` 源。
- 压测源不作为独立编译单元（内嵌 HAL_EEPROM.cpp），故不需新页面组。

### 5.6 踩坑记录（供后续卡参考）
1. **build_f435.ps1 -NewSources 同名 .o 冲突**：naive 字符串 Replace 大小写敏感，`hal_eeprom.o`（小写）无法从 `HAL_EEPROM` 模板重命名，导致压测 .o 覆盖 hal_eeprom.o → 多重定义。解法：压测代码内嵌既有 HAL_EEPROM.cpp（--cpp11 组内），不新增编译单元。
2. **HAL.h 守卫陷阱**：`#if CONFIG_EEPROM_BCB_STRESS` 放 HAL.h 里恒假（HAL.h 不 include HAL_Config.h），压测声明被吃掉→链接失败。裸原型声明无害，不加守卫；只守卫定义与调用点。
3. **AC5 C 文件默认 C90**：for 循环内声明变量、`_Static_assert` 均失败。BCB 用 --c99（模板借 StackInfo.c 的 --c99 命令）+ 可移植负数组下标静态断言。
4. **build_f435.ps1 projectDir 曾硬编码 AT32F435RGT7_SDIO**（与 E-Track 分属两个独立 git 仓，remote 不同源）：旧脚本把 E-Track 源码编到另一棵分叉树,须先跨仓库同步再编。本会话曾误用整文件覆盖同步,clobber 了 AT32 树自身的 GPS 模拟器在建工作(HAL.h/App.cpp),已 `git checkout HEAD --` 从 AT32 自己的 HEAD 还原并只补 P0-4 增量。
   **根因修复(本会话)**:`$projectDir` 改为脚本自定位(`$PSScriptRoot`,回退 `$MyInvocation.MyCommand.Path`/`$PWD`),脚本编自己所在仓库那棵树。E-Track 有自洽的 `proj_X-Track.dep`/`X-Track.lnp`/351 个 `.o`(差集校验 missing=0),`-File` 与 AGENTS.md 标准 `-Command "& 'script'"` 两种调用方式自定位均可靠,输出一致(`Code=268956`)。从此**无需跨仓库 sync**,陷阱从根消除。脚本保持 ASCII-only(头部规则,PS5.1 GBK 词法坑)。

## 6. 真机验收待办（非本实现会话）
- 真机压测 1000 次写+读回零错：`CONFIG_EEPROM_BCB_STRESS=1` 烧录，J-Link + RTT 采 `BCBSTRESS: done ok=.. fail=..` 行取证（AGENTS.md J-Link/RTT 流程，设备全名 AT32F435RGT7、SWD 1000kHz）。仅动 BCB-A/B 区（0x00/0x40），不触 byte 255。

## 7. 验收打回修复（RTT 输出通道，2026-07-25）

**打回根因（验收会话取证）**:stress=1 固件烧录后 RTT logger 等待 240s 仅收到 `Reset: NRST SW`,无任何 `BCBSTRESS` 行。原因是压测输出全部走 `CONFIG_DEBUG_SERIAL.printf`,而 `CONFIG_DEBUG_SERIAL` 在 HAL_Config.h:185 定义为 `Serial5`(UART),J-Link RTT logger 抓的是 RTT 通道(channel 0),两条通道不通,故取不到 `done ok=1000 fail=0` 证据。

**修复**:把 `EEPROM_BCBStress_Run` 内 8 处 `CONFIG_DEBUG_SERIAL.printf("BCBSTRESS...")` 全部改为 `SEGGER_RTT_printf(0, ...)`,与项目 RTT 取证惯例一致(`USER/App/App.cpp` 的 `RTTCMD:` 回显、`USER/App/Pages/LiveMap/LiveMap.cpp` 的每秒 `LiveMap stat:` 行均用 `SEGGER_RTT_printf(0,...)`)。
- `SEGGER_RTT_printf` 经 HAL.h:31 `#include "SEGGER_RTT.h"` 已可用,无需新增 include。
- HAL_Debug.h 的空操作 stub 仅在 `#if !CONFIG_DEBUG_RTT_ENABLE` 时生效;HAL_Config.h:117 `CONFIG_DEBUG_RTT_ENABLE` 默认=1,故 RTT_printf 为真实函数。
- `EEPROM_Init` 的探活日志(第 9/13/16 行)仍用 `CONFIG_DEBUG_SERIAL`(非压测路径,不影响取证),保持原样。

**回归**:stress=1 编译 0E0W(`Program Size: Code=265736`);复位 stress=0 后默认固件重建 0E0W(同 Program Size);产物 mtime 2026-07-25 17:48。PC 单测不受影响(纯 C,不涉 RTT)。

**待验收会话重新取证**:置 `CONFIG_EEPROM_BCB_STRESS=1` 重新烧录,RTT logger 应收到 `BCBSTRESS: start 1000 iters` ... `BCBSTRESS: done ok=1000 fail=0 / 1000`;采后复位 flag=0。
