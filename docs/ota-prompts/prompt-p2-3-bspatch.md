你是本轮的【实现会话】。任务：认领并实现 OTA 看板任务卡 P2-3「bspatch 流式集成」。

## 起点

仓库根工作树当前在 main / 14d5476（干净，与 origin/main 同步）。以此为基线。

## 先读（不要跳过，不要凭记忆替代）

1. `AGENTS.md` 的「OTA 执行规约」——你受其全部约束。
2. `PLAN-OTA-EXEC.md` 的 §0 认领规则 + P2-3 卡全文 ——唯一状态源。
3. `docs/ota-binary-contracts.md`：§143-158（40B 内层头逐字段表 + MCU 侧校验顺序）、
   §502-531（OTA_EXCLUSIVE、流式内存契约、§520 内存预算表）。冻结契约，只读。
4. `.claude/verification-report-ota-plan.md` 的「修正 2」（第 37 行起）+ 第 67 行
   「P2 注意项」——禁照抄 README `malloc(old_size)` 的原因与正确集成方式。
5. `docs/ota-exec-notes/P2-2-etu-full-package-research-2026-07-29.md` 与
   `P2-2-implementation-evidence-2026-07-29.md` ——P2-3 与 P2-2 共用解密/解压/
   candidate 写入链，必须复用而非另写一套。

## 认领

把 P2-3 状态从「待办」改「进行中」，填认领标识+日期（规约 §0）。本会话只认领这一张
卡，不越卡「范围」改文件。

## 目标（照卡执行，不得自行放宽）

差分链：base_vcode + base_sha8 校验 → 解密 → LZMA 解压 → bspatch → candidate。

集成方式是本卡核心约束（复审修正 2），逐条落实：

- old = 内部 flash XIP 指针直读（`0x08010000`），不复制到 RAM。
- patch 输入 = QSPI staging 流式 reader，替换 vFile 的 RAM-only 假设。
- new 输出 = `bs_flash_write` 回调按 1KiB 块写 QSPI candidate，用 P0-5 安全 API。
- 40B 内层头按契约 §143 表逐字段解析，禁止 struct memcpy。
- 内层 `ph_ocrc` 作二重兜底。

校验顺序严格按契约 §158，不得重排、不得省略：

```text
ph_hcrc(置零重算) → ph_psize 与 .etu payload_len-40 一致 →
解压长度 == ph_original_size → bspatch 前 ph_osize/ph_ocrc 对基版 →
合成后 ph_nsize/ph_ncrc 对 candidate
```

禁止把 old / new / 完整 patch / 完整解密包整体读入 RAM（契约 §512）。
任何未取得 `OTA_EXCLUSIVE` 的路径不得启动 LZMA/bspatch（契约 §531）。

## vendor 侧现状（已核实，这是本卡主要改造面）

vendor 源在 `bsdiff_lzma_AES128-main/bspatch/`。对外 API：

```c
int bspatch(const uint8_t *old, int64_t oldsize, uint8_t *new, int64_t newsize,
            struct bspatch_stream *stream);

struct bspatch_stream {
    void *opaque_r;
    int (*read)(const struct bspatch_stream *stream, void *buffer, int length);
    void *opaque_w;
    int (*write)(const struct bspatch_stream *stream, void *buffer, int length);
};
```

`bspatch_stream` 的 read/write 回调本身是流式友好的，可以直接挂 QSPI reader 与
flash 写回调。

真正的 RAM-only 假设在 `bsdiff_lzma_AES128-main/bspatch/user/interface.c`：

- 第 262 行 `bspatch_patch(patch_header_t, uint8_t *old_data, uint32_t old_size,
  uint8_t *patch_data, ...)` —— 签名要求完整 patch 在 RAM。
- 第 281 行 `vf = vfopen(patch_data, patch_size)` —— 把整个 patch 当内存数组。
- 第 85 行 `chunked_bspatch` 内 `bs_malloc(buffer_size)` 分配 `new_buffer`。
- 第 305 行 `vfopen(header_with_props, ...)` —— 这个是 40B 小头，可留。

不要照抄 `bspatch_patch` 的整包签名。正确做法是绕过它、直接驱动 `bspatch()` +
自建流式 stream，或把 vFile 换成 QSPI staging 流式 reader 实现。

vendor 目录尽量不改；确需改动必须在证据文档说明改了哪几行、为什么、以及是否影响
bsdiff 侧。

## 必须复用的既有模式（不要另起一套）

| 文件 | 复用点 |
|---|---|
| `Libraries/OTA/ota_package.{c,h}` | P2-2 的解析/校验/candidate 写入骨架 |
| `Libraries/OTA/ota_staging.{c,h}` | staging 流式读取 |
| `Libraries/OTA/ota_keys.{c,h}` | AES key 编译期注入（库内示例 key 仅开发） |
| `Libraries/OTA/ota_layout.h` | 布局常量唯一来源 |
| `USER/HAL/HAL_OTA_Package.{cpp,h}` | HAL 侧 workspace acquire/release 与 XIP 处理 |
| `USER/HAL/HAL_OTA_Staging.{cpp,h}` | HAL 侧 staging 接入 |

harness 开关照 `P2_2_TEST_ENABLE` 的现成模式加 `P2_3_TEST_ENABLE`，在
`MDK-ARM_F435/cmake-generated/CMakeLists.txt` 中（参照现有 51/54/60/70/691 行写法）：

1. `option(P2_3_TEST_ENABLE "..." OFF)`
2. 与 P1_6 / P2_1 / P2_2 两两互斥的 configure-time `FATAL_ERROR`（新增 3 条）
3. `list(APPEND OTA_TEST_LINKER_DEFINES "-DP2_3_TEST_ENABLE=1")`
4. `target_compile_definitions(X_Track_App_GCC PRIVATE "P2_3_TEST_ENABLE")`

若需 evidence control 区，照 P2-2 的 `0x800` 模式加在
`cmake/linker/x-track-app-gcc.ld.S`，并保持 `.ota_overlay` 四条断言与
P1-6 `0x200` / P2-1 `0x80` / P2-2 `0x800` 三段区不动。
测试头照 `Libraries/OTA/ota_p2_2_test.h` 的风格新建 `ota_p2_3_test.h`。

注意：`MDK-ARM_F435/cmake-generated/CMakeLists.txt` 是 `keil_uvprojx2cmake.py` 的
生成物，但本仓库已有先例在其中手工维护 OTA harness 开关块。沿用既有位置与风格；
不要改生成脚本，也不要重新生成该文件覆盖既有 OTA 块。

## 验收标准（卡上冻结，你负责让它可复现，但不自验收）

- `toy-patch.etu` 合成结果与 `toy-new.bin` 逐字节一致。fixtures 已在
  `tests/ota-vectors/` 齐备（`toy-old.bin` / `toy-new.bin` / `toy-patch.etu` /
  `expected.json` / `gen_vectors.py` / `test_vectors.py`），无需重新生成。
- 堆峰值实测 ≤ P0-6 预算：契约 §520 差分/extra 写缓冲 1024B、workspace 池 40960B。
  必须给出实测数字，不能只说「未超」。
- 宿主回归零回退，全部实跑：

  | 测试 | 期望 |
  |---|---|
  | fw_header vectors | `16/16` |
  | Boot Ymodem / ETSL | `19/19` |
  | BCB | `27/27` |
  | Boot state machine | `96/96` |
  | P1-6 control protocol | `21/21` |
  | OTA golden vectors | `9/9` |
  | P2-1 staging | `48/48` |
  | P2-2 package | `102/102` |

- 新增 P2-3 宿主测试放 `tests/ota/`，命名与 `test_ota_package.{c,py}` 一致
  （即 `test_ota_patch.c` / `test_ota_patch.py` 之类），覆盖正常链 + 每个拒绝分支。
  并在 `.github/workflows/firmware-build.yml` 的「Test Boot fw_header validator
  vectors」步骤（现有 5 行 `python3` 调用，约 167-171 行）追加一行。
- fresh GCC Release App/Boot 构建通过；Boot < 64KiB 且三个 LOAD 无 RWX；
  App 保留仓库既有 warning，报告时明说「有 warning、零 error」，不得粉饰。

## 环境与已知坑

- 在全新 checkout 里做，例如 `.cache/p2-3-<日期>`；不要动仓库根工作树（现干净且在
  14d5476，请保持）。
- 源码 `#include` 一律用正斜杠。Linux GCC 不把反斜杠当路径分隔符，本机 Windows 编过
  不算数（`AGENTS.md`「GCC / Linux CI 源码可移植防坑」）。提交前自检：

  ```powershell
  rg -n --glob "!**/build*/**" --glob "!**/vendor/**" "#include.*\\" Libraries USER
  ```

- Ninja 在本机会在首个 job 前挂起，改用 `Unix Makefiles`。
- 构建目录用短路径（如 `/tmp/etfw`）+ `-DCMAKE_OBJECT_PATH_MAX=1024`。
- App 镜像含 `__DATE__`/`__TIME__`（`USER/App/Version.h:76`），App 二进制 sha256 按
  构造不可复现。报告尺寸与逐字节 diff 定位即可，不要声称 App 哈希可复现。
  Boot 哈希可复现。
- 新增 `.c` 是纯 C，不受 Keil `--cpp11` group option 陷阱影响；但若新增 `.cpp` 到新
  group，必须复制既有 page group 的 `<GroupOption>` 块（`AGENTS.md` 有专节）。
- bspatch 最易犯的错是照抄 README 一把 `malloc(old_size)`：在 40960B 池里必然爆，
  而宿主 PC 上跑很可能不报错就过了。堆峰值必须真测。

## 禁止事项

- 不执行 `git commit` / `push` / `merge` / `rebase`（规约 §5，收口由主会话在用户
  确认后做）。
- 不修改 `PLAN-OTA.md`、`docs/ota-binary-contracts.md`（冻结契约）。发现矛盾或
  不可实现 → P2-3 置「阻塞」+ 卡内追加「阻塞记录:」一行 + 在看板 §9 变更登记表
  登记 + 停止该卡。禁止就地改契约继续实现。
- 不自验收、不把 P2-3 置「完成」。实现完成后保持「进行中」并声明待独立验收。
- 不跑 J-Link / RTT / 任何板卡命令；不碰 P1-6 物理断电点 03/05/07/15/16/17。
- P1-6 保持「进行中」，不得改其状态或 P1 进度数字。
- 不动 P1-6 / P2-1 / P2-2 的既有实现与证据文件。
- 不改 `.cache/` 下任何既有 evidence root。

## 交付

1. 编码前的检索与设计结论落盘
   `docs/ota-exec-notes/P2-3-bspatch-research-<日期>.md`（规约 §4，不许只留在会话
   回复里）。至少覆盖：vendor 三处 RAM-only 假设的处理方案、流式 stream 设计、
   内存预算逐项分配、与 P2-2 的复用边界。
2. 实现证据落盘 `docs/ota-exec-notes/P2-3-implementation-evidence-<日期>.md`：
   命令原文 + 关键输出 + 产物路径/尺寸/时间戳 + 堆峰值实测 + 逐字节一致性证明。
   长输出落盘，不要只贴摘要。
3. 会话收尾按规约 §6 回写 P2-3 卡状态，并在看板 §10 会话日志追加一行。
4. 向主会话汇报摘要，声明「待非实现会话独立验收」，不自行收口。
