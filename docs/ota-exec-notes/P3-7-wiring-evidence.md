# P3-7 接线证据与本地 fail-closed 反证

- 会话: Claude(P3-7 实现 agent, P3-7-WIRING-20260903)
- 日期: 2026-09-03(v1)/2026-09-03(v2 打回补做)
- 基线提交: `2d8ff7e52d4c575a4d109b1477a79a7c1493d81b`(main @ PR #18 合并后)
- 认领: 看板 §6 P3-7 已置「进行中」+ 认领标识(Python 字节编辑,diff 仅 1 行)
- v2 增量: 打回补做三件事 —— 追加第 4 条接线(`test_ota_device_info.py`)、
  修正 CI 反证选点(两处原选点会在第 8 条空转,见 §3.0)、反证由 3 次扩为
  4 次且每次先按 CI 同序跑全部 12 条命令定位红点。

## 1. workflow 改动内容(4 处执行行,同一批次)

文件: `.github/workflows/firmware-build.yml`(该文件在 HEAD 内为混合 EOL:
245 行 CRLF / 263 行 LF,且无 `.gitattributes` 护栏,故全程用 Python 字节
编辑;首次误用 Edit 工具产生整文件 EOL 归一伪 diff,已 `git checkout --`
丢弃后重做。v1 真实 diff `10+/1-`,v2 追加 1 行后为 `11 insertions(+),
1 deletion(-)`):

1. **步骤名**:`Test Boot fw_header validator vectors` →
   `Run host tests (boot vectors, OTA host tests, P3-1 product regressions)`
   (纯展示层;顶层 `name: MCU Firmware Build` 与
   `jobs.build.name: Build firmware (arm-none-eabi-gcc)` 未动,已断言核对)。
2. **执行行**:在既有 `set -euo pipefail` 块尾部追加 4 行裸执行 —— 前三行为
   `p3_1_verify_contract_alignment.py` / `..._text_isolation.py` /
   `..._portability.py`,第四行为 `test_ota_device_info.py`(打回补做追加,
   置末位而不按语义插入 host 测试组,避免移动已核验的 9/10/11 序号映射)。
   全部无 `|| true`、`continue-on-error`、`if:`、`set +e`。
3. **触发器**:`push` 与 `pull_request` 两份 `paths` 在
   `tests/ota/test_sdio_command_timeouts.py` 条目后同步各追加同序 3 个
   单文件精确条目(不用 `p3_1_verify_*.py` 通配,避免覆盖 5 个不接入的
   验收工具脚本;触发范围与执行范围严格互镜)。
   **v2 明确**:`test_ota_device_info.py` 已被现有
   `"tests/ota/test_ota_*.py"` 通配覆盖,paths **一行未加**——为其新增精确
   条目反而破坏「p3_1_verify_* 精确列举 ↔ test_ota_* 通配」的互镜判据。

### 结构校验(PyYAML 解析 + fnmatch 闭包复核,全部通过)

- 顶层 `name` / `jobs.build.name` 字节未变(红线);
- 两份 `paths` 列表逐项相等(同步,各 18 条,v1→v2 未动);
- 步骤内 12 条 `python3` 执行行全部被 `paths` 至少一条模式覆盖(闭包);
  其中 cmd9-11(三条 p3_1_verify)命中精确条目,cmd12 命中
  `tests/ota/test_ota_*.py` 通配;
- 目标步骤无 `continue-on-error` / `if` 字段。

### CI 步骤执行序(v2 后,12 条)

    cmd 1  tests/boot/test_fw_header_vectors.py
    cmd 2  tests/boot/test_boot_protocols.py
    cmd 3  tests/boot/test_boot_state_machine.py
    cmd 4  tests/ota/test_ota_staging.py
    cmd 5  tests/ota/test_ota_package.py
    cmd 6  tests/ota/test_ota_patch.py
    cmd 7  tests/ota/test_ota_ble_frame.py
    cmd 8  tests/ota/test_ota_ble_session.py
    cmd 9  tests/ota/p3_1_verify_contract_alignment.py
    cmd10  tests/ota/p3_1_verify_text_isolation.py
    cmd11  tests/ota/p3_1_verify_portability.py
    cmd12  tests/ota/test_ota_device_info.py

## 2. 本地基线(改动后工作树,12 条全绿)

| 命令 | 退出码 | 结论标记 |
|---|---:|---|
| `p3_1_verify_contract_alignment.py` | 0 | `P3_1_CONTRACT_ALIGNMENT=PASS drift=0 checks=47` |
| `p3_1_verify_text_isolation.py` | 0 | `P3_1_TEXT_ISOLATION=PASS cases=3 transparent=0 trace_points=1 sink_guard=True` |
| `p3_1_verify_portability.py` | 0 | `P3_1_PORTABILITY=PASS scanned=895 control_hits=1 live_hits=0 new_src_hits=0` |
| `test_ota_device_info.py`(v2 新增) | 0 | `P3_2_OTA_DEVICE_INFO checks=114 failures=0` / `P3_2_OTA_DEVICE_INFO_ALL=PASS` |
| `python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle` | 0 | 65 tests OK(v1 接线前后、v2 补做后各跑,均全绿) |

计数与 `P3-7-card-creation.md` §3 基线一致(`scanned` 893→895 为目录自然
增长,非判据字段)。

## 3. 本地 fail-closed 反证(v2:4 次,CI 同序预演)

### 3.0 v1 选点作废原因(打回裁定,留档)

步骤在 `set -euo pipefail` 下线性执行:cmd9-12 是新增行,cmd8 是
`test_ota_ble_session.py`。v1 原拟两处选点会先红在第 8 条——
`OTA_BLE_SYNC0 0xA5u→0xA55u`(test_ota_ble_frame.c 直接用该宏并硬编码
0xA5u)与 `ota_ble_ring.h` 反斜杠 include(同文件第 2 行 include 该头,
cmd7/cmd8 均编译它)——红点落在与本卡接线无关的既有测试上,第 9-12 行
根本不执行。v1 的孤立单脚本观测虽然成立,但不满足「红运行必须含全部
前置结论标记」的验收硬判据,故 CI 反证选点全部按 v2 更正。

18 个 `OTA_BLE_*` 常量中 11 个被 cmd7/cmd8(及更早命令)引用,实测安全
候选仅 `LEN_ABORT`/`LEN_ACK_BEGIN`/`LEN_ACK_OTHER`/`LEN_GET_INFO`;
其中 `LEN_ACK_OTHER 9u→8u` 实测仍会在 cmd8 红(`ota_ble_session.c:57,73`
的 `payload[OTA_BLE_LEN_ACK_OTHER]` 数组下标编译告警被 `-Werror` 升级),
`LEN_ABORT`/`LEN_GET_INFO` 同样红在 cmd7(本机快筛 rc=1/1)。
**最终安全选点为 `OTA_BLE_LEN_ACK_BEGIN 10u→11u`**(cmd7/cmd8 实测 rc=0/0,
漂移由 cmd9 独家捕获)。

### 3.1 反证一(cmd9 合同对齐)

- 注入:`Libraries/OTA/ota_ble_frame.h:47`
  `#define OTA_BLE_LEN_ACK_BEGIN 10u` → `11u`。
- 全序预演:cmd1-8 全绿,cmd9 红(rc=1):
  `[DRIFT] §5.6 ACK_BEGIN 10B: 契约=10 实现=11`,
  `P3_1_CONTRACT_ALIGNMENT=FAIL drift=1 checks=47`;cmd9 之前无红。
- 还原:`git checkout -- Libraries/OTA/ota_ble_frame.h`。
- 复绿:12 条全序 rc=0。

### 3.2 反证二(cmd10 文本隔离,选点沿用 v1)

- 注入:`USER/HAL/HAL_Bluetooth.cpp:180`
  `ota_ble_session_active(&s_ble_session) ? NULL : bt_text_sink,`
  → `? bt_text_sink : bt_text_sink,`(破坏活跃期文本 sink 置 NULL 接线)。
- 全序预演:cmd1-9 全绿,cmd10 红(rc=1):
  `FAIL: 未找到活跃期把文本 sink 置 NULL 的接线`
  `P3_1_TEXT_ISOLATION=FAIL ... sink_guard=False`。
- 还原:`git checkout -- USER/HAL/HAL_Bluetooth.cpp`。
- 复绿:12 条全序 rc=0。

### 3.3 反证三(cmd11 可移植性,选点改为 HAL_USB.cpp)

- 注入:`USER/HAL/HAL_USB.cpp` 文件首行插入
  `#include "nonexistent\path.h" /* P3-7 fail-closed probe */`(该文件
  纯 CRLF,插入行继承 CRLF)。
- 全序预演:cmd1-10 全绿,cmd11 红(rc=1):
  `[正式] 参与编译的手写源命中 1 处  USER/HAL/HAL_USB.cpp:1`,
  `P3_1_PORTABILITY=FAIL scanned=895 control_hits=1 live_hits=1
  new_src_hits=0`(阳性对照 `msc_diskio.c.old` 同轮仍命中,证明扫描正则
  有效;`new_src_hits=0` 证明注入点不在 P3-1 新源清单,红因唯一)。
- 还原:`git checkout -- USER/HAL/HAL_USB.cpp`。
- 复绿:12 条全序 rc=0。

### 3.4 反证四(cmd12 设备身份,v2 新增)

- 注入:`Libraries/OTA/ota_device_info.c:23`
  `k_ota_device_model[8]` 首字符 `'E'` → `'F'`(打破冻结金标向量;
  该常量与任何 `OTA_BLE_*` 宏、include 形态无关,cmd1-11 不受影响)。
- 全序预演:cmd1-11 全绿,cmd12 红(rc=1):
  `FAIL: T1 model exact 8B`(golden fixture 逐字节锚定把改漂捕获)。
- 还原:`git checkout -- Libraries/OTA/ota_device_info.c`。
- 复绿:12 条全序 rc=0。

### 3.5 复现方式

同序预演脚本:`.claude/p3_7_run_ci_sequence.py`(按 §1 的 12 条顺序
逐条 `python -X utf8 -B`,遇红即停并打印末 3 行;全绿 rc=0)。四次
反证的「注入→红在目标行→还原→全序复绿」均由该脚本驱动,每轮结束后
`git status --short` 确认注入文件零残留(仅剩 workflow/看板两处预期改动)。

## 4. CI 证据状态与待办

按看板 §0 规则 8,本实现会话不执行 `git commit/push/merge`。以下证据
需主会话推送后补齐(派工书完成判据要求真实 CI 运行日志,本地执行不算):

1. **正例**:特性分支推送接线 commit → run 绿,CI 日志含四条结论标记原文
   (v1 三条 + `P3_2_OTA_DEVICE_INFO_ALL=PASS`)。
2. **触发器反证**:再推一次**只改被接入脚本自身**的 commit
   (建议:`tests/ota/p3_1_verify_portability.py` 文件尾追加一行注释),
   确认 workflow 被触发且执行到该脚本(未被 `Libraries/**` 等模式掩盖的
   证据是:该 commit 的 changed files 仅此一个文件)。
3. **CI 版 fail-closed 反证**:§3.1-§3.4 的四次注入在特性分支各做一次
   临时提交 → 观测 job 红且红在对应执行行(红运行日志须包含全部前置
   结论标记,这是 `tests/ota/p3_7_verify_ci_evidence.py` 的硬判据,
   无效选点会判失败)→ 还原提交 → 转绿。注错提交必须留在特性分支,
   不得进入 main(收口时 squash,沿用 P3-6 先例)。

推送方案(建议主会话采用):分支名 `ota/p3-7-host-test-wiring`;提交序列
1 接线(含 4 条执行行)+ 2 触发器反证(注释 commit)+ 3-10 注错/还原 ×4;
收口 squash。CI run 标识、提交 SHA 与关键日志片段由执行推送的会话回填到
本文件 §5。

## 5. CI 运行证据(待推送后回填)

- [ ] 正例 run:
- [ ] 触发器反证 run:
- [ ] 反证一(cmd9)红 run:
- [ ] 反证一还原绿 run:
- [ ] 反证二(cmd10)红 run:
- [ ] 反证二还原绿 run:
- [ ] 反证三(cmd11)红 run:
- [ ] 反证三还原绿 run:
- [ ] 反证四(cmd12)红 run:
- [ ] 反证四还原绿 run:
