# P3-2 验收补证 R10：seq 回显铁证（冻结后加强项）

- 卡：P3-2「GET_INFO 设备身份链」
- 关联轮次：`P3-2-V1-FREEZE-20260903-01`（第 1 轮，结果 `PASS`）
- 本补证执行者：独立验收会话（非 P3-2 实现方）
- 执行时间：2026-09-03
- 结果：**42 项核对全绿，`P3_2_R10=PASS`**
- 与判定的关系：**不改变第 1 轮 `PASS`**。R10 在冻结合同里属
  `scope.excluded_by_freeze`，本文件是冻结后的加强证据，不是补救。

## 1. 为什么需要这一项

第 1 轮真机取证留下一处**证据强度**上的残留质疑（非产品缺陷）：

- 判据 C06 的证据 `artifacts/realdevice/feed_before.bin` 与
  `artifacts/realdevice/info_frame.bin` **逐字节相同**。
- 原因见实现方笔记 `docs/ota-exec-notes/P3-2-implementation-evidence.md` §7.5：
  R3 轮是活体固件的真实观测，但 R4 轮复现时固件已死（PC 停在 Reset_Handler），
  所以那一轮读到的帧是 R3 轮遗留在 RAM 里的旧值。
- 因此 R4 轮**无法单独证明**「帧是这次喂入 GET_INFO 产生的」，只能证明
  「RAM 里存在一个格式与字段全部正确的 INFO 帧」。
- 第 1 轮的判定不依赖这一点：C05 的三方闭合（本仓库重建镜像 → finalize →
  板上 dump 逐字节一致）已把 INFO 里的摘要绑回本仓库源码。所以当时按
  `ENV_BLOCKED` 记为「待 J-Link 物理链路恢复后补」。

R10 要闭掉的正是这一条：**喂入一个 `seq=0x1234` 的请求，看应答帧是否回显
`0x1234`**。历史帧全为 `seq=0`，回显即证明帧由本次喂入产生。

## 2. 方法与独立性划分

硬件操作沿用实现方已调试好的脚本，**解码与重算全部由验收方重写**：

| 环节 | 由谁做 | 文件 |
| --- | --- | --- |
| 复位 / attach / 喂帧 / dump | 实现方脚本 | `.cache/p3-2-realdevice/p3_2_r10_capture.py` |
| 地址前置复核 | 验收方 | 本文件 §3 |
| 解帧 / CRC 重算 / 全部断言 | 验收方独立重写 | `.cache/p3_2_verify_r10.py` |

验收方校验器不 import 实现方任何代码，CRC16-CCITT-FALSE 按位实现（不抄表），
并用「同一实现重算冻结轮 CRC 亦自洽」作为校验器自身无偏的对照。

### R3 轮崩溃的根因与本轮消除方式

R3 轮喂帧后固件崩溃，根因是 GDB inferior call 里执行了
`env.send → ble_env_send → BT_SERIAL.write`（UART 写）。本轮在喂帧前把
`session.env.send` 指向固件内一条 2 字节 `bx lr`：

```
080537a8 <__retarget_lock_init_recursive>:
 80537a8:	4770      	bx	lr
```

`session_send_info` 的 encode 路径照常填充 `tx_frame`，UART 副作用被彻底消除；
取证后恢复原指针。本轮固件全程存活（§6）。

## 3. 地址前置复核（验收方自行核对，不采信实现方数字）

脚本里 5 个硬编码地址 + 2 个结构偏移，全部用本轮干净重建的产物重核：

| 对象 | 脚本值 | 复核来源 | 复核结果 |
| --- | --- | --- | --- |
| `ota_ble_session_feed_idle` | `0x08049B48` | 本轮 nm（包内 `artifacts/build/nm-app-gcc-symbols.txt`） | `08049b48 T` 一致 |
| `_ZL13s_ble_session` | `0x20053058` | 同上 | `20053058 b` 一致 |
| `_ZL14s_ble_identity` | `0x20053008` | 同上 | `20053008 b` 一致 |
| `_ZL12ble_env_sendPKht` | `0x08040BF8` | 同上 | `08040bf8 t` 一致 |
| `__retarget_lock_init_recursive` | `0x080537A8` | 同上 + objdump 反汇编 | `080537a8 T`，指令 `4770 bx lr` |
| `env.send` 字段偏移 4 | — | 冻结 `sess_full.bin` 的 `u32@4` | `0x08040BF9`（= `ble_env_send`\|1） |
| `tx_frame` 偏移 421 | — | 冻结 `sess_full.bin` 内 `A5 5A` 出现位置 | 全 568B 内仅出现于 421 |

ELF 与板上镜像的对应关系不靠时间戳，靠第 1 轮 C05 的三方闭合：
`finalize(重建 App.bin) == 板上 dump`，SHA-256
`4512de0878c146a93b55f65aa86acab4eedcf7f7082ead97ad73c24884671b4b`。

## 4. 采集原始字节

喂入请求（GET_INFO，`seq=0x1234`，CRC 由验收方重算得 `0xC50B`）：

```
a5 5a 00 00 34 12 00 00 0b c5
```

喂帧前 `tx_frame`（60B，复位后 session init 清零）：

```
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

喂帧后 `tx_frame`（60B，INFO 应答）：

```
a5 5a 80 00 34 12 32 00 45 2d 54 72 61 63 6b 00 01 00 01 01
f8 75 00 00 45 12 de 08 78 c1 46 a9 3b 55 f6 5a a8 6a ca b4
ee dc f7 f7 08 2e ad 97 ad 73 c2 48 84 67 1b 4b 01 20 6b c2
```

`s_ble_identity` 快照（60B）：

```
01 00 00 00 45 2d 54 72 61 63 6b 00 01 00 01 01 f8 75 00 00
45 12 de 08 78 c1 46 a9 3b 55 f6 5a a8 6a ca b4 ee dc f7 f7
08 2e ad 97 ad 73 c2 48 84 67 1b 4b 00 00 00 00 01 00 00 00
```

对照：第 1 轮冻结的 INFO 帧（`seq=0`，包内
`artifacts/realdevice/info_frame.bin`）：

```
a5 5a 80 00 00 00 32 00 45 2d 54 72 61 63 6b 00 01 00 01 01
f8 75 00 00 45 12 de 08 78 c1 46 a9 3b 55 f6 5a a8 6a ca b4
ee dc f7 f7 08 2e ad 97 ad 73 c2 48 84 67 1b 4b 01 20 4f 1b
```

**两轮整帧差异恰好 4 字节，位置 `[4,5]`（seq）与 `[58,59]`（CRC）。**
50B payload 逐字节相同 —— seq 变了、身份没变，正是协议期望的行为。

## 5. 命令与核对输出

```
python -X utf8 -B .cache/p3-2-realdevice/p3_2_r10_capture.py
jlink_reset_exit=0
等待固件启动 15s ...
gdb_exit=0
P3_2_R10_ATTACH_PC=0x8026432
P3_2_R10_SEND_STUB=0x80537a9
P3_2_R10_FEED_DONE
P3_2_R10_SEND_RESTORED=0x8040bf9
P3_2_R10_PC_AFTER=0x8026432
P3_2_R10_DUMP_DONE
退出码 0
```

```
python -X utf8 -B .cache/p3_2_verify_r10.py
== A. 复位后基线：RAM 残留已排除 ==
  ok   喂帧前 tx_frame 快照长度 = 60
  ok   喂帧前 tx_frame 全零（复位后 session init 清零） = 所有 60 字节为 0x00
  ok   喂帧前后不同（帧确由本次喂入产生，非 RAM 残留） = True
  ok   对照：冻结轮(R4) before==after，正是本轮要排除的残留质疑 = True
== B. seq 回显：请求与应答一一绑定 ==
  ok   喂入请求自身 CRC 独立重算一致（请求合法，设备才会应答） = 0xc50b
  ok   喂入请求 seq = 0x1234
  ok   喂入请求 cmd = 0x00 GET_INFO = 0x0
  ok   应答帧 seq 回显 == 喂入请求 seq = 0x1234
  ok   冻结轮应答 seq = 0（两轮可区分） = 0x0
  ok   本轮 seq 与冻结轮 seq 不同 = True
== C. 线格式自洽（§5.1，本文件独立重算）==
  ok   帧总长 = 8 头 + 50 payload + 2 CRC = 60
  ok   magic A5 5A = a55a
  ok   cmd = 0x80 INFO = 0x80
  ok   session = 0（GET_INFO 无会话） = 0
  ok   len 字段 = 50 = 50
  ok   len 字段与帧总长自洽 = 60
  ok   CRC16-CCITT-FALSE 覆盖 cmd..payload、按位重算 == 上线值 = 0xc26b
  ok   同一实现重算冻结轮 CRC 亦自洽（校验器本身无偏） = 0x1b4f
  ok   两轮 CRC 不同（seq 入 CRC 覆盖范围） = 0xc26b vs 0x1b4f
== D. payload 逐字节与冻结轮同一（身份未因 seq 改变）==
  ok   50B payload 与冻结轮逐字节相同 = 50
  ok   两轮整帧差异位置仅 seq(4,5) 与 CRC(58,59) = [4, 5, 58, 59]
  ok   两轮整帧差异字节数 = 4
== E. payload 字段仍满足 §5.2.1 冻结偏移（独立重解）==
  ok   model 偏移 0 长 8 ASCIIZ = b'E-Track\x00'
  ok   hw_rev 偏移 8 = 1
  ok   layout_id 偏移 10 = 1
  ok   boot_ver 偏移 11 = 1
  ok   cur_vcode 偏移 12 (3.2.0) = 30200
  ok   proto_ver 偏移 48 恒 1 = 1
  ok   max_window_segs 偏移 49 恒 32 = 32
  ok   image_sha256 == 本轮三方闭合的 raw 身份摘要（绑回本仓库重建镜像） = 4512de0878c146a93b55f65aa86acab4eedcf7f7082ead97ad73c24884671b4b
== F. 固件存活与调试副作用可控 ==
  ok   喂帧前后 PC 相同（未进 fault、未崩） = 0x8026432
  ok   PC 不在复位向量（R4 轮死机特征已消除） = 0x8026432
  ok   取证期间 env.send 指向 bx lr 桩（消除 UART 副作用） = 0x80537a9
  ok   取证后 env.send 已恢复为 ble_env_send|1 = 0x8040bf9
  ok   取证前 env.send 原值即 ble_env_send|1（桩替换是可逆的） = 0x8040bf9
  ok   会话结构 dump 时刻 env.send 为桩（dump 与替换同一时序） = 0x80537a9
  ok   s_ble_session 整结构长度 = 568
  ok   结构内 A5 5A 仅出现一次且在 tx_frame 偏移 421 = [421]
  ok   整结构切片 == 单独 dump 的帧（两次读一致） = True
  ok   s_ble_identity 快照 valid = 1 = 1
  ok   快照 model 与 INFO 同源 = b'E-Track\x00'
  ok   快照内含同一 raw 身份摘要 = 4512de0878c146a9

P3_2_R10 checks=42 failures=0
r10_seq=0x1234 r10_crc=0xC26B frozen_seq=0x0000 frozen_crc=0x1B4F
P3_2_R10=PASS
退出码 0
```

## 6. 板子状态与调试副作用

- `ATTACH_PC == PC_AFTER == 0x8026432`，addr2line 解为
  `lv_draw_sw_letter.c` —— 固件在 LVGL 渲染循环里正常运行，既不在
  Reset_Handler 也不在 fault handler。R4 轮的死机特征已消除。
- GDB 会话日志 10 行，无 `Program received`、无 `HardFault`、无
  `Cannot access memory`。
- `env.send` 取证前 `0x08040BF9` → 取证中 `0x080537A9`（桩）→ 取证后恢复
  `0x08040BF9`，三点均有 dump/printf 留痕。
- 未烧录、未改 Flash，只做一次 nrst 复位与若干 RAM 字写。产品源码零改动。

## 7. 产物哈希（原始字节在 git-ignored `.cache/`，故正文已内联全部十六进制）

| 文件 | 字节 | SHA-256 |
| --- | --- | --- |
| `.cache/p3-2-realdevice/feed_before.bin` | 60 | `5DCC1B5872DD9FF1C234501F1FEFDA01F664164E1583C3E1BB3DBEA47588AB31` |
| `.cache/p3-2-realdevice/info_frame.bin` | 60 | `E582BD26F7C5CA9276D4B4395500C32D02D23DC9AE1054BD230D7987DB567F8B` |
| `.cache/p3-2-realdevice/sess_full.bin` | 568 | `0579B7EA779A7EDC0040C6ED966BD815A27FEE55B57F3A6C1214099507D0E1DA` |
| `.cache/p3-2-realdevice/identity.bin` | 60 | `FFDE650422B8EEE0B8E7B3EB619C7DDABFB97C48B04462282F32FAE2955DE0C5` |
| `.cache/p3-2-realdevice/r10_env_before.bin` | 64 | `6E381DDAB015CC9E587211D0E08E760561AC1C79436DC02A3D927F9CC3E118CA` |
| `.cache/p3-2-realdevice/r10_capture.gdb` | 2154 | `C61973DB0A35BB499B57D2B89627CE1455ADD1D560A58D93A6529AFF710BB4D2` |
| `.cache/p3-2-realdevice/gdb_session.log` | 400 | `A7360F7A5AFF9A7B9A3A0297A236FE81A6E1F100C6F5B24C682CE2F73985A92D` |
| `.cache/p3-2-realdevice/p3_2_r10_capture.py`（实现方） | 8872 | `AD94DFE19DB3350DD9DCF17BF6A37D475EFB4AD242D7A4C7A95B972EB496D0CC` |
| `.cache/p3_2_verify_r10.py`（验收方） | 7669 | `7B6670B7990EF51D7B97227A14EEFF92DD1769C34E2CD39A2AE275765149CD9B` |

第 1 轮的 R3/R4 原始 dump 已备份到
`.cache/p3-2-realdevice/pre-r10/`；包内
`docs/acceptance-contracts/P3-2-v1/artifacts/realdevice/` 的冻结副本未被触碰。

## 8. 为什么不升 P3-2-v2

- R10 在冻结合同里属 `scope.excluded_by_freeze`，**不是任何判据的门槛**，
  它的结果无论正负都不改变第 1 轮 12 条判据的 `PASS`。
- 升 v2 会强制两条路之一：要么整轮重跑 12 条判据，要么走 `REUSED` 复用
  （需要 `--previous-contract` / `--previous-matrix` / `--previous-repo-root`
  与 `rerun-plan.json` 绑定链）。为一条不入门槛的加强项付这个代价，收益为零。
- 所以按「冻结后加强证据」记录：合同与矩阵保持原样不做追溯编辑，本文件与
  第 1 轮报告 §5 的状态更新构成完整链条。

如果后续 P3-3/P3-4 需要把 seq 回显纳入门槛，应在**那些卡自己的合同**里立判据，
而不是回头改 P3-2 的冻结件。

## 9. 交叉引用

- 第 1 轮验收报告：`docs/ota-exec-notes/P3-2-acceptance-round1.md`
- 实现方证据（含 R3/R4 崩溃根因与 R10 方案）：
  `docs/ota-exec-notes/P3-2-implementation-evidence.md` §7.5
- 冻结合同：`docs/acceptance-contracts/P3-2-v1.contract.json`
- 冻结证据矩阵：`docs/acceptance-contracts/P3-2-v1/P3-2-v1.evidence-matrix.json`
