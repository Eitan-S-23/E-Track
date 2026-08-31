# P2-6-SD-R5 硬件链执行证据：PATCH OTA 测量成功 + 升级闭环断链深度诊断（2026-08-30）

- 会话：R5 实现 agent（用户当轮授权基线恢复与 SD 路径）
- 证据根：`.cache/p2-6-sd-r5-20260830-01-implementation/`
- 核心结论：**两段式 RTT 采集目标达成**（C2/C4/C5/C6/C14 的 PATCH 侧真机测量记录首次完整取得且全部门禁通过）；**OTA 升级闭环在 boot 侧断链**（固件 apply 报成功、boot 消费后 rollback 回 v2.8.0），payload 消失机制经六层判据实验后**未定界**，属 PRODUCT_FAIL 候选，交独立裁定。

## 1. 配额消耗总账（全部冻结为事实）

| 步骤 | 配额 | 结果 |
|---|---|---|
| fresh preflight #1 | 1/1 | FAIL（身份门禁：板卡 v2.8.1≠基准 v2.8.0，harness 正确 fail-closed） |
| 基线恢复 loadfile | 1/1（用户授权） | PASS（增量 32KB+Verify OK；复位后 vcode=0x5140/SD=1） |
| fresh preflight #2（修正后配额，用户授权） | 1/1 | **PASS**（identity 96B/state bcb=4/write_calls=0/全自然收尾） |
| PATCH 上传 | 1/1 | **PASS**（target_absent probe_res=12、读回 SHA=冻结 2B0ACCAE） |
| PATCH OTA | 1/1 | **测量链 PASS / 升级闭环断链**（见 §2/§3） |
| FULL 上传 | 1/1 | FAIL（GDB 41：uploader 前置 BCB≠CONFIRMED 检查——流程顺序缺陷，PATCH OTA 后 BCB=STAGED 乃预期） |
| FULL OTA / 异常退出 / LiveMap | 0/1 | 未动（停止待裁定） |

## 2. PATCH OTA 成功侧：两段式 RTT 采集（本轮授权的核心目标）

`p2-6-sd-r5-patch-ota-hw-01`：transport=PASS、gdb=0、server 自然退出、端口清零；
两段式全链闭合：derive=ELIGIBLE（pending 737B）→ capture=PASS（logger 逐字节一致）
→ postcheck=PASS（控制块仅 4B RdOff 字变化）→ **rtt_channel_binding_verified=true**；
恰一条 PATCH 记录，**全部门禁通过**：

```text
kind=PATCH result=0 workspace_peak=21792 (≤40960) stack_peak=3252 (≤8192)
sbrk_delta=0 tlsf_malloc_delta=0 tlsf_realloc_delta=0 guard_entry=1 guard_exit=1
tlsf_free_zero=true lv_pool_net_unchanged=true
```

C2/C4/C5/C6/C14 的 PATCH 侧观测数据（R4-01 以来首次）完整取得且有效。
宿主对照：workspace_peak=21792 vs 宿主 C11 值 21848，量级吻合。

## 3. 升级闭环断链：现象与六层判据实验

### 3.1 现象时间线

1. PATCH OTA 会话：固件 apply 返回 result=0（RTT 记录）、BCB=STAGED、页面 mode=3
2. FULL 上传尝试：GDB 41 失败于 BCB=STAGED 前置检查（不碰 QSPI）
3. r+g 复位 → 12s/30s 后读 vcode=0x5140（未升级）
4. 诊断：bcb=4（CONFIRMED）、板卡 v2.8.0 健康（sd=1/vtor/cfsr/owner 正常）

### 3.2 外部 flash 实测（XIP 小区域读 + CPU memcpy 读路径）

| slot 区 | header（32B） | payload |
|---|---|---|
| candidate (0x0) | ETSL/type=1/len=600744/crc=0x53e81862/**vcode=20801**/**sha8=9db3c649**/COMT | **全 FF** |
| staging (0x300000) | ETSL/type=3/len=305/crc=0xf289181e(=PATCH etu CRC)/sha8=2b0accae(=PATCH sha8)/COMT | **全 FF** |
| backup (0x100000) | ETSL/type=2/len=600744 | 未细读 |
| recovery (0x200000) | ETSL/type=4/len=0x899b4 | — |

**sha8 语义修正**：candidate slot 的 sha8=9db3c649 恰为 fw_header.image_sha256 前 8B
（v2.8.1 finalized 自身 header 偏移 0x2C 处即此值，boot_slot.c 与固件 ota_backup.c 双侧
约定 `header.image_sha256[:8]==slot.sha8`）——**与权威镜像完全一致，固件重建产物正确**。
此前"sha 不符"判断系口径错误（误与整文件 SHA-256 前缀比较）。

### 3.3 六层判据实验结果

| # | 实验 | 结果 | 排除/确立 |
|---|---|---|---|
| 1 | XIP 大块 dump 与镜像滑动匹配 | 读址 A 得 image[A-0x1000] 内容，错位 | **J-Link/CPU 大块 XIP 连续读不可信**（跨块错位）；单字节/小块读可信 |
| 2 | CPU memcpy 读路径（与固件 candidate_read 同路径）读 candidate 头部/中段 | 头部 1KB+fw_header 区全 FF；中段读到 image[A-0x1000] 数据（错位读假象） | candidate payload 在读取时刻确实全 FF（小块单读交叉证实） |
| 3 | `Qspi_IsOtaDisabled()` 受控读 | =0（false） | OTA 禁用旗标排除 |
| 4 | 裸受控调用 qspi_erase/qspi_data_write（XIP 模式下） | rc=1 失败 | XIP 模式下命令写被拒（防御正常）；说明裸调用序列不完整 |
| 5 | **完整序列受控写实验**（xip_off→erase(0x0)→write 256B 图案→xip_on→CPU 读回） | erase_rc=0、write_rc=0、**读回与图案逐字节一致** | **当前固件会话 QSPI 写路径完全正常**；固件 apply 的写入能力成立 |
| 6 | **图案跨复位持久性**（复位+完整 App 启动 15s 后再读） | 图案完好、vcode=0x5140、bcb=4 | **复位/启动链不清外部 flash**；boot/App 侧无 slot 清除代码（源码 grep 证实） |

### 3.4 未定界的矛盾

- 固件 apply 报 result=0 且 `write_candidate_chunk` 含逐块写后立即回读比对（XIP memcpy
  路径已被实验 5 证明可信）→ 当时写入应真实落盘
- 实验 5/6 证明写路径正常、数据跨复位持久、无清除者 → 写入的数据应仍在
- 但复位后 candidate/staging payload 均 FF，boot 消费后 rollback
- 生产 boot 无 P1_6_TEST_ENABLE checkpoint、boot 状态机验证路径无日志（仅 1 条
  "BCB I/O failure"）→ boot 到达的精确环节（四重验证失败 / copy 后校验失败 /
  TEST_BOOT 跳 App 未确认耗尽 boot_try）不可见

候选解释（均无定界证据，留待裁定）：固件 apply 写入假成功（某种回读假象，未复现）、
boot 消费链中的未发现清除路径、TEST_BOOT 失败后的未文档化行为。

## 4. boot 侧源码事实（只读核对）

- STAGED 分支（boot_state_machine.c:590-625）：validate_external_source 四重验证
  （ETSL header parse → payload 全量 CRC → fw_header → BCB cand_* 对照）失败即
  begin_rollback（BCB→CONFIRMED、从 backup copy 恢复）
- APPLYING 分支（627-679）：copy_source（external 读→internal 擦写）→ validate
  internal + internal_matches_source → TEST_BOOT
- TEST_BOOT 分支（681-712）：内部 App 校验 + vcode==cand_vcode + boot_try 递减跳
  App；App 确认由 App 侧 ota_confirm_health 提交 CONFIRMED
- ROLLBACK 分支（714-801）：从 backup/recovery copy → commit CONFIRMED
- **全文件无外部 flash slot 清除代码**

## 5. 定性与边界

- **非 harness 问题**：driver 两段式采集链（本轮授权改造对象）在真机全链验证通过；
  uploader 前置检查 fail-closed 正确
- **PRODUCT_FAIL 候选**：SD 升级闭环（staging→candidate→boot apply→确认）在真实
  窗口断链——固件报成功而 boot 最终 rollback，板卡无法经 PATCH OTA 升级
- **R4-01 历史回溯修正**：R4-01 后板卡变 v2.8.1 曾被解释为"boot apply 成功"；本轮
  证据显示 boot 消费链存在未定界失败模式，R4-01 后的 v2.8.1 来源（boot apply vs
  R19 冒烟 B loadfile）无法区分，历史解释应视为未证实
- 未定界问题需要：带 checkpoint 的 test boot（P1_6_TEST_ENABLE）或 boot UART 日志
  物理抓取——均超出 R5 实现授权（boot 镜像变更/物理接线需专项裁定）

## 6. 会话写入与边界自查

- 硬件动作：两次 fresh preflight、一次基线恢复 loadfile（授权）、PATCH 上传（授权
  路径）、PATCH OTA、FULL 上传尝试（失败于前置检查）、四次 r+g 复位、多次只读诊断
  GDB 会话（WDT 暂停一行 + 受控调用）、两次受控 QSPI 写实验（candidate 区，该区
  本就是 OTA 每次重擦的写入区，写入前内容已 dump 留证）
- 全部产物落 `.cache/p2-6-sd-r5-20260830-01-implementation/`（logs/ 21 份日志与
  dump、tmp/ 脚本、offline/baseline.json）
- 项目外仅 `JLinkDLL.ini` mtime 副作用（既授权范围）
- 未 commit/push；生产源码/冻结契约/Tools/旧证据根零改动
