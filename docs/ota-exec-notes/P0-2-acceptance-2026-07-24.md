# P0-2 独立验收记录

日期: 2026-07-24
验收人: Codex（非实现会话）
依据: `PLAN-OTA-EXEC.md` P0-2 卡内验收标准及冻结契约 `docs/ota-binary-contracts.md` §1

## 执行环境

- Python 3.13.12，`pycryptodome` 可用，vendor `bsdiff.exe` 可用。
- 测试夹具位于运行时临时目录 `C:/Users/SU/AppData/Local/Temp/E-Track-P0-2-acceptance-20260724`，未写入仓库。
- 差分 CLI 首次调用受沙箱对 Python 动态临时目录的权限限制；随后将 `TemporaryDirectory` 映射到固定授权夹具目录，仅重跑同一实现路径，未修改源码。

## 卡内标准

### 1. pack→unpack 往返

- 全量:
  `python Tools/etu_pack.py pack-full --app app-finalized.bin --out full-1.etu --target-vcode 20800`
  后执行 `python Tools/etu_unpack.py full-1.etu --out candidate-full.bin --verify-fw-header`，两者 rc=0，原镜像与 candidate SHA-256 均为
  `8569c5b70087bd6ed154dfe6e752961a36a2faeafc4a8281e34668baa0bf17f3`，逐字节一致。
- 差分:
  `pack-patch` 与 `unpack --old old.bin` 均 rc=0，candidate 与目标镜像逐字节一致，SHA-256 同为
  `8569c5b70087bd6ed154dfe6e752961a36a2faeafc4a8281e34668baa0bf17f3`。

### 2. 同输入两次打包 nonce 不同

对同一个 `app-finalized.bin` 执行两次 `pack-full`:

- `full-1.etu[16:32] = 7a11aeb119d1a06089d3dabe385315f1`
- `full-2.etu[16:32] = ec4d36aa749a4339ccf8b1558aaf7988`
- 结果: `nonce_different=True`。

### 3. 超限输入明确拒绝

使用 `983041 B (0xF0001)` 镜像，三个制包入口均返回 rc=1 并给出明确错误:

- `finalize`: `image_len 超 §0.5 上限 0xF0000`
- `pack-full`: `image_len=983041 超 960KB`
- `pack-patch`: `new image_len=983041 超 960KB`

## 契约阻断复核

夹具长度为 `12288 B`，在 `0x00..0x07` 放置可识别向量表哨兵，在 `0x400..0x45f` 放置 `0xa5` 占位头。执行:

`python Tools/etu_pack.py finalize --app app-placeholder.bin --out app-finalized.bin --ver-name 2.8.0 --build-ts 1760000000`

虽然工具返回 rc=0，独立按契约 `FW_HEADER_OFFSET=0x400` 检查结果为:

| 检查 | 结果 |
|---|---|
| `image[0x400:0x404]` | `a5a5a5a5`，不是 `ETFW` |
| 真实头 `0x400` 的 CRC32 | 不匹配，stored=`a5a5a5a5`，calc=`3cc1c001` |
| 真实头 `0x400` 的 SHA 双零法 | 不匹配 |
| `image[0:0x400]` 是否保持 | 否 |
| 错误位置 `0x00` 的头 | `ETFW`，CRC/SHA 自洽 |

源码对应位置为 `Tools/etu_pack.py:129,150,166`（`image[:FW_HEADER_SIZE]` / `full[:FW_HEADER_SIZE]`）以及 `Tools/etu_unpack.py:156`（`hdr = image[:FW_HEADER_SIZE]`）。文件虽定义了 `FW_HEADER_OFFSET = 0x400`，但 finalize 和 verify 未使用该偏移，导致自包自解测试可以通过，却会覆盖向量表并留下真实 fw_header 未初始化。

## 判定

不通过。P0-2 保持（打回）`进行中`，阻断原因是 finalize 与 verify 未遵守冻结的 `FW_HEADER_OFFSET=0x400` 布局契约。需要实现侧修正并由非实现会话重新验收；本次仅更新验收证据和日志，未修改 `Tools/etu_pack.py` 或 `Tools/etu_unpack.py`。
