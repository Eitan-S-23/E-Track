# P0-2 独立复验记录

日期: 2026-07-25
验收人: Codex（非实现会话）
依据: `PLAN-OTA-EXEC.md` P0-2 卡内验收标准及冻结契约 `docs/ota-binary-contracts.md` §1/§2

## 测试环境

- Python 3.13.12，`pycryptodome` 和 vendor `bsdiff.exe` 可用。
- 全部夹具位于 `C:/Users/SU/AppData/Local/Temp/E-Track-P0-2-reaccept-20260725`，未写入仓库。
- Windows 沙箱禁止 Python `TemporaryDirectory` 动态子目录写入；差分 pack 仅将该临时目录映射到固定授权夹具目录后执行，未修改工具代码，pack-patch 实现路径和 unpack CLI 均实际运行。

## 执行结果

### 1. finalize 与 `FW_HEADER_OFFSET`

使用 20480B 夹具，在 `0x00..0x3ff` 放置向量表哨兵，在 `0x400..0x45f` 放置 `0xa5` 占位头。`finalize` rc=0，独立复算结果:

- `image[0x400:0x404] = 45544657`（`ETFW`）。
- 真实头 CRC stored/calc 均为 `dfe44766`。
- 真实头 SHA 双零法通过，`image_len=20480`。
- `image[0:0x400]` 与 `image[0x460:]` 均与输入一致。
- `image[0:4] = 00000420`，向量表未被写成 `ETFW`。

### 2. pack→unpack 往返

- 全量 `pack-full`、`unpack --verify-fw-header` 均 rc=0，candidate 与目标逐字节一致。
- 差分 `pack-patch`、`unpack --old ... --verify-fw-header` 均 rc=0，candidate 与目标逐字节一致。
- 目标、全量 candidate、差分 candidate SHA-256 均为 `8ba6159ec6c8098a4f4048f99f2d3ddc34a8a5c1936cd4186dd23dfb06303e0e`。
- 独立复算 full 外层头 CRC 和 payload CRC 均通过。

### 3. nonce 随机性

同一目标镜像两次 `pack-full` 的外层头 nonce 为:

- `da1421f329ea0ba7896a41f5e372a8d2`
- `f22c5f7ac3d43fb423d6408b41f3449c`

两值不同，`NONCE_DIFFERENT=True`。

### 4. 超限与损坏拒绝

- `983041 B (0xF0001)` 输入的 `finalize`、`pack-full`、`pack-patch` 均 rc=1，并分别报告 image length 超限。
- `1119 B (0x45f)` 输入的 `finalize` rc=1，报告短于 `0x400+96`。
- 外层头 CRC 损坏的 `.etu`：unpack rc=1，报告 `header_crc32` 不匹配。
- payload 损坏的 `.etu`：unpack rc=1，报告 `payload_crc32` 不匹配。

## 判定

通过。P0-2 卡内三项验收标准及 `FW_HEADER_OFFSET=0x400` 冻结布局契约均满足，卡置 `完成`。本次未修改 `Tools/etu_pack.py` 或 `Tools/etu_unpack.py`，仅更新计划证据、会话日志和本复验记录。
