# P3-2 独立验收报告（第 1 轮）

日期：2026-09-03 ｜ 执行者：独立验收会话（非实现方）
被验收卡：P3-2「GET_INFO 设备身份链」
冻结合同：`docs/acceptance-contracts/P3-2-v1.contract.json`
证据矩阵：`docs/acceptance-contracts/P3-2-v1/P3-2-v1.evidence-matrix.json`

**单轮结论：PASS**（附 2 项非阻断发现、1 项已授权偏差、1 项环境阻塞的范围外补证）

## 0. 验收方资格与独立性

本会话创建了 P3-7 任务卡并冻结派发了 P3-2 派工书，**未参与 P3-2 实现**，
满足 `AGENTS.md` §0 规则 4「验收命令由非实现会话执行，实现者不自验收」。

独立性做法：本轮不复用实现方任何解码脚本或断言集，按冻结契约条文重写核验器
（`tests/ota/p3_2_verify_*.py` 四个，共 116 项断言）；实现方证据笔记仅作为
**待核对的声明**冻结进 `external/`，不作为判据来源。

## 1. 判据与结论一览

| 判据 | 结论 | 决定性观测 |
|---|---|---|
| C01 帧线格式（§5.1） | PASS | 60B = 8+50+2；`A5 5A`；cmd=0x80；session=0；CRC16-CCITT-FALSE 覆盖 cmd..payload 重算 == 上线值 |
| C02 INFO payload 字段（§5.2.1） | PASS | model=`E-Track\0`（偏移 0 长 8 ASCIIZ）、proto_ver=1、max_window_segs=32、cur_vcode≠0、摘要非全零 |
| C03 字段可追溯 fw_header | PASS | hw_rev/layout_id/cur_vcode 与 fw_header 实值逐项相等；boot_ver ≥ min_boot_ver |
| C04 摘要域分离（OTA-XC-IMAGE-IDENTITY） | PASS | 双零法重算 == 头内摘要；raw 域 ≠ 双零域；INFO 摘要 == raw 域 32B 全等且 ≠ 双零域 |
| C05 三方镜像闭合 | PASS | 源码构建 bin → finalize 复算 → 板上 dump 三者 SHA-256 同为 `4512de08…1b4b` |
| C06 快照与会话结构一致 | PASS | 快照 valid=1、model/vcode/摘要与 INFO 同源；INFO 帧位于会话结构偏移 421 |
| C07 host 测试全绿且具鉴别力 | PASS | `checks=114 failures=0`；三处红线注错各把 harness 打红（非编译错误），还原后复绿 |
| C08 harness fail-closed 静态属性 | PASS | 退出码绑定 failures；`-Werror`/`/WX`；链接真实产品源；无 fail-open 模式 |
| C09 生产构建绿且逐字节可复现 | PASS | 全量 clean 重建 exit 0；App bin `7328c1b1…`、Boot bin `5842ff3e…` 与实现方声明逐字节一致 |
| C10 生产符号落位、路径只读 | PASS | 身份链在 text(0x08048868 段属性 T)、快照在 BSS(0x2005…)、无测试符号泄漏 |
| C11 范围与红线 | PASS | 卡内 9 项改动；12 类红线路径与 HEAD 完全一致；CI 无 fail-open |
| C12 治理门禁 | PASS | `tests/ota/test_acceptance_bundle.py` 全绿 |

核验器汇总：realdevice 41 + harness 38 + scope 23 + build 14 = **116 项断言，0 失败**。

## 2. 决定性证据（原始观测值）

### 2.1 摘要域分离——本卡最核心的契约风险点

冻结裁决 `OTA-XC-IMAGE-IDENTITY` / `OTA-DEC-002` 要求：跨系统镜像身份 = 最终
`app.bin` 全部 `image_len` 字节的 **raw SHA-256**；`fw_header.image_sha256` 的
双零法属 header 完整性域，**不得进入** `INFO.image_sha256`。

本轮独立重算（`tests/ota/p3_2_verify_realdevice.py` D 段）：

```
raw_identity_sha256      = 4512de0878c146a93b55f65aa86acab4eedcf7f7082ead97ad73c24884671b4b
header_double_zero_sha256= d97534841302c16d4e026820a6b854c8ee68cc256b0042024d1280001f7401dd
```

两域确实互异；`INFO.image_sha256` 32 字节全等于 raw 域、且不等于双零域。
即混域这条最容易过审的错误在真机层面被排除，而非仅靠代码阅读。

交叉佐证（`p3_2_verify_harness.py` D 段，读冻结向量而非设备）：
`tests/ota-vectors/expected.json` 中 `toy-patch.etu` 的 `base_sha8`
= `3081fa0afc5bb2f3` = `toy-old.bin` 的 `file_sha256` 前 8B（raw 域），
与同一 fixture 的 `fw_header.image_sha256`（`e025e068…`）不同。**冻结向量本身
就把两域区分开了**，P3-2 的取值与向量一致。

### 2.2 三方镜像闭合——摘要绑定到本仓库源码

真机段只能证明「板上镜像 == INFO 摘要」（两方）。本轮补上第三条腿
（`tests/ota/p3_2_verify_build.py`）：用当前仓库源码全量重建的 App bin，经
`Tools/etu_pack.py finalize` 按取证参数回填 fw_header，独立重算后与包内冻结的
板上 dump 逐字节比较。

```
app_bin_bytes=602984
finalize_sha256   = 4512de0878c146a93b55f65aa86acab4eedcf7f7082ead97ad73c24884671b4b
board_dump_sha256 = 4512de0878c146a93b55f65aa86acab4eedcf7f7082ead97ad73c24884671b4b
fw_header_diff_bytes=78   （差异全部落在 0x400..0x45F，镜像正文未被触碰）
```

三方同值后，INFO 帧里的 32B 才真正绑定到「本仓库源码构建出的那一份镜像」，
而不只是「某个板上镜像」。

### 2.3 构建绿与逐字节可复现（两次独立复现）

本轮执行 `cmake --build … --target clean` 后全量重建双目标（App 103 步全编译、
Boot 亦真实重链，非 up-to-date）：

```
CONFIGURE_EXIT=0  CLEAN_EXIT=0  BUILD_EXIT=0
FLASH: 602984 B / 960 KB = 61.34%
text 601544  data 940  bss 561688   (X-Track-App-GCC.elf)
text  14720  data   4  bss   9780   (X-Track-Boot.elf)
```

| 产物 | 大小 | SHA-256 |
|---|---|---|
| X-Track-App-GCC.bin | 602984 | `7328c1b15feff7214378065ca3e7d556ac803b59ebed7029a892d64f15e2153f` |
| X-Track-App-GCC.elf | 872076 | `0d645338529659ad95aabcbf10e214f3627974b6cadfa66efad01ff94417f547` |
| X-Track-Boot.bin | 14724 | `5842ff3e19ba9e1eaaea10f27e825c7b6efc278b200531014b0dba61264f6594` |
| X-Track-Boot.elf | 36860 | `d21713ca2c1efeac949f8ec0ffddacac439fed6bf26f9c65641bee24464fdabc` |

与实现方声明的前 8B（`7328c1b15feff721` / `5842ff3e19ba9e1e`）一致。值得单独指出：
实现方那轮 Boot 是 up-to-date 未重链，本轮 Boot **真实重链后仍逐字节相同**，
可复现性比实现方证据更强。`ota_device_info.c.obj` 确实进入链接（1760 B，
`build.ninja` 中 4 处引用）。

警告口径如实记录：**0 错误**；警告全部为仓库既有基线（全对象共有的
`uses 2-byte wchar_t`、newlib `_isatty/_kill/_lseek/_read/_write is not
implemented`、`LOAD segment with RWX permissions`），本卡新增源无自身编译警告。

### 2.4 harness 鉴别力（注错反证）

静态属性核验易被「看起来很严格」骗过，因此另做三处红线注错，每处都保持可编译
（避免用编译失败假冒断言失败）：

| 注错 | 针对红线 | 结果 |
|---|---|---|
| M1 raw 域被 fw_header 双零域覆盖 | 禁止混用两域 | 退出码 1，6 项断言变红（T1/T7×3/T4） |
| M2 `E-Track` → `X-Track` | OTA-XC-DEVICE-MODEL | 退出码 1，`T1 model exact 8B` 变红 |
| M3 BCB 仲裁 ERROR 不再拒绝 | IO 失败必须 fail closed | 退出码 1，`T5 bcb io fail closed`、`T5 out untouched` 变红 |

三处均 `编译错误=False`；产品源逐字节复原（`c1188336e449b79e…` 前后一致）；
还原后复跑 `checks=114 failures=0`。**harness 不是橡皮章**。

### 2.5 范围与红线

卡内改动 9 项：`Libraries/OTA/ota_device_info.{c,h}`、`USER/HAL/HAL_Bluetooth.cpp`、
`MDK-ARM_F435/cmake-generated/CMakeLists.txt`、`MDK-ARM_F435/proj.uvprojx`、
`tests/ota/test_ota_device_info.{c,py}`、`docs/ota-exec-notes/P3-2-*.md` 两篇。

12 类红线路径（`boot/`、P3-1 BLE 资产、其他 OTA 模块、四份冻结契约文档、
`Tools/etu_pack.py`、`Tools/acceptance/`、`Tools/provenance/`、
`.github/workflows/`、`tests/ota-vectors/`）与 HEAD **完全一致，无一被改动**。
两份 CI workflow 无 fail-open 模式（`|| true`、`continue-on-error: true`、
`if: always()`、`set +e`、裸 `exit 0`）。实现 agent 未产生任何提交
（`merge-base..HEAD` 为 0 次提交），符合 §0 规则 8。

### 2.6 修复了一处真实的冻结契约违反

P3-2 之前的占位身份链上报 `model = "X-Track"`，违反 `OTA-XC-DEVICE-MODEL`。
本轮独立解码确认设备现在上报 `E-Track\0`（7 ASCII + NUL 恰 8B），违反已消除。

## 3. 非阻断发现

### 3.1 F-1：`cmake-generated/CMakeLists.txt` 被编辑器整体行尾归一（547 行伪变更）

事实（本轮实测）：

```
工作区    bytes=55063  总行=957  CRLF=0    纯LF=957
HEAD blob bytes=55540  总行=956  CRLF=547  纯LF=409
忽略行尾后的真实差异行数 = 1
    + "${CMAKE_CURRENT_LIST_DIR}/../../Libraries/OTA/ota_device_info.c"
```

HEAD 里这个文件本身是**混合行尾**，实现方的编辑器把它整体归一成纯 LF，于是
1 行真实改动带出 547 行行尾伪变更。

为什么不只是观感问题：`Tools/provenance/source_manifest.ps1` 哈希的是**工作区
字节**，而该文件当时未被 `.gitattributes` 保护，`core.autocrlf` 会在下次检出时
把它变回 CRLF。Git 自己给出了直接证据：

```
warning: in the working copy of 'MDK-ARM_F435/cmake-generated/CMakeLists.txt',
LF will be replaced by CRLF the next time Git touches it
```

也就是说，在纯 LF 工作副本上冻结的 Production 指纹**先天不可复现**——这是指纹
有效性问题，不是排版偏好。

处置（见 §4 已授权偏差 DEV-1）：本会话按 P3-6 先例补 `.gitattributes` 行尾护栏
（该文件不属任何 manifest profile，改动对指纹中性；`git hash-object` 过滤前后
一致，证明加 `-text` 对入库字节中性）。补护栏后上述警告消失，
`git check-attr text` 对 9 条新增路径均为 `unset`。

**未做**两件事，理由如实说明：不自行把 CRLF 改回去（那会让验收方兼任实现方，
违反 §0 规则 4）；不因空白差异退回本卡（1 行真实改动是必要的构建注册，
功能与契约均无问题）。代价是这次一次性的 547 行归一会落到 main —— 换来的是该
文件**首次**变成字节稳定、可复现指纹。

### 3.2 F-2：派工书未把 `MDK-ARM_F435/**` 写入允许修改范围（本会话的遗漏）

我冻结的 `docs/ota-prompts/prompt-P3-2-implementation.md` 列出的允许修改范围
未包含 `MDK-ARM_F435/**`，而实现方必须改 `CMakeLists.txt` 与 `proj.uvprojx`
才能让新增的 `Libraries/OTA/ota_device_info.c` 进入两条构建链。

裁定：**判为「范围内必要」**，不计为越界。理由：新增卡内产品源必然要求构建注册，
这是机械必要项，不是自选扩张；两处改动内容各只有一行/一组文件条目，无其他夹带
（本轮逐行核对过）。责任在派工书作者（本会话），不在实现方。

改进：后续派工书在允许范围里显式写出构建注册路径。

### 3.3 其他两项候选发现在核实中自行消解（如实记录）

- 曾怀疑「应改生成脚本而非手改生成物」：核实后 `keil_uvprojx2cmake.py`
  **未入库**，手改 `CMakeLists.txt` 是当前仓库唯一可行路径。
- 曾怀疑 `.cache-cmake-time-test.cmake` 是本卡残留：其时间戳为 8 月 13 日，
  早于 P3-2 约三周，属既有残留。

## 4. 已授权偏差

| ID | 内容 | 范围 | 证据 |
|---|---|---|---|
| DEV-1 | 验收会话补 `.gitattributes` 行尾护栏 9 条（本卡 4 条产品/测试源 + 4 条本轮核验器 + 1 条构建文件） | 仅 `.gitattributes`，不属任何 manifest profile，对三类指纹中性 | `commands/verify-scope.log`、本文件 §3.1；P3-6 先例（其验收会话同样自行补护栏） |
| DEV-2 | 注错反证脚本冻结为包内产物而非接入 CI | `artifacts/mutation_probe.py` + `commands/mutation-probe.log` | 该脚本会临时改写产品源，接入 CI 会带来 CI 侧写产品目录的风险；冻结为可手工复跑产物更安全 |
| DEV-3 | `python3` 在本机是 Windows 应用执行别名（rc=49），全部命令改用 `python -X utf8 -B` | 所有命令记录 | P3-6 合同 DEV-5 同款先例 |
| DEV-4 | 实现方证据/research 笔记所在 `docs/ota-exec-notes/**` 不属任何 manifest profile，无法由 `input_groups` 绑定 | 以 `external_inputs` 显式冻结包内副本与 SHA-256；profile 范围变更须走 acceptance-governance CI，不在本卡处置 | `external/P3-2-implementation-evidence.md`、`external/P3-2-identity-research.md`；P3-1-v2 DEV-3、P3-6 DEV-1 先例 |
| DEV-5 | 真机取证件（板上镜像 dump 与 RAM 快照）由实现方经 J-Link 采集，验收会话因 J-Link USB 链路故障无法重新采集 | 五件真机产物按 `hardware_state` 类外部输入声明并绑定 SHA-256；独立性由「解码与重算全部独立重写」+ C05 把摘要绑回本仓库源码重建结果保证，而非靠重新采集 | `artifacts/realdevice/*.bin`、本文件 §5 |
| DEV-6 | C11 门槛绑定 `p3_2_verify_scope.py` 的核对项总数 `checks=23`，与 P3-6 DEV-4「不得把核对项总数写进门槛」的处置相反 | 差异是刻意的：本卡核验器把未跟踪文件**聚合为单一检查项**，故总数在不同轮次恒为 23，是不变量而非计数；随验收产出增长的 `tracked`/`untracked_new`/`acceptance` 计数只出现在汇总行，不进门槛 | `commands/verify-scope.log`、`tests/ota/p3_2_verify_scope.py` 模块 docstring |

## 5. 范围外未观测项（不影响本卡完成判据）

实现方 §7.5 已如实记录：R10「seq=0x1234 回显铁证」补证因 J-Link USB 链路死亡
而未完成，需物理拔插/断电恢复，超出 agent 自动化能力，按「连续三次失败即停止」
纪律停止重试。

本轮独立评估：该补证的目标是排除「帧为更早 seq=0 残留」这一解释。本轮已用**不
依赖 seq 的独立证据**覆盖同一风险——帧内 32B 摘要必须等于板上镜像的 raw
SHA-256，而板上镜像又等于本仓库源码重建后 finalize 的镜像（三方逐字节闭合）。
一个「更早的残留帧」不可能携带与当前源码构建结果一致的摘要。故该补证
标记为 `ENV_BLOCKED` 的**加强项**，不属完成判据缺口。

### 5.1 冻结后更新：R10 已实际观测（2026-09-03）

用户物理恢复 J-Link 链路后，本验收会话已完成该补证，结果
**42 项核对全绿 `P3_2_R10=PASS`**：喂帧前 `tx_frame` 60 字节全零（复位后
session init 清零），喂帧后应答 `seq` 回显 `0x1234`，与冻结轮 `seq=0` 的帧
整帧差异**恰好 4 字节**（seq 2B + CRC 2B），50B payload 逐字节相同；固件全程
存活（PC 前后同为 `0x8026432`，落在 LVGL 渲染循环，非 Reset_Handler/fault）。
硬件操作沿用实现方已调试脚本，解帧与 CRC 重算由验收方独立重写。

完整方法、原始十六进制、地址前置复核与产物哈希见
`docs/ota-exec-notes/P3-2-acceptance-r10-addendum.md`。

该项状态由 `ENV_BLOCKED` 升级为**已观测**。**冻结合同与证据矩阵不做追溯编辑、
不升 v2**：R10 属 `scope.excluded_by_freeze`，不是任何判据的门槛，其结果无论
正负都不改变本轮 12 条判据的 `PASS`；升 v2 只会强制整轮重跑或引入 `REUSED`
复用链，对一条不入门槛的加强项付这个代价收益为零。理由详见补证笔记 §8。

## 6. 收口前必须处理（主会话事项）

当前工作树把三批改动混在同一分支 `ota/p3-7-card` 上：

1. P3-2 卡内 9 项（实现方产出，未提交）；
2. P3-7 立卡批次 3 项 + 共有的 `PLAN-OTA-EXEC.md`（本会话早前产出，未提交）；
3. 本轮验收产出（核验器、证据包、合同、矩阵、护栏、看板回写）。

按 §0 规则 8，子会话不执行 `git commit/push/merge`。收口时应拆成互不夹带的独立
提交，且 `.gitattributes` 与 `PLAN-OTA-EXEC.md` 由后两批共同持有需按内容归位。
需用户确认后由主会话执行。

## 7. 命令与产物索引

命令日志（`docs/acceptance-contracts/P3-2-v1/commands/`）：
`verify-realdevice.log`、`verify-harness.log`、`verify-scope.log`、
`verify-build.log`、`host-test.log`、`mutation-probe.log`、
`build-gcc-production.log`、`build-artifacts.log`、`governance-gate.log`。

包内产物（`artifacts/`）：`realdevice/{app_dump,info_frame,identity,sess_full,
feed_before}.bin`、`build/nm-app-gcc-symbols.txt`、`mutation_probe.py`。
实现方声明（待核对，非判据来源）冻结在 `external/`。

产物哈希、文件大小与三类 manifest 指纹见证据矩阵；本文件按看板与笔记的分工，
不重复承载指纹清单以外的哈希索引。

## 8. 冻结指纹与校验器结论

| 对象 | SHA-256 / 指纹 | 备注 |
|---|---|---|
| `docs/acceptance-contracts/P3-2-v1.contract.json` | `1520787999B606ABA6270B5D1F9F3449939DDD7E98D9A004EAEC581CF0F3C60B` | 35363 B；矩阵 `contract_sha256` 与此逐字符相同 |
| `docs/acceptance-contracts/P3-2-v1/P3-2-v1.evidence-matrix.json` | `469CE6B08CFA7441B618FAB11C38C82ABEDE22CF8A11F9438049706273246A60` | 18313 B；12 判据全 `EXECUTED PASS`，无 `REUSED` |
| Production manifest（2920 文件） | `ManifestSHA256 = A1DC6E8C0308E6B08B3B24AF60B182205EA32FADAA222F9DE05F3BD435478764`；`ManifestJsonSHA256 = F25EFBED6D8BC1E8B827F43E5BA9542AACA3F75CFF3BA62D7B8B1FE4FA88E7E8` | GCC 生产输入全集 |
| Validation manifest（152 文件） | `ManifestSHA256 = 189861A3178D649812C571B84EC8626ABBC0558252EC58331BF347842AB8E11B`；`ManifestJsonSHA256 = B8E772D739224A434C2E35DEAE4326449366ED182147E8AA1F4850CC192BE6BA` | `Tools/` + `tests/` 全量 |
| Governance manifest（26 文件） | `ManifestSHA256 = 014C3982F43D96659C0A9D9141C61A46E397084164FAF4E899878352071D59C9`；`ManifestJsonSHA256 = E50F9C5016C41820357E755B128C3FD6ACF2243245ECF560E9569775FBF3B372` | 看板、规约、契约、派工书 |

校验命令与结果：

```text
python Tools/acceptance/validate_bundle.py \n  --contract docs/acceptance-contracts/P3-2-v1.contract.json \n  --matrix docs/acceptance-contracts/P3-2-v1/P3-2-v1.evidence-matrix.json \n  --repo-root D:/github/my/E-Track
VALIDATION=PASS contract=P3-2-v1 round=P3-2-V1-FREEZE-20260903-01 overall=PASS
退出码 0
```

该次校验由校验器从本轮精确 worktree **重新枚举并逐文件读取**三个 profile 的真实文件，因此它同时构成两条附带结论：①注错反证脚本对 `Libraries/OTA/ota_device_info.c` 的临时改写已逐字节还原（Production 指纹未变）；②看板回写发生在 manifest 冻结之前，Governance 指纹未过期。

`observed` 取值的派生方式：由生成器从包内原始 stdout 按正则逐元素派生（段内 `ok` 行计数、核对行取值按 Python 字面量解析、判定行与汇总行独立提取），派生完成后再与冻结合同 `gate.expected` 做**列表全等断言**，不一致即拒绝生成矩阵；全部 12 条判据在首次成功运行时即全等，未从 `expected` 反抄。
