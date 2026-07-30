# P2-2 .etu 全量包解析与流式解包研究

- 日期: 2026-07-29
- 实现会话: Codex
- 状态: 编码前研究与设计冻结，待实现、真机取证和独立验收

## 1. 任务边界

P2-2 仅实现 `.etu` 全量包路径，接受冻结组合 `flags=0x000B`：

1. 逐字段解析 64B 外层头，禁止结构体覆盖或 `memcpy` 到宿主结构。
2. 按契约顺序校验头 CRC、flags、算法/key、设备身份、版本、长度和密文 payload CRC。
3. 使用 AES-128-CTR 解密，nonce 作为大端 128 位计数器并从末字节递增。
4. 解析 LZMA-Alone 的 5B properties 与 u64 LE 输出长度，流式解码并直接写 candidate。
5. 对每次 `offset + len` 做溢出安全边界检查，输出不得超过 `OTA_APP_LENGTH`。
6. 复用 Boot 的 fw_header 校验器完成 header CRC、SHA 双零法、设备身份和 boot 版本终验，并额外要求 fw_header vcode/image_len 与外层头/实际输出一致。P0-3 toy 向量的前 8B 是刻意的哨兵而非可启动向量，因此 App 内容终验不检查 MSP/Reset_Handler；Boot 搬运前仍通过原入口执行完整向量校验。

差分 `flags=0x0007` 明确返回“不支持”，留给 P2-3。P2-2 不写 ETSL commit marker、不写 BCB、不进入 STAGED；candidate 槽头在首次输出前失效化，后续提交属于 P2-5。

## 2. 权威输入与实测资产

- 字段、端序、CRC、上限和校验顺序：`docs/ota-binary-contracts.md` §0、§1、§2、§4、§10。
- 卡片目标：`PLAN-OTA-EXEC.md` P2-2。
- golden package：`tests/ota-vectors/toy-full.etu`，748B，SHA-256 `d8e26e51cf574570d69842b6dcc926c7becb2f050a2f996702c1075fc1617bfc`。
- golden output：`tests/ota-vectors/toy-new.bin`，4096B，文件 SHA-256 `f68f357c708c2d65e6b1547648e955ea47949d81bd52f2cded684a8f640e21c3`。
- fw_header 双零 SHA：`5b508eea3c3604ef42b5895d44b1df540a21e910bd00b184ff31ab80f0c824df`。
- toy-full 外层头：payload_len=684，payload CRC=`0xB8D54B65`，target_vcode=20800。
- 解密后的 LZMA-Alone 前 13B：`02004000000010000000000000`，即 `lc=2/lp=0/pb=0`、dict=16384、output=4096。

## 3. 复用与适配结论

### 3.1 AES-CTR

复用 `bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c` 的 AES-128 key expansion 和单块加密。vendor `AES_CTR_decrypt()` 在每次调用末尾丢弃不足 16B 的剩余 keystream，不适合作任意分块流式入口，因此 P2-2 在其上封装持久化 counter、keystream 和 byte index；counter 与 Python packer 一致，从 byte 15 向 byte 0 进位。

### 3.2 LZMA

复用 7-Zip `LzmaDec.c/.h`。使用 `LzmaDec_DecodeToBuf()`，4KiB 密文输入缓冲原地解密，1KiB 输出缓冲写 candidate。自定义 `ISzAlloc` 只从 40KiB 固定 arena 线性分配，不支持主堆回退。properties 必须满足冻结的 `lc=2/lp=0/pb=0`，dictionary 介于 4KiB 与 16KiB，避免概率表或字典突破 P0-6 预算。

### 3.3 fw_header 与散列

App target 复用 `boot_crc32.c`、`boot_sha256.c`、`boot_fw_header.c`，避免再实现一套 CRC/SHA/fw_header 口径。共享校验器增加显式 flags：Boot 旧入口固定启用向量检查，P2-2 App 内容终验只关闭该项，其余 header/SHA/身份检查完全同源。外层 payload CRC 使用同一增量 CRC API；candidate 终验通过 callback reader 读取 QSPI payload。

## 4. API 与失败原子性

portable core 使用 callback I/O：package read、candidate prepare/program/read、workspace acquire/release。调用顺序冻结为：

1. 读取并逐字段校验外层头。
2. 完整流式计算密文 payload CRC；此阶段不得擦写 candidate。
3. 取得 40KiB OTA workspace；失败仍不得擦写 candidate。
4. 解密前 13B，检查 properties 与输出长度。
5. `candidate_prepare(image_len)` 先擦 candidate 槽头，再擦覆盖镜像的 payload 扇区。
6. LZMA 每产出最多 1KiB，先做安全范围检查，再 program，并立即 readback 比对。
7. 全镜像 fw_header 终验；成功仅返回经过验证的 metadata，不提交 ETSL/BCB。
8. 所有出口清零 key、counter、LZMA 状态与工作区后 release。

坏外层头、错误身份、降级、长度或 payload CRC 必须在 candidate prepare 前拒绝。解密/解压/flash/fw_header 后期错误允许 candidate 留下无 commit marker 的半成品，但 BCB 必须逐字节不变。

## 5. Overlay 与链接设计

P0-6 已冻结 `[0x20058000,0x20080000)` 为 LiveMap/OTA 互斥物理区，OTA 固定池上限 40960B。实现增加 `.ota_overlay` 40KiB `NOLOAD` section，与 `.sram_ext` 使用相同 VMA；GCC linker 与 AC5 scatter 均必须在 map 中显示同址且各自不超过物理区，不能把两个 section 顺序摆放。

P2-2 提供 owner/acquire/release 基础接口。当前卡只接入生产 HAL 和 evidence harness；真正停止 LVGL、卸载 LiveMap、失败后重建页面的 UI 生命周期由后续 FirmwareUpdate 页面接入时调用，未满足前置条件时 acquire 必须失败。

## 6. 测试与真机证据计划

宿主测试使用同一 C core、AES 和 LZMA decoder：

- toy-full 逐字节还原 toy-new；验证文件 SHA、fw_header 双零 SHA、vcode、长度。
- 外层 magic/header_len/header CRC/flags/alg/key/hw/layout/min_boot/version/base 字段/包长/payload CRC 的有序拒绝。
- LZMA properties、dictionary、u64 输出长度、密文流损坏、flash prepare/program/readback 和 workspace 失败。
- 每个失败样本断言 BCB 哨兵区不变；core API 不暴露 BCB callback。
- candidate 写入前拒绝类断言 prepare/program 调用数为零；所有写入 offset/len 均在净槽边界。

真机 evidence build 通过保留 RAM 控制区接收 748B golden package，运行同一 core 写 QSPI candidate，并由 J-Link 串行读取结果、candidate 4KiB 与 BCB 前后摘要。所有 Commander/logger/viewer 严格串行；取证后恢复生产 Boot/App、验证当前 map RTT 地址与 `SEGGER RTT` 签名并清理进程。

## 7. 红线

- 不修改 `PLAN-OTA.md` 或 `docs/ota-binary-contracts.md`。
- 不使用 struct memcpy 解析任何 wire format。
- 不分配完整 `.etu`、完整明文或完整 candidate。
- 不使用无界 malloc/new，不让固定 arena spill 到主 RAM。
- 不写 BCB，不提交 candidate ETSL marker。
- 不把 P2-3 差分处理混入本卡。
- 不并行启动任何 J-Link 命令。
