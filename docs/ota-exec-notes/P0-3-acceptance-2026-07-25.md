# P0-3 acceptance — 2026-07-25

验收人: Codex（非实现会话）

## 卡内命令

命令:

```text
python tests/ota-vectors/test_vectors.py
```

结果: `Ran 7 tests in 0.020s` / `OK`（7/7 通过；运行时仅有未设置 `OTA_AES_KEY` 的开发 key 警告）。

## 契约字段核对

按 `docs/ota-binary-contracts.md` §1.2、§2.1、§2.3 直接读取当前向量并复算：

1. `vectors.toy-old.bin.image_sha256` = `3081fa...`、`vectors.toy-new.bin.image_sha256` = `f68f35...`，分别等于整文件 SHA-256；契约 §1.2 的同名字段应等于 0x400 fw_header 的 SHA 双零值，实测分别为 `e025e0...`、`5b508e...`。同一 JSON 字段在 toy 与 .etu 条目中因此有两种语义，不能作为跨端契约字段。
2. §2.3 规范化 40B 内层头要求 `ph_lzma_props` 5B 和 `pad` 3B；`vectors.toy-patch.etu.patch_inner` 未提供这两个字段。
3. §2.1 64B 外层头要求 `magic`、`header_len`、`payload_crc32`；full/patch 两个向量的 expected 条目均未提供。

上述字段缺失/语义不一致，且现有单测未覆盖，故“expected.json 字段与契约文档一一对应”不成立。结论：**不通过，P0-3 保持 `进行中`**。

## 整改后复验

复验人: Codex（非实现会话） / 2026-07-25

卡内命令:

```text
python tests/ota-vectors/test_vectors.py
```

关键输出:

```text
Ran 9 tests in 0.015s
OK
```

运行时仅有未设置 `OTA_AES_KEY`、使用 vendor 开发 key 的预期警告；`expected.json.aes_key_source` 已明确记录该口径。

另以原始字节直接解析并复算，不依赖 `etu_unpack.parse_etu_header` / `parse_patch_header`，结果:

```text
RAW_CONTRACT_AUDIT_OK
fw_header_fields=12 outer_header_fields=15 patch_inner_fields=9
toy_new_fw_image_sha256=5b508eea3c3604ef42b5895d44b1df540a21e910bd00b184ff31ab80f0c824df
full_package_sha256=d8e26e51cf574570d69842b6dcc926c7becb2f050a2f996702c1075fc1617bfc
patch_package_sha256=bf1ac6c9708110b4c100b62e7d735e493a22c2a6e89cd24594427ef80663eb6e
```

复核结论:

1. toy 整文件 SHA 已独立为 `file_sha256`；契约字段 `fw_header.image_sha256` 与 full/patch 向量的 `image_sha256` 均统一为 §1.2 双零法值。
2. §1.1 fw_header 12 字段、§2.1 outer_header 15 字段、§2.3 patch_inner 9 字段均完整存在并与原始字节逐项一致。
3. 外层 `payload_crc32`、`header_crc32`、内层 `ph_hcrc`、fw_header `header_crc32` 均独立复算一致；端序、5B `ph_lzma_props`、3B 零 `pad` 与 18B `0xFF` pad 均符合契约。
4. 全量/差分往返、seq 回绕/相等/单坏/双坏和契约 §8 数值样例回归均由 9 项单测覆盖并通过。

结论：**整改复验通过，P0-3 可置 `完成`**。

---

## 主会话独立复核确认（2026-07-25）

验收人: 主会话(Claude，非实现侧独立复核)

### 卡内命令

```text
python tests/ota-vectors/test_vectors.py
```

关键输出:

```text
Ran 9 tests in 0.015s
OK
```

运行时仅有未设置 `OTA_AES_KEY`、使用 vendor 开发 key 的预期警告。

### 产物哈希抽查

| 文件 | size | sha256[:24] |
|---|---:|---|
| toy-old.bin | 4096 | 3081fa0afc5bb2f3a7d456a2 |
| toy-new.bin | 4096 | f68f357c708c2d65e6b15476 |
| toy-full.etu | 748 | d8e26e51cf574570d69842b6 |
| toy-patch.etu | 213 | bf1ac6c9708110b4c100b62e |
| expected.json | 4354 | db41f34b634f081d45e69b11 |
| gen_vectors.py | 14936 | 7e28c716e0bfcd15236022bf |
| test_vectors.py | 15288 | 6f3c568163f74d5cc7566686 |

与看板证据栏一致。

### 独立原始字节审计

- `fw_header_offset=0x400` / `fw_header_size=96`
- 字段集合完整: fw_header=12、outer_header=15、patch_inner=9
- toy 根字段仅 `file_sha256`（整文件 SHA）；契约 `fw_header.image_sha256` 与 full/patch `image_sha256` 统一为双零法值 `5b508eea3c3604ef42b5895d44b1df540a21e910bd00b184ff31ab80f0c824df`
- full flags=`0x000B`、patch flags=`0x0007`；外层 header_crc32/payload_crc32 复算通过
- patch 内层 `ph_lzma_props=0200100000`、`pad=000000`；`ph_hcrc` 置零重算=`f21b9bb4`；`ph_ocrc/ph_ncrc` 分别等于 old/new 整文件 CRC32
- `base_sha8=3081fa0afc5bb2f3` = sha256(toy-old.bin) 前 8B
- full/patch `etu_unpack --verify-fw-header` 往返 candidate 均与 `toy-new.bin` 逐字节一致
- seq 四场景 A_newer / B_wrap_newer / equal_both_valid / only_B_valid 与 expected 一致

输出标记: `RAW_CONTRACT_AUDIT_OK`

### 判定

通过。P0-3 卡内两项验收标准（单测绿；expected.json 字段与契约一一对应）均满足，卡保持 `完成`。本复核未修改 `tests/ota-vectors/**` 实现代码。
