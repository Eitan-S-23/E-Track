# P2-3 bspatch 流式集成研究与设计（编码前落盘）

- 日期：2026-07-31
- 实现会话：Claude（P2-3 实现会话）
- 基线：`main` / `14d5476`（干净），独立 checkout `.cache/p2-3-20260731`
- 状态：编码前研究与设计冻结，待实现、宿主取证、独立验收

## 1. 任务边界

P2-3 只实现差分 `.etu` 路径，接受冻结组合 `flags=0x0007`（bit0 AES + bit1 LZMA
+ bit2 差分）。全量路径 `flags=0x000B` 属 P2-2，已完成，本卡不动其代码。

本卡同样**不**写 ETSL commit marker、**不**改任何 BCB 副本、**不**进 STAGED；
candidate 提交属 P2-5。

## 2. 权威输入（逐条已读）

| 来源 | 用到的内容 |
|---|---|
| `AGENTS.md`「OTA 执行规约」 | 认领/契约只读/证据/research 落盘/不自提交/收尾回写 |
| `PLAN-OTA-EXEC.md` §0 + P2-3 卡 | 认领规则、目标、验收 |
| `docs/ota-binary-contracts.md` §2.1 | 64B 外层头逐字段（base_vcode off44、base_sha8 off52） |
| 同上 §2.3（143-156 行） | 40B 内层头逐字段表 + 端序 |
| 同上 §2.3 注（158 行） | MCU 侧校验顺序，本卡按此实现，不重排不省略 |
| 同上 §2.4 | 外层头校验清单①-⑩，差分走⑧ |
| 同上 §10.2（502-507 行） | `OTA_EXCLUSIVE` acquire 前置、互斥、退出清零 |
| 同上 §10.3（510-531 行） | 内存预算表、流式契约、未取得独占不得启动 LZMA/bspatch |
| `.claude/verification-report-ota-plan.md` 修正 2（37-41 行）+ §6.3（67 行） | 禁照抄 README `malloc(old_size)`；old 用 XIP、new 用写回调、patch 走流式 |
| `docs/ota-exec-notes/P2-2-*.md` ×2 | 复用解密/解压/candidate 写入链与 arena 设计 |

## 3. vendor 现状核实：RAM-only 假设共 4 处（比卡上列的多 1 处）

卡片与提示词列出 `interface.c` 三处。实际逐行读完 vendor 后确认**还有第 4 处，
且位于 vendor 核心而非 user 层**，这决定了集成方式：

| # | 位置 | 假设 | 处理方案 |
|---|---|---|---|
| 1 | `bspatch/bspatch.c:49-98` `bspatch()` | 形参 `uint8_t *new`，第 72/78/89 行直接 `new + newpos` 读写，**从不调用 `stream->write`** —— `new` 必须是完整 4096B..603KB RAM 数组 | **不调用 `bspatch()`**。`bspatch_stream` 的 write 回调在核心里是死字段，挂上去也不会被调用。改为在 `ota_patch.c` 内实现同语义的分块驱动 |
| 2 | `user/interface.c:262` `bspatch_patch(..., uint8_t *patch_data, uint32_t patch_size, ...)` | 完整 patch 在 RAM | 不调用该函数（绕过整包签名） |
| 3 | `user/interface.c:281` `vfopen(patch_data, patch_size)` | 整个 patch 当内存数组 | 不用 vFile。patch 输入改走 P2-2 已验收的 `stream_append()` 4KiB 滑窗（QSPI staging 读 → 原地 AES-CTR 解密） |
| 4 | `lzma/lzma_decompress.c:207` `inBuf = vfgetpos(pf, &position)` | 把「整个压缩流的裸指针」交给 `LzmaDec_DecodeToBuf`，隐含全流在连续 RAM | 不用 `lzma_decompress_read()`。直接用 `LzmaDec_DecodeToBuf` + P2-2 的 4KiB 输入滑窗（P2-2 已证明可行） |
| 5 | `user/interface.c:85` `chunked_bspatch` 内 `bs_malloc(buffer_size)` | 需要主堆 malloc | 不用主堆。1KiB diff/extra 缓冲取自 40KiB 固定 arena（契约 §520 已为此预算 1024B） |

**结论：vendor 目录零改动。** 复用范围收窄为纯算法/数据文件，全部已在 P2-2 入库：
`lzma/LzmaDec.c`（解压）、`AES128_CTR/aes_core.c`（AES 块）。
`interface.c` / `vFile.c` / `lzma_decompress.c` / `bspatch.c` 一行不引用、不编译、
不修改，因此对 bsdiff 制包侧零影响（制包侧走 `bsdiff/build/bin/bsdiff.exe`，
与 bspatch 目录不共享源）。

`bspatch()` 只有 49 行核心逻辑，且必须逐块换成「读 diff → 加 old → 写 candidate」，
照搬后再改反而比重写更易掩盖流式边界错误。重写的算法语义严格对齐 vendor：
控制三元组 `offtin` 解码、`ctrl[0]` diff 段叠加 old、`ctrl[1]` extra 段直写、
`oldpos += ctrl[2]`、`ctrl[0]/ctrl[1]` 的 `<0 / >INT_MAX / newpos+ctrl>newsize`
三项 sanity check 全部保留。

### 3.1 offtin 编码坑（实测确认）

`ctrl[2]` 是 **符号-数值（sign-magnitude）编码，不是补码**：bit63 为符号位，
低 63 位为绝对值。toy-patch 实测首个控制三元组：

```text
原始 ctrl[2] 字节 = 0f00000000000080
vendor offtin/sign-magnitude = -15
按 little-endian int64_t 补码误读 = -9223372036854775793
ctrl = [4096, 0, -15]
```

实现必须逐字节按 vendor `offtin` 公式还原，禁止 `memcpy` 到 `int64_t` 后直接用。

原版 bsdiff 还会合法产生 `[0,0,z]`：该组不推进 `newpos`，但会执行
`oldpos += z`，随后由后续组继续输出。验收复现包包含 9 个 `[0,0,-256]`；因此
不能把 `ctrl[0]==0 && ctrl[1]==0` 一概视作死循环。实现只拒绝 `[0,0,0]`，并以
`ph_original_size = ph_nsize + 24*N` 推导的有限 `N` 精确约束总解码字节和控制组数。

## 4. 校验顺序（严格照契约 §158，不重排不省略）

```text
外层（§2.4 ①-⑩，差分分支）
  ① magic + header_len + header_crc32
  ② flags == 0x0007（差分组合）
  ③ alg_id == 1、key_id == 1
  ④ hw_rev == 本机     ⑤ layout_id == 本机     ⑥ min_boot_ver <= 当前 boot
  ⑦ target_vcode > cur_vcode（降级拒绝）
  ⑧ base_vcode == cur_vcode 且 base_sha8 == 当前镜像 SHA-256 前 8B
  ⑨ 包长/payload_len 上限（§0.5）
  ⑩ payload_crc32（覆盖加密后 payload，收齐后算，此阶段不得擦写 candidate）
内层（§158，取得 OTA_EXCLUSIVE 之后）
  1. ph_hcrc：off0..3 置零参与，CRC32 覆盖规范化 40B 全头，BE
  2. ph_psize == .etu payload_len - 40
  3. 解压长度 == ph_original_size
  4. bspatch 前：ph_osize / ph_ocrc 对基版（XIP 直读，流式 CRC）
  5. 合成后：ph_nsize / ph_ncrc 对 candidate（回读 QSPI 流式 CRC）
```

整改后的顺序实现：

- **首遍只解压不合成**：取得 workspace、解析 40B 内层头并分配一次 LZMA 状态后，
  把完整 bsdiff 流解压到固定 1KiB 缓冲并丢弃，确认实际长度恰等于
  `ph_original_size`、流正常终止且没有尾随压缩数据。该遍不读基版、不 prepare
  candidate，恢复冻结的第 3 步位置。
- **第 4 步随后执行**：首遍长度通过后才流式读取基版核对 ph_osize/ph_ocrc，仍在
  `candidate_prepare` 之前，错基版不会擦 candidate。
- **第二遍重绕后合成**：复用同一 LZMA allocation，重置 AES-CTR/LZMA 状态并跳过
  同一 40B 头，再按控制组流式合成。双遍不新增与镜像大小相关的 RAM。

`base_sha8` 语义按 toy 向量实测确认 = 基版**整文件** SHA-256 前 8B
（`toy-old.bin` file_sha256 `3081fa0afc5bb2f3…` == 外层头 base_sha8），
不是 fw_header 里的双零法 image_sha256。设备侧对应「当前运行镜像
`[0x08010000, 0x08010000+image_len)` 的 SHA-256 前 8B」。

## 5. 流式 stream 设计

### 5.1 三条数据通路

```text
old     : XIP 直读 (const uint8_t *)0x08010000 + oldpos      —— 零拷贝，不进 RAM
patch   : QSPI staging --package_read--> 4KiB input 滑窗 --AES-CTR 原地解密-->
          LzmaDec_DecodeToBuf --> 1KiB patch_out 环形消费（控制/diff/extra）
new     : 1KiB diff/extra 工作缓冲 --candidate_program--> QSPI candidate
          （P0-5 安全 API，写后立即 candidate_read 回读比对）
```

`old` 的 XIP 直读需要 `image_len` 边界钳制：`oldpos + i` 落在
`[0, ph_osize)` 内才叠加，与 vendor `bspatch()` 第 77 行的
`(oldpos+i>=0) && (oldpos+i<oldsize)` 语义一致；越界不读、按 0 处理。

### 5.2 patch 侧「双层流」

差分 payload 明文 = 40B 内层头 + LZMA 流，LZMA 流解压后 = 裸 bsdiff 流
（控制三元组 + diff + extra 交错，**无 ENDSLEY/BSDIFF43 magic**，
实测 `ph_original_size=4120 = 24B 控制 + 4096B diff`）。因此需要两层：

- 外层：`stream_append()`（P2-2 已验收）从 QSPI 读密文 → 原地解密 → 4KiB 滑窗。
- 内层：`patch_stream_read(dst, len)` 按需驱动 `LzmaDec_DecodeToBuf`，把解压
  输出放进 1KiB 缓冲后按 len 拷出。`len` 只会是 8（控制字）或 ≤1KiB 的分块，
  所以 1KiB 缓冲足够，不需要按 `ctrl[0]` 大小分配。

一处关键差异：P2-2 的解压输出**直接就是** candidate 字节，可以边解压边写 flash；
P2-3 的解压输出是 patch 指令流，必须先被 bsdiff 状态机消费，再产出 candidate 字节。
所以 P2-3 需要一个额外的 1KiB「patch 解压输出环形缓冲」，这正是契约 §520
「bspatch 差分/extra 写缓冲 1024B，与解压缓冲分开」预算的那 1KiB。

### 5.3 分块合成主循环

```c
while (newpos < ph_nsize) {
    读 3×8B 控制字（经 patch_stream_read）→ offtin 解码
    sanity: ctrl[0]/ctrl[1] >= 0 && <= INT_MAX && newpos+ctrl[0] <= nsize
    /* diff 段：分 1KiB 块 */
    while (left > 0) {
        take = min(left, 1024)
        patch_stream_read(work, take)                  // 解压出的 diff 字节
        for i in take: if (oldpos+i < ph_osize) work[i] += XIP_old[oldpos+i]
        candidate_program(newpos, work, take) + 回读比对
        newpos += take; oldpos += take; left -= take
    }
    sanity: newpos + ctrl[1] <= nsize
    /* extra 段：分 1KiB 块，直写不叠加 */
    while (left > 0) { ... patch_stream_read + candidate_program ... }
    oldpos += ctrl[2]                                   // 可负，sign-magnitude
}
```

峰值 RAM 只与「1KiB 工作缓冲 + 1KiB 解压缓冲 + 4KiB 密文滑窗 + LZMA 状态」有关，
与 `ph_osize`/`ph_nsize` 无关 —— 这是「不照抄 malloc(old_size)」的实质。

## 6. 内存预算逐项分配（契约 §520 对账）

复用 P2-2 的 40KiB 固定 arena（`.ota_overlay` @ `0x20058000`，`OTA_POOL_CEILING
= 40960`）。P2-3 状态结构相对 P2-2 的增量只有 patch 解压缓冲，其余全部同构：

| 项 | 字节 | 契约 §520 对应行 |
|---|---:|---|
| `CLzmaDec` | 100 | `CLzmaDec` 100 |
| LZMA 概率表（lc=2,lp=0,pb=0 → numProbs=5056×2B） | 10112 | LZMA 概率表 10112 |
| LZMA dictionary（props 内 16384，实测 toy 为 4096；上限按 16KiB 预算） | ≤16384 | dictionary 16384 |
| patch 解压输出缓冲 `patch_out` | 1024 | LZMA 解压输出缓冲 1024 |
| diff/extra 工作缓冲 `work` | 1024 | bspatch 差分/extra 写缓冲 1024（**本卡新增项，预算已预留**） |
| 回读比对缓冲 `verify` | 1024 | 归入 hash/CRC 与 allocator 开销 2048 |
| staging 活跃窗口 `input` | 4096 | 单个 BLE/staging 活跃窗口 4096 |
| `AES_ctx` + counter + keystream | 192+ | AES-CTR context + counter 192 |
| parser/控制流元数据（40B 头、3×i64、offtin 临时） | ≤512 | parser/vFile/控制流元数据 512 |
| **合计（16KiB 字典口径）** | **≈34.5K** | 已知工作集小计 35492 |

`verify` 缓冲取 1024（与 `work` 同尺寸即可满足 1KiB 块回读），不新增预算行。
实际峰值由实现导出 `workspace_peak` 实测回填证据文档，不用估算值交付。

## 7. 与 P2-2 的复用边界（不另起一套）

| 复用 | 方式 |
|---|---|
| `ota_package.c` 的 AES-CTR 流（`aes_stream_init/xcrypt`、counter 从 byte15 进位） | 语义与实现照搬，但**在 `ota_patch.c` 内自包含**（理由见 §7.2） |
| `stream_append` / `stream_read_exact` 4KiB 滑窗 | 同上 |
| arena（`arena_alloc`/`arena_free`/peak 统计） | 同上 |
| `ota_package_io_t` 六个回调（package_read / candidate_prepare / program / read / workspace_acquire / release） | **原样复用，不扩字段**。P2-3 只多需要「old 镜像读」，而 old 走 XIP 常量地址，宿主测试用同一 io 结构无法表达 → 单独加一个 `base_read` 回调（见 §7.1） |
| `ota_keys.c` 编译期 key 注入 | 直接调 `ota_keys_get_aes128` |
| `ota_layout.h` 布局常量 | 唯一来源，不再定义地址 |
| `boot_crc32*` / `boot_sha256*` / `boot_fw_header_validate_ex` | 直接调，不重写 CRC/SHA/fw_header 口径 |
| `HAL_OTA_Package.cpp` 的 overlay owner / XIP 恢复 / QSPI 安全写 | 新增 `HAL::OTA_PackageApplyPatchStaging()` 复用同一组静态回调，不复制 QSPI 代码 |

### 7.1 API 形态

新增 `Libraries/OTA/ota_patch.{c,h}`，与 `ota_package.h` 同风格：

```c
typedef struct ota_patch_io_t {
    void *ctx;
    /* 与 ota_package_io_t 同语义的六个回调 */
    int (*package_read)(void *ctx, uint32_t off, uint8_t *dst, uint32_t len);
    int (*base_read)(void *ctx, uint32_t off, uint8_t *dst, uint32_t len); /* 基版：MCU 侧 = XIP memcpy */
    int (*candidate_prepare)(void *ctx, uint32_t image_len);
    int (*candidate_program)(void *ctx, uint32_t off, const uint8_t *src, uint32_t len);
    int (*candidate_read)(void *ctx, uint32_t off, uint8_t *dst, uint32_t len);
    int (*workspace_acquire)(void *ctx, uint8_t **ws, uint32_t *ws_len);
    void (*workspace_release)(void *ctx, uint8_t *ws, uint32_t ws_len);
} ota_patch_io_t;

ota_patch_result_t ota_patch_apply(const ota_patch_io_t *io,
                                   const ota_patch_device_t *device,
                                   uint32_t package_len,
                                   ota_patch_info_t *out_info);
```

`base_read` 而非直接写死 `(const uint8_t *)0x08010000`：宿主测试必须能喂
toy-old.bin，且 MCU 侧实现就是一行 `memcpy` XIP —— 仍然是「XIP 指针直读、
不复制到 RAM」（memcpy 到 1KiB 工作缓冲的是**当前块**，不是整镜像）。
`device` 增加 `base_image_sha8[8]`（当前运行镜像 SHA-256 前 8B）与
`base_image_len`，供⑧与 ph_osize 交叉校验。

### 7.2 为何 AES/arena/滑窗三原语自包含而不提取共享（技术债显式登记）

`ota_package.c` 里这三个原语全是 `static`，直接链接复用必须先把它们提取到
新的共享翻译单元并改 `ota_package.c` 的实现。权衡后**选自包含**：

- P2-2 已通过独立验收并收口（提交 `docs(ota): accept P2-1 and P2-2`），其真机
  r3 证据（`.cache/p2-2-hardware-evidence-20260729-r3`，112 checks）绑定当时的
  `ota_package.c` 字节。提取共享会改动该文件，使已验收证据与源码脱节，
  按规约需要重跑 P2-2 真机取证 —— 而本卡明确禁跑板卡命令，且「不动 P2-1/P2-2
  既有实现与证据」是提示词红线。
- 反向代价：AES-CTR 流（约 40 行）、arena（约 30 行）、4KiB 滑窗（约 70 行）
  暂时存在两份，违反 DRY。

**登记为待收敛技术债**：建议在 P2-5 或 P2-6（届时 P2-2/P2-3 会因 BCB/STAGED
接入或 RAM 峰值回填而本就需要改动与重新取证）一并提取
`Libraries/OTA/ota_stream.{c,h}`，两卡同时切换、一次性重跑真机证据。
本卡在实现中保持两份代码**逐字段同构**（同名函数、同顺序、同边界条件），
使后续提取是纯机械移动，不含语义合并风险。

## 8. `OTA_EXCLUSIVE` 与失败原子性

- `workspace_acquire` 成功之前不启动任何 LZMA/bspatch 工作（契约 §531）。
- acquire 失败 → 返回 workspace 错，**不擦写 candidate**。
- 外层①-⑩ 与内层 1/2/3/4 全部在 `candidate_prepare` 之前；解压坏、长度不符、
  ph_osize/ph_ocrc 不符均不会擦写 candidate。
- prepare 之后的失败（控制流坏、第二遍输入变化、合成坏、ph_nsize/ph_ncrc 不符、flash 失败）允许
  留下无 commit marker 的半成品 candidate，但 BCB 逐字节不变（本卡不含 BCB 回调）。
- 所有出口 `secure_zero(workspace)` 后 `release`（清 key / counter / LZMA 状态 /
  I-O 数据），与 P2-2 同一模式。

## 9. 测试与证据计划

宿主测试 `tests/ota/test_ota_patch.{c,py}`，命名与编译方式照 `test_ota_package.{c,py}`：

- 正常链 1：`toy-patch.etu` + `toy-old.bin` → candidate **逐字节等于** `toy-new.bin`；
  校验 image_len / target_vcode / 双零 SHA / arena 峰值。
- 正常链 2：仓库未修改 `bsdiff.exe` 生成的 11 组控制回归，含 9 个
  `[0,0,-256]`，必须通过公开 `ota_patch_apply()` 并逐字节得到预期新镜像。
- 拒绝分支逐条覆盖（每条都断言「candidate 未被擦写」或「prepare 计数为 0」）：
  外层 magic / header_len / header_crc / flags(误用 0x000B) / alg / key /
  hw_rev / layout / min_boot / 降级 target_vcode / base_vcode 不符 /
  base_sha8 不符 / 包长 / payload_crc；
  内层 ph_hcrc / ph_psize 不符 / ph_osize 与基版长度不符 / ph_ocrc 不符 /
  解压长度 != ph_original_size / ph_nsize 越界 / ph_ncrc 不符 /
  LZMA props 非冻结值 / 字典越界 / 控制字 sanity（`[0,0,0]`、ctrl 负数、越界）/
  fw_header 校验失败 / 外层与 candidate 元数据不一致 /
  workspace acquire 失败 / short workspace / flash prepare/program/readback 失败。
- 内存：断言 `workspace_peak <= 40960`，且工作缓冲尺寸常量 == 1024。

真机 evidence harness 按 P2-2 模式加 `P2_3_TEST_ENABLE` + `0x800` 控制区
（`.p2_3_control`），本卡实现侧只保证可构建与 host 可复现；J-Link 真机取证
不在本会话执行（提示词明确禁跑板卡命令），留独立验收会话决定。

## 10. 红线

- 不改 `PLAN-OTA.md` / `docs/ota-binary-contracts.md`。
- 不改 vendor `bsdiff_lzma_AES128-main/` 任何文件。
- 不 struct memcpy 解析任何 wire format（40B 内层头逐字段）。
- 不把 old / new / 完整 patch / 完整解密包整体读入 RAM。
- 不用主堆 malloc/new，arena 不回退主 RAM。
- 不写 BCB、不写 ETSL commit marker、不进 STAGED。
- 不动 P1-6 / P2-1 / P2-2 既有实现与证据。
- 不 `git commit/push/merge`，不自验收，不置 P2-3 为「完成」。
- 不跑 J-Link / RTT / 板卡命令。
- 源码 `#include` 一律正斜杠。
