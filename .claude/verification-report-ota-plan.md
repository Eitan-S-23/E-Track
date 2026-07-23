# 复审报告：PLAN-OTA.md v1.3 审查结论核查

生成时间：2026-07-23
复审对象：另一 agent 对 `PLAN-OTA.md` v1.3 的静态审查结论（8 条阻断项 + P0-P5 顺序 + 最终判定）
复审方式：逐条打开被引用文件核对行号与内容，未修改任何源码/方案文件。
（注：`.claude/verification-report.md` 为 2026-06-17 Dialplate 皮肤任务旧报告，保留未动，本报告独立成文。）

## 一、总体结论

**维持原审查的最终判定**：PLAN-OTA.md v1.3 可作为实现基线，当前仓库不能标记为 OTA 可用，须按 P0→P5 完成后才满足端到端功能。原审查引用的全部代码证据（10 处抽查）均命中真实文件与行号，无捏造。但有 **2 处结论表述过重需修正、3 处重要事实遗漏需补充、1 条建议（Ed25519 提前）不应采纳**。

综合评分（对原审查报告）：**92/100，通过**。扣分点见下文三、四节。

## 二、逐条证据核实结果（全部属实）

| # | 原审查论断 | 核实 |
|---|---|---|
| 1 | 方案自称 P0 契约基线、codex 未跑构建/真机 | ✅ PLAN-OTA.md:3、PLAN-OTA-REVIEW-LOG.md:351/355 原文一致 |
| 2 | App 仍链接 0x08000000、VTOR 偏移 0 | ✅ generated_linker.ld:11 `ORIGIN=0x08000000`；system_at32f435_437.c:38 `VECT_TAB_OFFSET 0x0`，且 SystemInit 于第 100 行重写 VTOR（与方案 §4 所述行号吻合） |
| 3 | MCU BLE 仅文本协议，OTA() 只打印 | ✅ Bluetooth.cpp:20 encode 状态机只认 `+...\r\n`；OTA()（:60-68）仅向调试串口回显；Bluetooth.h:19 收包缓冲 256B |
| 4 | UART 环形缓冲 512B、200ms 周期 X-Trace | ✅ mcu_config.h:40 `SERIAL_RX_BUFFER_SIZE 512`；HAL_Bluetooth.cpp:67 发送；HAL.cpp:107 `taskManager.Register(BT_Update, 200)` 确为 200ms |
| 5 | Flutter startOtaUpgrade 固定失败、机型/版本硬编码 | ✅ ota_service.dart:234-243 返回 false；ota_upgrade_page.dart:595-596 `igpsport-bsc300`/`0.0.0`；CI 注册型号 `e-track-at32f435`（firmware-build.yml:59），deviceModel 不匹配时 worker 直接返回无更新 |
| 6 | workflow 无 fw_header/.etu/patch/recovery/bspatch 自验 | ✅ firmware-build.yml 仅 objcopy bin/hex + sha256 + 上传（:135-161） |
| 7 | version_code=major*1000+minor 丢 patch 位 | ✅ firmware-build.yml:103-106，2.8.0 与 2.8.1 同为 2008 |
| 8 | workflow/CMake/vendor 未入库 | ✅ git status 显示 `.github/workflows/firmware-build.yml`、`CMakeLists.txt`、`cmake/`、`vendor/`、`MDK-ARM_F435/cmake-generated/` 全部 untracked，CI 干净 checkout 拿不到 |
| 9 | push 会注册 CF nightly，与方案 §6.1 冲突 | ✅ firmware-build.yml:169-171 `push` 即触发 register-cloudflare；PLAN-OTA.md:185 明文"不建 Release、不注册 CF" |
| 10 | D1 单资产模型、latest 单下载地址、无 currentImageSha/ready 门槛 | ✅ 0003_firmware_releases.sql:14-18（单组 file_name/sha256/r2_key）、:12（state 仅 candidate/disabled）；firmware.ts:10-16（查询参数无 currentImageSha）、:116（单 downloadUrl） |
| 11 | EEPROM 驱动无页边界/ACK polling/错误返回 | ✅ EEPROM.cpp 全文为 Wire 薄封装，WriteReg 忽略返回值，无读回验证 |
| 12 | QSPI 无超时死循环 | ✅ qspi_cmd_send:462 `while(...==RESET);` 忙等无超时，qspi_busy_check/qspi_set_qe_bit 同样 |
| 13 | LiveMap 静态 .sram_ext 大缓冲不随页面释放 | ✅ LiveMap.cpp:43-45 `snapshotBuf[256*320]`（RGB565 共 163,840B），静态分配 |

## 三、需修正的两处（原结论方向对、程度/位置不准）

### 修正 1：「未经验证的提交直接成为 APP 最新版」风险表述过重
CF 侧是**候选注册 + 渠道晋升**两段式：注册只写 `state='candidate'` 的 release 行，`/firmware/latest` 只返回 `firmware_channels.current_release_id` 指向的版本（firmware.ts:78），晋升在 admin 端人工完成。因此 nightly 注册**不会**直接变成 APP 可见最新版。原审查建议的"draft/candidate + 受保护人工晋升"机制上已经存在。真正的问题是方案文本与 workflow 行为二者矛盾（且 workflow 的 push 注册机制上跑不通，见补充 A/B），应二选一对齐，而非新增机制。

### 修正 2：「bspatch 要求完整 old/patch/new 内存数组」以偏概全
- **new 侧无需改**：`bspatch_patch` 支持 `new_data=NULL` 直写模式，经 1KB 分块回调 `bs_flash_write` 输出（interface.h:50、interface.c:72 chunked_bspatch、MCU_CONFIG_README.md:220-221），只需把回调实现成 QSPI candidate 写。
- **old 侧无需拷贝**：本项目旧镜像位于内部 flash 0x08010000，XIP 内存映射可随机读，`old_data` 直接传 flash 指针即可。**但参考集成文档示范的是 `bs_malloc(old_size)` 把整个旧固件读入 RAM（README:198-202），603KB 远超全部 RAM——P2 绝不能照抄该示例**。
- **真正必须改造的是 patch 输入侧**：`vfopen(patch_data, patch_size)`（interface.c:281）只包 RAM 缓冲，patch 存于 QSPI staging 且本驱动无内存映射读，需要 QSPI 流式 reader 适配。
结论方向（需要流式适配）正确，但工作量集中在 patch 读与 candidate 写两条 QSPI 通路，而非三个数组全部重写。

## 四、原审查遗漏的三处补充发现

### 补充 A（高危）：注册脚本硬编码 `isFormalRelease: true`，穿透 worker 防线
`build-firmware-release-metadata.mjs:55` 无条件写 `isFormalRelease: true`。worker 专门设置的 `FORMAL_RELEASE_REQUIRED` 拦截门（firmware.ts:157-159，方案 §6.1 也引用它作为"nightly 注册不可行"的依据）被 CI 侧硬编码绕过——nightly 会以"正式发布"身份注册进 D1。防线设计存在但已被自己人穿透。

### 补充 B（高危）：nightly 重复注册必然撞 UNIQUE，push 路径最多成功一次
push 构建的 version_code 恒定（当前 `VERSION_SOFTWARE="v2.7"` → 2007），而 D1 有 `UNIQUE(app_id, device_model, version_code)`（0003 migration:29）。第一次 push 注册成功后，第二次 push 起（release_tag 变、version_code 不变）INSERT 必然违反唯一约束，注册步骤失败、CI 变红。即：**现 workflow 的 push 自动注册不但违反方案，机制上也不可持续**。顺带：方案 §6.1 写 artifact 保留 14 天，workflow 实为 30 天（:161），对齐时一并处理。

### 补充 C（中危）：RAM 预算的分母与代码现状矛盾
方案 §1/§9 按"总 RAM 384KB、常态占用 82.96%、余 ~65KB"做预算，但代码证明芯片已用 EOPB0 扩展至 **512KB**：LiveMap.cpp:41 注释明言"低 384K 尾部 + EOPB0 扩展高 128K"，generated_linker.ld:12-13 划分 RAM 352KB + RW_IRAM2 160KB=512KB，且 RW_IRAM2 整区恰好被 snapshotBuf 占满（163,840B = 0x28000）。"65KB 余量"的口径（82.96% 基于哪个分母、是否含 .sram_ext）无法自洽，**P0 冻结前必须以当前真实 map 重算 RAM 基线**。另有方案未提的机会：升级独占页若把 `.sram_ext` 160KB 显式 overlay 复用为 OTA 缓冲（LZMA 字典/状态/bspatch 堆/I-O 合计 ~60KB 轻松容纳），预算压力可根除——但必须写入契约显式管理，不得隐式挪用。

### 补充 D（对原审查第 4 条的加重）：version_code 公式是方案内部矛盾，不止 CF 注册冲突
workflow 注释称该公式为"Q5 锁定规则"，而方案 §8-P0 要求"全局单调 version_code"、§4 的 MCU 端依赖 `target_vcode > cur_vcode` 拒绝。2.8.0→2.8.1 同为 2008 时，**MCU 会直接拒绝升级**（不仅是 CF 注册失败）。P0 必须重定义编码（如 major*10000+minor*100+patch，u32 足够）并同步 fw_header/.etu/CF/workflow 四处。当前两段式 "v2.7" 暂不触雷，三段式一出现即断。

## 五、对「Ed25519 提前到正式发布前」建议的处置：不采纳（v1）

- 方案 §0.2 已把"不防主动伪造"记录为**已接受的产品风险**，Ed25519 明确列入 v2 可选，这是八轮审查收敛后的既定决策；
- 仓库全局准则明确安全需求优先级最低、不为安全性分配开发资源；
- 该建议属于重新翻已定案决策，且原审查自己也承认这是完整性 vs 身份验证的定位差异。维持 v2 清单原位即可。

## 六、复审后的行动落点（并入 P0 清单）

1. **P0 新增前置项**：version_code 编码重定义（补充 D）；RAM 基线以真实 map 重算并决定是否契约化 `.sram_ext` overlay（补充 C）。
2. **workflow 对齐项**：push 分支删除 register-cloudflare 触发（回归方案 §6.1"仅 artifact"），或修订方案改走"候选注册+晋升"并修复 isFormalRelease 硬编码与 version_code 唯一冲突（补充 A/B）——二选一，不得维持现状。
3. **P2 注意项**：bspatch 集成禁止照抄 README 的 malloc(old_size) 模式；old 用 XIP 指针、new 用 QSPI 写回调、patch 走 QSPI 流式 reader（修正 2）。
4. 原审查其余阻断项与 P0-P5 顺序照单维持。
