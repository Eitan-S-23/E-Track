# P3-3 恢复用 GCC Boot 构建绑定与命令离线验证 —— 2026-09-13

> 依据用户 2026-09-13 第三轮裁定第 3 条：P5 现版 R0-R5 尚不能执行，实际
> 恢复路线是「清空 BCB → NONE → 根据有效 App 重建 CONFIRMED」，不是
> TEST_BOOT 全流程。**本批授权范围**：在项目内构建恢复用 GCC Boot、绑定
> 产物身份、离线验证命令生成与解析。**未授权、未执行**：烧录、连接设备、
> 清空 BCB、修改生产 Boot/BCB/OTA 逻辑。六项细节修正（a-f）补齐后集中
> 审批一次，不先上板尝试。

## 1. 构建（P1_6_TEST_ENABLE=ON 的恢复用 GCC Boot）

构建目录：`<worktree>/.cache/p3-3-recovery-boot/`（worktree 内忽略目录，
独立于生产 `build-gcc-release`，不影响任何生产产物）。

命令（bash，worktree 根目录；与 CI 同参数另加 P1_6 开关）：

```bash
SOURCE_DATE_EPOCH=1786320000 cmake -S MDK-ARM_F435/cmake-generated \
  -B .cache/p3-3-recovery-boot -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OBJECT_PATH_MAX=1024 -DP1_6_TEST_ENABLE=ON
cmake --build .cache/p3-3-recovery-boot --target X_Track_Boot --parallel
```

- 配置：GNU Arm Embedded GCC 13.3.1（`arm-none-eabi-toolchain.cmake` 接线），
  configure 成功；`P1_6_TEST_ENABLE` 与 P2_1/P2_2/P2_3/P2_6 互斥项默认全 OFF，
  单开合法（`MDK-ARM_F435/cmake-generated/CMakeLists.txt` option 定义）。
- 启用效果：`BOOT_PROJECT_SOURCES` 追加 `boot/src/boot_p1_6_test.c`，
  `X_Track_Boot`/`X_Track_App_GCC` 定义 `P1_6_TEST_ENABLE`，OTA 链接定义追加
  `-DP1_6_TEST_ENABLE=1`。**只构建 `X_Track_Boot` 目标，未构建/触碰 App**。
- 构建：exit 0，无 error。关键输出：
  - FLASH 用量 18,720 B / 64 KB（28.56%）
  - RAM 用量 14,136 B
  - `P1_6_CTRL` 段 512 B / 512 B（100%，控制块段落位）
  - `arm-none-eabi-size`: text 18,716 / data 4 / bss 14,644

### 1.1 产物身份（构建树 `boot/` 下，2026-09-13 15:13 本机）

| 产物 | size | SHA-256 |
| --- | --- | --- |
| `X-Track-Boot.elf` | 42,968 B | `c2fd838c940316a36aaa0a75ac0ac2e6f86eeeac819d64508ffca5c7db1d6853` |
| `X-Track-Boot.hex` | 52,727 B | `409d4f1690b80f5e5b3ce8169119bdd462dea87a60822c104693c5e8c216cbb4` |
| `X-Track-Boot.bin` | 18,720 B | `abd042db09b27198d2c52e9ee4e8c15d0c524bd28cb55023dd2aecac9098ce55` |
| `X-Track-Boot.map` | 121,507 B | `268e4a4c03ac7b05f12741758cd8f4a48d5599b082a666f99d3e7c0a98544f97` |

### 1.2 写入范围实证（修正 e 项输入：不预设 16KB，按实际 HEX 核）

Python 解析 Intel HEX（含 extended linear address 记录）实测地址范围：

- HEX 覆盖 **0x08000000 – 0x0800491F**（18,720 B，与 `.bin` 尺寸一致）。
- 全部落在 Boot 64KB 区 `[0x08000000, 0x08010000)` 内，断言通过；对
  64KB 区上界裕量 46,816 B。
- 烧录（若将来获批）的写入/擦除范围以本 HEX 与 J-Link AT32F435RGT7
  烧录算法为准：**擦除按 flash 扇区对齐**（AT32F435 sector 2KB/4KB，
  实际擦除范围 ≥ HEX 覆盖范围，上界仍封在 Boot 64KB 区内），不预设
  「只写 16KB」或「只写 18,720B」。App 区 0x08010000（内部 Flash，
  非 QSPI）不受本次 Boot 构建影响。

## 2. 命令生成与解析的离线验证（零设备、零 J-Link）

验证脚本（入库，ASCII-only）：`docs/ota-exec-notes/tools/p3-3-recovery-cmd-verify.ps1`
运行输出：`.cache/p3-3-recovery-boot/cmd-verify.log`（exit 0）。

复用 `Tools/jlink/p1-6-common.ps1` 纯函数与 `Tools/jlink/p1_6_protocol.py`
（command/arm/decode 子命令均为纯本地计算；dot-source 阶段仅读
`ota_layout.h`/`ota_p1_6_test.h` 宏，不启动任何 J-Link 进程）：

- `New-P16EncodedBlock`（生成 staged/committed/magic 三件并内部结构自校验）
- `Get-P16DecodedControl`（decode 子命令解析 + CRC/inverse 校验）
- `Get-P16WordWriteLines`（纯文本生成 J-Link 写块命令行，本批不执行）

控制块事实（脚本运行实测，供 v3 操作单直接引用）：

| 项 | 值 |
| --- | --- |
| 控制块 RAM 地址 | `0x20057E00`（OTA_RAM 末尾 512B） |
| 控制块尺寸 | 512 B |
| COMMAND magic | `0x43365045` |
| ARM magic | `0x41365045` |
| DONE magic | `0x44365045` |

### 2.1 验证矩阵（13 项全 PASS）

| # | 验证 | 结果 |
| --- | --- | --- |
| T1 | CLEAR_BCB（opcode=1）命令块生成→解析往返：kind/magic/version/opcode/CRC/inverse/valid 全字段断言 | PASS |
| T2 | SNAPSHOT（opcode=4，arg0=BcbOnly=1，arg1/arg3 非零）参数编码往返 | PASS |
| T3 | ARM checkpoint 块（checkpoint=7，target_arg0/arg1 非零）往返：status=Armed(0)、target CRC 有效 | PASS |
| T4 | staged 与 committed **仅 magic 4 字节差异**（diff_bytes=4），staged magic=0 | PASS |
| T4b | staged 块解析 kind=unknown、无任何 valid —— 部分写入不可被误认为有效命令 | PASS |
| T5 | `Get-P16WordWriteLines` 生成 131 行（h + 127×w4 体 + magic w4 + savebin + qc），首体行偏移 4、magic 行最后写、savebin 参数正确 | PASS |
| T5b | magic 非 0 的块作为 staged 输入被拒绝（防时序污染防护本身 fail-closed） | PASS |
| T6 | 篡改 arg0 一字节 → command_crc_valid=false、command_valid=false | PASS |
| T7 | 篡改 opcode（inverse 保持）→ opcode_inverse_valid=false、command_valid=false | PASS |
| T8 | 篡改存储的 command CRC → command_valid=false | PASS |
| T9 | 篡改 ARM target_checkpoint → target_crc_valid=false、arm_valid=false | PASS |
| T10 | magic 改写为 DONE → kind=done、done=true、command/arm 均 invalid | PASS |
| T11 | 尺寸 511/513 字节输入 decode 拒绝（`control block must be 512 bytes`，预期 traceback 已留日志） | PASS |

实测输出（日志原文）：

```
control_address=0x20057E00 control_size=512
magic_command=0x43365045 magic_arm=0x41365045 magic_done=0x44365045
PASS T1 clear_bcb round trip opcode=1
PASS T2 snapshot args round trip
PASS T3 arm checkpoint round trip
PASS T4 staged keeps magic zero diff_bytes=4
PASS T4b staged block is not valid control
PASS T5 word write lines shape lines=131
PASS T5b nonzero-magic staged rejected
PASS T6 arg0 tamper rejected
PASS T7 opcode tamper rejected
PASS T8 command crc tamper rejected
PASS T9 arm target tamper rejected
PASS T10 done magic recognized
PASS T11 size guard rejects wrong sizes
verify_total passed=13 failed=0
VERIFY_RESULT=PASS
```

过程缺陷（如实记录，已修复）：首轮 T2 用 `0xA5A5A5A5` 作为 uint32 参数，
Windows PowerShell 5.1 把该字面量解析为 int32 负值（-1515870811）导致参数
转换失败；改为 int32 域内值 `0x5A5A5A5A` 后全绿。该陷阱对 v3 操作单同样
适用：**向 `New-P16EncodedBlock` 传高位字面量时必须显式 `[uint32]` 或避免
≥0x80000000 的裸字面量**。

## 3. 对 v3 恢复方案的直接输入

- 每命令控制块地址/尺寸/magic 值见 §2 表（修正 a 项的"完整控制块"要素）。
- 提交时序语义已离线证明：staged（magic=0）逐字写入 → 最后一次 w4 写
  magic 提交；部分写入的块不会被固件认作有效命令（T4b）。
- 命令编码（CLEAR_BCB/SNAPSHOT/ARM）往返一致，CRC/inverse/尺寸防篡改
  拒绝语义 fail-closed（T6-T11）。
- Boot 写入范围实证见 §1.2（修正 e 项）。
- 本批不证明：固件在真机上对这些命令的实际行为（需上板授权）、
  TEST_BOOT 状态机全流程（v3 已按用户裁定改为清空 BCB 路线）。

## 4. 边界声明

- 本批未烧录、未连接设备、未读写 BCB、未修改生产 Boot/BCB/OTA 源码；
  构建与验证全部发生在项目内 `.cache/` 与 `docs/` 路径。
- 构建产物仅在获批后按 v3 操作单使用；届时以本文件 §1.1 哈希核对
  被烧录文件身份。
- `X_Track_App_GCC` 未在本构建目录构建；生产 App 链不受影响。
