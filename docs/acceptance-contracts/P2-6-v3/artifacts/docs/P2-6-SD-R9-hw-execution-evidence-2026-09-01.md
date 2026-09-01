# P2-6-SD-R9 硬件链执行证据：C7 补测（20802 制包 + Apply 中途失败注入）（2026-09-01）

- 会话：R9 实现 agent（授权来源：本轮派工书【P2-6-SD-R9 派工书：C7 补测（20802 制包
  + Apply 中途失败注入）】，原文落盘 `.cache/_r9.txt`）
- 证据根：`.cache/p2-6-sd-r9-20260901-01-implementation/`（启动前写入预检确认原不存在，
  路径链无 reparse point，位于项目根内；未改动 R5/R7/R8 证据根）
- 动作序列：S0 预检 → S1 离线制包（GOOD/BAD v2.8.2）+ 宿主闸门 → S1B BAD 硬件上传
  （含 USB MSC 释放插曲）→ S2 LiveMap 基线 32s → S3 C7 链（**产品行为观测 1/1**）
  → S3B/S3E 失败后稳态与失败码 → S4 Pop 恢复 32s → S5 终态
- 本文档只报事实，不写"验收通过"；验收由非实现会话执行。
- 产品行为观测严格 1/1：S3 链只发起一次升级；S3B/S3E/S4/S5 均为只读观测或页面导航，
  不发起第二次升级。

## 0. 执行环境

| 项 | 值 |
|---|---|
| 冻结测试 ELF | `.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.elf`，SHA-256 `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`（与 R5/R7/R8 一致，未重建） |
| 板卡起始基线 | test v2.8.1（fw_header vcode=20801，image_len=600744），BCB=CONFIRMED(4)，LiveMap 前台 owner=1 |
| 设备镜像（上传闸门用） | `.cache/p2-6-sd-ota/assets/X-Track-App-GCC-p2-6a-test-v2.8.1.finalized.bin`，SHA-256 `A2D3083B25EE32813EFF6CC1BD0CF77CE235FD03BF79947C08B8A3C815D58E00` |
| BAD 包 | `tmp/BAD-2.8.2.etu`，282355 B，SHA-256 `EA7C5CA22E572BFB2D211E21C9475091D9F68725F862939B71FA874E5FA24C30`，target_vcode=20802 |
| GOOD 包（未上传） | `tmp/GOOD-2.8.2.etu`，282355 B，SHA-256 `761A71C00631FB12ACC3C30C7A387FDFACF2D5DC298501CE96E9CE63A1A19E20`，target_vcode=20802 |
| 关键符号（本轮 nm 重取，`tmp/r9-nm-full.txt`） | `HAL::HAL_Update()`=0x08040884、`HAL::OTA_GetBcbState()`=0x08040CCC（thumb+1）、`LzmaDec_Allocate` 入口=0x0804b568、`FirmwareUpdate::FinishImport` 入口=0x08045074、`FirmwareUpdate::SelectRow`=0x08045710（thumb+1）、`FirmwareUpdate::StartImport`=0x080457a8（thumb+1）、`FirmwareUpdate::EnterPath`=0x08045618（thumb+1）、`PageManager::Push`=0x0803db94（thumb+1）、`usbd_disconnect`=0x08018e76（thumb+1）、`usbd_connect_state_get`=0x0804238c（thumb+1）、`_SEGGER_RTT`=0x20053E1C、`SD_IsReady`=0x20053214、`g_ota_overlay_owner`=0x20053FA0、`g_ota_overlay_workspace`=0x20058000、USB conn_state 字节=0x20053970（反汇编推导，见 §3.2） |
| 页面 vptr（身份判定） | LiveMap=0x0805d818、FirmwareUpdate=0x0809cb44、Dialplate=0x0805d7ac、MainMenu=0x0805d878 |
| J-Link | 板载 J-Link，`C:\Users\SU\SEGGER\JLink_V818`，SWD 1000 kHz，烧录/连接设备全名 `AT32F435RGT7`，RTT logger 设备 `CORTEX-M4` |

每个硬件会话沿用受控停点模式：`monitor halt` → `monitor WriteU32 0xE0042008
0x00001000`（WDT 暂停，每次 halt 后立即写）→ thbreak `HAL::HAL_Update()` 确定性停点
→ 受控调用后校验 `$pc`。固件身份用 96 B fw_header 期望字序列校验
（`tmp/v281-fw-header-gdb-block.txt`，含 `0x00005141`=20801）。

## 1. S0：上传前置预检 —— PASS

脚本 `tmp/r9-s0-precheck.gdb`，日志 `logs/r9-s0-precheck-gdb.log`：

```
P2_6_R9_S0 state vcode=20801(0x00005141) bcb=4 owner=1 sd=1 vtor=0x08010000 cfsr=0x00000000
P2_6_R9_S0 current_page ptr=0x20032ae0 vptr=0x0805d818 (LiveMap)
P2_6_R9_S0 livemap_current popping_to_release owner=1
P2_6_R9_S0 pop_ok=1
P2_6_R9_S0 release_wait turns=10 owner=0
P2_6_R9_S0 final vcode=20801 bcb=4 owner=0 sd=1
P2_6_R9_S0 PASS upload_preconditions_ok
```

LiveMap 弹出后 overlay 释放（owner 1→0，10 轮 HAL_Update 等待），SD 就绪，BCB=4，
身份 96 B 头校验 PASS（vcode=20801）。上传前置满足。

## 2. S1：离线制包与宿主闸门 —— PASS

### 2.1 制包方法（`tmp/derive_bad.py`）

以 R8 冻结资产 `P2-6A-FULL-v2.8.1.etu` 的制作流程为模板，用 v2.8.1 源镜像
`tmp/app-src-2.8.1.bin`（600744 B，即设备现运行镜像）重新制包：

- **GOOD-2.8.2.etu**：vcode 改 20802，AES-128-CTR + LZMA-Alone 全链重打包，外层
  双 CRC（off36 payload_crc32 / off60 header_crc32）按新内容重算。
- **BAD-2.8.2.etu**：在 GOOD 基础上翻转 payload 中段 1 字节（偏移 **141209**），
  再**重算双 CRC**。这是派工书指出的决定性陷阱的解法：`ota_package.c` 中
  `validate_payload_crc()`(:667) 在 `workspace_acquire()`(:672) 之前，只翻字节不改
  CRC 会在 acquire 前返回 PAYLOAD_CRC 错误、进不到 Apply 窗口；双 CRC 修复后失败点
  被推到 acquire 之后的 LZMA 解码，从而实现"Apply 中途失败"。

### 2.2 宿主闸门（`tmp/test_r9_gate.c`，PC 侧复用仓库 ota_package 源）

日志 `logs/r9-s1-host-gate.log`，全部检查 PASS（failures=0 status=PASS）：

```
P2_6_R9_GATE kind=good result=ok package_len=282355 payload_len=282291 target_vcode=20802
              workspace_peak=33072 prepares=1 programs=619 acquires=1 releases=1
P2_6_R9_GATE kind=bad result=lzma_data workspace_peak=0 arena_peak_observed=33072
              prepares=1 programs=228 acquires=1 releases=1 workspace_zeroed=1
  good: result ok / target 20802 / workspace_peak>0 / candidate==源镜像 / acquire-release 成对 / BCB 逐字节不变
  bad : result 是失败 / 不是 payload_crc / 外层 CRC 过(acquire=1) / workspace 恰好释放一次 /
        workspace 清零 / arena 已初始化 / 失败发生在 candidate_prepare 之后 / BCB 不动
```

宿主侧证明：BAD 包外层 CRC 通过、`workspace_acquire` 恰好执行 1 次（即失败点在
acquire 之后）、失败码 `lzma_data`（-20）、cleanup 释放并清零 workspace、BCB 不动。
GOOD 包 result=ok（对照完整成功路径），**未上传设备**（派工书红线）。

## 3. S1B：BAD 硬件上传 —— PASS（第 2 次尝试，第 1 次为环境类失败）

### 3.1 第 1 次上传失败（产品前失败，按派工书条款当场修复重试）

命令 wrapper `tmp/run_r9_upload.py`（调用仓库冻结 uploader
`tests/ota/p2_6_rtt_sd_uploader.py`）。第 1 次目标路径
`/P2-6A-FULL-v2.8.2-BAD-R9-20260901-01.etu`：

```
P2_6_SD_UPLOAD target_absent probe_res=12
P2_6_SD_UPLOAD write chunk=0 res=2 bytes=0
P2_6_SD_UPLOAD ERROR write_failed close=0
```

日志 `logs/p2-6-sd-r9-bad-upload-hw-01-gdb.log`（exit 47）。根因不是卡满
（E: 盘剩 28.6GB）：当时 Windows 正经 USB MSC 挂载设备 SD（E:），设备侧
「SDIO 被 USB MSC 独占」（`PM_Router.cpp:38` 注释与 `IsLiveMapBlockedByUsbMsc` gate），
设备侧 SdFat 首簇分配 I/O 失败（lv_port_fs_sdfat `fs_write` 返回 FS_ERR=2，
FatFile::write addCluster 路径）。**属产品前失败（上传失败），按派工书
「可当场修并在同一 session 重试」条款处理，不消耗产品行为 1/1 限额。**
SD 卡上遗留 0 字节半成品 `-01.etu`（设备侧 `FatFile::remove` 未被链接，无法删除；
uploader 拒绝覆盖既有目标，故重试改用新路径 `-02`）。

### 3.2 USB MSC 释放链（三次 GDB 会话）

**第 1 步** `tmp/r9-s1-usb-release.gdb`（日志 `logs/r9-s1-usb-release-gdb.log`）：
受控调用 `usbd_disconnect(&otg_core_struct.dev)`（0x08018e77）。反汇编确认该函数只置
OTG+0x804 的 D+ 软断连位；宿主立即失去 E: 盘，但——

```
P2_6_R9_USB plugged_before=1
P2_6_R9_USB usbd_disconnect_done
P2_6_R9_USB plugged_after=1 (应=0: MSC 已释放)
```

`USB_IsPlugged`（HAL_USB.cpp:21，`usbd_connect_state_get()==CONFIGURED`）仍返回 1。
**第 2 步** verify 会话确认软断连后状态依旧（`plugged_now=1`）。

**根因**：`usbd_suspend_handler`（usbd_int.c:487）应把枚举状态置 SUSPENDED(4)，但软
断连后该 USB IRQ 从不触发，`conn_state` 陈旧停在 CONFIGURED(3)。
`usbd_connect_state_get` 反汇编为 `ldrb r0,[r0,#740]`，即 conn_state 单字节位于
`&otg_core_struct.dev + 0x2E4` = **0x20053970**（otg_core_struct 布局见
usb_core.h:85-102，`&dev`=0x2005368c；枚举值 DEFAULT=1/ADDRESSED=2/CONFIGURED=3/
SUSPENDED=4 见 usb_std.h:128-138）。

**第 3 步** `tmp/r9-s1-usb-fix.gdb`（日志 `logs/r9-s1-usb-fix-gdb.log`）：

```
P2_6_R9_USBF before conn_state=3 plugged=1 (软断连已生效宿主已脱离, 但 suspend IRQ 未触发)
P2_6_R9_USBF conn_state_fix old=3 conn=4(SUSPENDED)
P2_6_R9_USBF plugged_after=0 (应=0: MSC gate 打开)
P2_6_R9_USBF state sd=1 owner=0 bcb=4
P2_6_R9_USBF PASS usb_gate_cleared plugged=0 sd=1 owner=0 bcb=4
```

GDB 直写 0x20053970=4（SUSPENDED），**复刻 suspend handler 本应产生的状态**。此补写
只涉及 USB 枚举状态单字节（非 QSPI、非 BCB、非 overlay、非 flash），已按红线要求
在此登记；软断连本身（usbd_disconnect）是产品提供的正常 API。

### 3.3 第 2 次上传 —— PASS

目标路径 `/P2-6A-FULL-v2.8.2-BAD-R9-20260901-02.etu`，日志
`logs/p2-6-sd-r9-bad-upload-hw-02-gdb.log`，结果
`logs/p2-6-sd-r9-bad-upload-hw-02-result.json`：

| 判据 | 实测 |
|---|---|
| MCU 落盘路径 | `/P2-6A-FULL-v2.8.2-BAD-R9-20260901-02.etu` |
| 分块 | 9 块（8×32768 + 20211）全部 res=0 |
| 读回校验 | readback 282355 B，SHA-256 `EA7C5CA2…4C30` 与输入逐字节一致（`readback_matches`） |
| 上传期间状态 | sd=1 vtor=0x08010000 cfsr=0 bcb=4 owner=0 |
| 上传后 | BCB=4，owner=0，vcode=20801（未动） |

### 3.4 上传 wrapper 的双门禁等效替代（如实登记）

仓库 uploader/driver 为冻结测试基建，本轮**零改动**（`git status` 无
tests/ota 变更）。wrapper（`tmp/run_r9_upload.py`）在运行时 monkey-patch 两道冻结
门禁，保持 fail-closed：

1. `uploader.FROZEN_ASSETS[BAD_SHA256] = "FULL"`——dict 注入本轮新制 BAD 包的
   SHA-256（该门禁的本义是"只传冻结资产清单内的包"，本轮 BAD 包是派工书授权专门
   制作的新资产，故按其真实哈希登记；未知输入仍被拒绝）；
2. `driver.FROZEN_V280_IMAGE_SHA256 = <v2.8.1 finalized bin 哈希>`——设备镜像校验
   常量按板卡**现运行** v2.8.1 冻结资产登记（板卡自 R8 FULL 升级后运行 v2.8.1，
   传入的 device-image 即 v2.8.1 finalized bin；`load_frozen_device_header` 的校验
   逻辑零改动，仅换冻结哈希为真实值）。

两道门禁的校验逻辑、比较方向、失败行为均未改动。

## 4. S2：LiveMap 基线（32 s RTT）—— PASS

脚本 `tmp/r9-s2-baseline.gdb`：复位（`r`+`g` 经 GDB server 脚本）→ RTT 命令
`gpsreset`（经 RTT down channel 发送，实测 curLon=104.883930 curLat=26.568540，防止
随机游走出瓦片区）→ `Push("Pages/LiveMap")` → 32 s RTT logger 采集。

日志 `logs/r9-s2-baseline-gdb.log` + `logs/r9-s2-baseline.rtt.log`：

```
P2_6_R9_S2 state vcode=20801 bcb=4 owner=0 sd=1
P2_6_R9_S2 gps_before curLon=104.841022 curLat=26.535982
P2_6_R9_S2 gps_reset_done curLon=104.883930 curLat=26.568540
P2_6_R9_S2 push_try1=1
P2_6_R9_S2 livemap_owner=1 (应=1: LiveMap 持有)
P2_6_R9_S2 livemap_page_state=3
P2_6_R9_S2 bcb_after=4 (应=4)
P2_6_R9_S2 PASS baseline_ready owner=1
```

**基线统计（40 行 `LiveMap stat:`）**：update 39–47、lineHit 8–608、lineMiss 0–44、
lineReadKB 合计 1584、refrMs 158–250。地图瓦片正常命中（lineHit>0、sdMs 低频），
作为 C7 "地图正常"的对照基线。

## 5. S3：C7 链 —— 产品行为观测 1/1（发起被接受，中途失败）

脚本 `tmp/r9-s3-c7-chain.gdb`，日志 `logs/r9-s3-c7-chain-gdb.log`。链路：
Push FirmwareUpdate（LiveMap 释放）→ EnterPath("/") → 行扫描选中 BAD →
SelectRow（Inspect，产品行为从此计入 1/1）→ StartImport → LzmaDec_Allocate 停点
（Apply 窗口内）→ FinishImport 停点 → 结果页。

实测标记（按时间序）：

```
P2_6_R9_S3 pre vcode=20801 bcb=4 owner=1 sd=1        ← LiveMap 前台基线态
P2_6_R9_S3 push_try1=1                                 ← Push FirmwareUpdate 成功(首轮, 无需 USB 重试)
P2_6_R9_S3 livemap_release_wait turns=1 owner=0        ← 切页后 LiveMap 释放 overlay
P2_6_R9_S3 page_ready state=4                          ← FirmwareUpdate 页就绪
P2_6_R9_S3 bcb_mid1=4
P2_6_R9_S3 enter_path_done
P2_6_R9_S3 row_index=12                                ← BAD 包在 24 行列表中定位
P2_6_R9_S3 confirm mode=1                              ← ★发起被接受(CONFIRM), 不是"发起被拒"
P2_6_R9_S3 owner_at_confirm=0
P2_6_R9_S3 bcb_mid2=4
P2_6_R9_S3 import_started mode=2                       ← StartImport 进入 WORKING
P2_6_R9_S3 lzma_alloc_entry pc=0x0804b568              ← LzmaDec_Allocate 入口停点(acquire 后, 解码前)
P2_6_R9_S3 DECISIVE owner_at_apply=2                   ← ★Apply 窗口内 overlay 归包(R8 唯一缺失格)
P2_6_R9_S3 lzma_ctx vcode=20801 mode=2
P2_6_R9_S3 ERROR context_lost_bcb_3 pc=0x0804b568      ← harness 缺陷(见 §5.1), 非产品行为
```

### 5.1 S2-3 harness 缺陷（如实登记）

LzmaDec 停点采到 `owner_at_apply=2` 后，脚本对「BCB 中检 3」的受控调用
`OTA_GetBcbState()` 返回后做 PC 上下文检查时，**误用了 HAL_Update 地址
0x08040884**，而当前上下文仍在 LzmaDec 停点 0x0804b568 → 误判 context_lost →
quit 89 中止脚本（GDB detach，设备恢复全速执行）。丢失的采样：FinishImport 停点的
失败瞬间观测（owner_at_fail / mode 变迁时序）与中检 3。

裁决依据派工书：产品行为观测 1/1 已消耗且**决定性格（owner_at_apply=2）已落盘**，
不重跑升级链；丢失格用 S3B（失败后稳态只读观测）+ S3E（产品自身 lastError）补偿，
补偿结果与宿主闸门（S1 `result=lzma_data`、acquires=1 releases=1）三方一致。

### 5.2 失败后稳态（S3B，只读）

脚本 `tmp/r9-s3b-post-fail.gdb`，日志 `logs/r9-s3b-post-fail-gdb.log` +
`r9-s3b-post-fail-rtt-{cb,up0}.bin`：

```
P2_6_R9_S3B post_fail mode=3 (应=3 结果页) owner=0 (应=0 已释放) vcode=20801 (应=20801)
P2_6_R9_S3B bcb_post_fail=4 (应=4)
P2_6_R9_S3B RTT_CB pBuffer=0x20053a1c size=1024 wroff=700 rdoff=701
P2_6_R9_S3B PASS post_fail_steady mode=3 owner=0 vcode=20801 bcb=4
```

Apply 失败后：页面已进入 MODE_RESULT(3)（FinishImport(false) 走完）、
overlay 已释放（owner=0，cleanup 执行）、vcode=20801、BCB=4。

### 5.3 失败码（S3E，产品自身状态）

脚本 `tmp/r9-s3e-errstring.gdb`，把 FirmwareUpdate 页对象整块 dump
（`logs/r9-s3e-page-object.bin`，13824 B）离线检索
`Session::lastError`（页内偏移 0x13ac）：

```
0x12ac  /P2-6A-FULL-v2.8.2-BAD-R9-20260901-02.etu   ← 页对象当前选中包(BAD, 与上传路径一致)
0x13ac  full:lzma_data                               ← ★产品失败码: LZMA 数据错误(-20)
```

失败码为 `full:lzma_data`（解压数据校验失败），**不是 `OTA_SD_ERR_VERSION`**——
满足派工书第 4 步"失败返回预期是解压/镜像校验失败，不是 OTA_SD_ERR_VERSION"。
该证据来自产品自身页对象状态，与宿主闸门 `result=lzma_data` 一致。

### 5.4 RTT 测量行缺口（如实登记）

派工书第 4 步同时预期 RTT 测量行 `P2_6 kind=full result=<失败码>`。实测 RTT up0
控制块 flags=**0001（NO_BLOCK_TRIM）**：logger 停读后 rdoff 冻结，ring（1024 B）写满
后 wroff 钉死在 rdoff-1（S3B 实测 wroff=700 rdoff=701，环绕态），**此后固件所有
写入（含测量行）被 TRIM 丢弃**。从 S3B/S3 dump 的 ring 按环绕顺序重解，只有
LiveMap 统计行，无 `P2_6` 测量行——采集侧缺口（logger 未持续排空），非产品缺口。
失败码证据改道 §5.3 的产品 lastError（等效），并由 §2.2 宿主闸门
`kind=bad result=lzma_data` 旁证。

## 6. S4：Pop 恢复（LiveMap 重建 + 32 s RTT）—— PASS

脚本 `tmp/r9-s4-recover.gdb`，日志 `logs/r9-s4-recover-gdb.log` +
`logs/r9-s4-recover.rtt.log`：

```
P2_6_R9_S4 pre mode=3 owner=0 bcb=4 sd=1              ← 从失败结果页出发
P2_6_R9_S4 pop_ok=1                                    ← Pop() 取消(用户返回)
P2_6_R9_S4 reacquire_wait turns=0 owner=1              ← ★LiveMap 立即 reacquire(同步, 0 轮等待)
P2_6_R9_S4 livemap_state=3                             ← DID_APPEAR
P2_6_R9_S4 gps_reset_done curLon=104.883930 curLat=26.568540
P2_6_R9_S4 final vcode=20801 bcb=4 owner=1
P2_6_R9_S4 PASS recover_ready owner=1 livemap_front
```

Pop 返回后 LiveMap onViewLoad **同步**重新 acquire（turns=0，无需跨帧等待），
owner 0→1，页面回到前台。gpsreset 后 32 s RTT：

**恢复统计（44 行 `LiveMap stat:`）**：update 40–47、lineHit 2–313、lineMiss 0–24、
lineReadKB 合计 1952、refrMs 152–220——与基线（40 行、lineHit 8–608、lineReadKB
1584、refrMs 158–250）同档，瓦片命中与 SD 读正常，**地图正常显示**。

## 7. S5：终态 —— PASS

脚本 `tmp/r9-s5-final.gdb`，日志 `logs/r9-s5-final-gdb.log`：

```
P2_6_R9_S5 final vcode=20801 bcb=4 owner=1 sd=1 vtor=0x08010000 cfsr=0x00000000 page_vptr=0x0805d818
P2_6_R9_S5 PASS final_state_ok vcode=20801 bcb=4 owner=1 livemap_front
```

96 B fw_header 身份校验 PASS：vcode=20801（**升级失败后设备仍是 v2.8.1**）、
BCB=CONFIRMED(4)、LiveMap 前台持 overlay、无 fault、运行时正常。

## 8. 判据汇总

按派工书「■ 交付」要求的判据行格式：

```
P2-6-C7 | overlay 释放=t(owner 2→0) / LiveMap 重建=t(owner→1) / 地图正常=44行, lineHit 2-313(基线40行, 8-608) | .cache/p2-6-sd-r9-20260901-01-implementation/logs/r9-s3-c7-chain-gdb.log
```

| # | 判据 | 实测 | 来源 |
|---|---|---|---|
| 1 | 上传 BAD 读回 SHA 一致 | 282355 B，SHA-256 `EA7C5CA2…4C30` 逐字节一致 | `p2-6-sd-r9-bad-upload-hw-02-result.json` |
| 2 | 发起被接受（非发起被拒） | `confirm mode=1`（Inspect→CONFIRM） | `r9-s3-c7-chain-gdb.log` |
| 3 | **owner_at_apply==2**（Apply 窗口内 overlay 归包，R8 缺失格） | `DECISIVE owner_at_apply=2`（LzmaDec_Allocate 入口停点实测） | `r9-s3-c7-chain-gdb.log` |
| 4 | 失败码为解压/镜像校验失败，非 VERSION | 产品 lastError=`full:lzma_data`；宿主闸门 `result=lzma_data`（-20） | `r9-s3e-page-object.bin`（0x13ac）、`r9-s1-host-gate.log` |
| 5 | 失败后 owner 回 0 | `post_fail … owner=0`（稳态实测，cleanup 已释放） | `r9-s3b-post-fail-gdb.log` |
| 6 | 失败后进结果页 | `post_fail mode=3`（MODE_RESULT） | `r9-s3b-post-fail-gdb.log` |
| 7 | Pop 后 owner 回 1（LiveMap 重建） | `reacquire_wait turns=0 owner=1` | `r9-s4-recover-gdb.log` |
| 8 | 恢复统计与基线同档 | 恢复 44 行 lineHit 2–313 lineReadKB 1952 refrMs 152–220 vs 基线 40 行 lineHit 8–608 lineReadKB 1584 refrMs 158–250 | `r9-s4-recover.rtt.log` / `r9-s2-baseline.rtt.log` |
| 9 | 全程 BCB=CONFIRMED(4) | S0/S2 前/S2 后/S3 pre/mid1/mid2/apply 窗口（稳态复核）/S3B/S3E/S4/S5 **全 4** | 各对应日志 |
| 10 | 全程 vcode=20801 | S0/S2/S3 pre/S3 lzma_ctx/S3B/S3E/S4/S5 全 20801 | 各对应日志 |
| 11 | 出现 STAGED/APPLYING 即停 | 未出现（全部观测点 BCB=4） | 各对应日志 |
| 12 | 终态身份 | 96 B 头校验 PASS，vcode=20801 | `r9-s5-final-gdb.log` |
| 13 | GOOD 包不传 | `uploaded_to_device=false`（仅宿主闸门离线验证） | §2.2 |

**C7 三要素**：①overlay 所有权释放＝t（Apply 窗口 owner=2 → 失败后 owner=0）；
②LiveMap 重新初始化＝t（Pop 后 owner 同步回 1、DID_APPEAR、前台 vptr）；③地图正常
显示＝t（恢复 44 统计行，lineHit/lineReadKB/refrMs 与基线同档）。

## 9. 偏差与如实登记汇总

| # | 项 | 说明 |
|---|---|---|
| 1 | 上传 wrapper 双门禁 monkey-patch | 见 §3.4。冻结测试基建零改动；等效替代，仍 fail-closed，未知输入仍拒绝 |
| 2 | conn_state GDB 补写 | 见 §3.2。写 0x20053970=4（复刻 suspend handler 应产生的 USB 枚举状态）；非 QSPI、非 BCB、非 overlay、非 flash 写 |
| 3 | 第 1 次上传失败 + 路径变更 | 见 §3.1。MSC 独占导致产品前失败（exit 47，res=2），当场修复后重试；卡上遗留 0 字节 `-01.etu` 半成品（设备侧无法删除，FatFile::remove 未链接）；最终使用 `-02` 路径 |
| 4 | S2-3 harness PC 检查缺陷 | 见 §5.1。quit 89，丢失 FinishImport 停点瞬间采样；以 S3B 稳态 + S3E lastError 补偿，与宿主闸门三方一致 |
| 5 | RTT 测量行被 TRIM 丢弃 | 见 §5.4。up0 flags=TRIM，ring 写满后测量行被丢；失败码改由产品 lastError（`full:lzma_data`）等效证明 |
| 6 | 本轮未观测到 boot 侧行为 | 派工书范围仅 App 侧 C7（BCB 全程 4，无复位）；未烧录、未复位进 boot |
| 7 | 证据根未含独立 rerun-plan | 本轮为补充性硬件证据（非合同验收轮），产物矩阵见 §10 与 `result.json` |

## 10. 产物清单

证据根 `.cache/p2-6-sd-r9-20260901-01-implementation/`：

- `result.json` —— 39 个决定性产物逐文件 SHA-256/字节数 + 判据摘要（本轮生成，
  生成器 `tmp/build_result_json.py`）
- `logs/`（46 文件）—— 上表全部日志 + 上传分块/RTT raw/J-Link server 日志 +
  RTT cb/ring 二进制 dump + 页对象 dump
- `tmp/`（27 文件）—— GOOD/BAD etu、derive_bad.py、test_r9_gate.c（宿主闸门源）、
  r9-nm-full.txt（符号重取）、v281-fw-header-gdb-block.txt（身份期望字序列）、
  10 个 .gdb 脚本、run_r9_{session,logger,upload}.py、上传分块目录、
  kanban_claim_r9.py、extract_v281_header.py、build_result_json.py

关键哈希（另见 `result.json`）：

| 产物 | SHA-256 |
|---|---|
| BAD-2.8.2.etu | `EA7C5CA22E572BFB2D211E21C9475091D9F68725F862939B71FA874E5FA24C30` |
| GOOD-2.8.2.etu | `761A71C00631FB12ACC3C30C7A387FDFACF2D5DC298501CE96E9CE63A1A19E20` |
| 冻结测试 ELF | `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019` |
| 设备镜像（v2.8.1 finalized） | `A2D3083B25EE32813EFF6CC1BD0CF77CE235FD03BF79947C08B8A3C815D58E00` |

本轮零生产源码改动、零契约改动、零 R5/R7/R8 证据根改动（`git status` 仅
PLAN-OTA-EXEC.md 与本轮新文件）。
