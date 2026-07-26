# P0-3 research — golden vectors 设计（编码前落盘）

认领: Claude(实现 agent) / 2026-07-25
输入契约: `docs/ota-binary-contracts.md` v1.0（已冻结）；P0-2 打包器 `tools/etu_pack.py`/`etu_unpack.py`（已验收通过）。
产物: `tests/ota-vectors/{toy-old.bin,toy-new.bin,toy-full.etu,toy-patch.etu,expected.json,gen_vectors.py,test_vectors.py}`（新建）。

## 1. 卡内验收清单（对号 PLAN-OTA-EXEC.md P0-3 目标）

- toy-old.bin / toy-new.bin（≈4KB，卡内要求 4KB）。
- toy-patch.etu（差分）、toy-full.etu（全量）。
- expected.json：含 SHA + 关键字段，字段与契约文档一一对应。
- 打包器侧单测跑通：pack→unpack 往返字节一致 + expected.json 字段比对。
- 向量覆盖 seq 回绕 / 相等仲裁场景（§8 验收）——这是 BCB §3.2 seq 仲裁规则。
- 为 P2 MCU 解析与 P3 Flutter 解析预留同一套向量（字段以契约命名稳定，便于跨语言复用）。

## 2. design — golden vectors 结构

### 2.1 toy 二进制

- `toy-old.bin`：4096B。前 0x400 为向量表哨兵区（`DEAD0000..` à la P0-2 验收夹具，确保 finalize 不覆盖 0..0x3ff），0x400..0x45F 占位 0xFF（finalize 前的状态由 P0-2 finalize 回填），0x460..0xFFF 为简单填充（`0x10*i` pattern）。
- `toy-new.bin`：4096B。在 toy-old 基础上做约 200 处 `+1` 改动，确保差分包有真实 diff 内容（bsdiff 实际能产出有意义 LZMA 流，与 P0-2 §5.4 的 toy-new/toy-old 一致风格）。

为 P0-2 已通过验收的 `BUILD_FW_HEADER` 在镜像 0x400 处回填，二者都需走 `etu_pack.py finalize`：
- `toy-old.bin`（旧版，正式基版）：finalize `--ver-name 2.7.0 --build-ts 1720000000`（vcode=20700）。
- `toy-new.bin`（目标版）：finalize `--ver-name 2.8.0 --build-ts 1721000000`（vcode=20800）。

### 2.2 .etu 包

由 `etu_pack.py` 直接生成（复用已验收工具，不重复实现打包逻辑）：
- `toy-full.etu`：`pack-full --app toy-new.bin --ver-name 2.8.0` → flags=0x000B。
- `toy-patch.etu`：`pack-patch --old toy-old.bin --new toy-new.bin --ver-name 2.8.0 --base-ver-name 2.7.0` → flags=0x0007，base_sha8=SHA(old)[:8]。

每包记录：包 sha256（即 §4.2.1 package_sha256）、image_sha256、header_crc32、aes_nonce、payload_len、target_vcode、base_vcode、flags、key_id、base_sha8。

## 3. expected.json schema（字段名与契约文档对齐）

```json
{
  "contract_version": "ota-binary-contracts v1.0",
  "generated_at": "<ISO>",
  "aes_key_source": "OTA_AES_KEY env or vendor default (dev only)",
  "fw_header_offset": 1024,
  "fw_header_size": 96,
  "vectors": {
    "toy-old.bin": {
      "size": 4096,
      "version_name": "2.7.0",
      "version_code": 20700,
      "build_ts": 1720000000,
      "image_sha256": "<hex>",
      "fw_header_crc32": "<hex8>",
      "fw_header_magic": "45544657"
    },
    "toy-new.bin": {...v2.8.0/20800/1721000000...},
    "toy-full.etu": {
      "size": <N>,
      "package_sha256": "<整包 SHA-256，= §4.2.1>",
      "header_crc32": "<hex8>",
      "flags": "000b",
      "alg_id": 1,
      "key_id": 1,
      "target_vcode": 20800,
      "base_vcode": 0,
      "hw_rev": 1,
      "layout_id": 1,
      "min_boot_ver": 1,
      "base_sha8": "0000000000000000",
      "payload_len": <N>,
      "aes_nonce": "<32 hex>",
      "image_sha256": "<= toy-new image_sha256>"
    },
    "toy-patch.etu": {
      "size": <N>,
      "package_sha256": "...",
      "header_crc32": "...",
      "flags": "0007",
      "alg_id": 1,
      "key_id": 1,
      "target_vcode": 20800,
      "base_vcode": 20700,
      "hw_rev": 1,
      "layout_id": 1,
      "min_boot_ver": 1,
      "base_sha8": "<SHA(toy-old)[:8]>",
      "payload_len": <N>,
      "aes_nonce": "...",
      "image_sha256": "<= toy-new image_sha256>",
      "patch_inner": {
        "ph_hcrc": "<hex8 BE>",
        "ph_psize": <N>,
        "ph_osize": 4096,
        "ph_nsize": 4096,
        "ph_ocrc": "<hex8 BE = crc32(toy-old)>",
        "ph_ncrc": "<hex8 BE = crc32(toy-new)>",
        "ph_original_size": <N>
      }
    }
  },
  "seq_arbiter_cases": [
    {"name": "A_newer", "a_seq": 5, "b_seq": 3, "expect": "A"},
    {"name": "B_newer", "a_seq": 1, "b_seq": 65000, "expect": "B"},
    {"name": "equal_both_valid", "a_seq": 7, "b_seq": 7, "expect": "A"}
  ]
}
```

字段说明：所有 hex 字段串都在 expected.json 中以"字节序小写 hex"记录（与契约 §8 样例风格一致）；BE 字段（ph_hcrc/psize/ocrc/ncrc、base_sha8 在文档语义层面 BE-CRC 但 base_sha8 是 SHA 前 8B 原始字节）按"片上字节 hex"给出，便于跨语言比对。

## 4. seq 仲裁场景（§8 验收 / 契约 §3.2）

契约 §3.2：`(int16)(a.seq - b.seq) > 0` 者 A 新；相等且双合法取 A。

P0-3 在 vectors 单测中以**纯 Python seq 仲裁函数** `arbiter_pick(a_seq, b_seq, a_valid, b_valid)` 验证三类场景（不写真 EEPROM，P0-4 的活）：
- **A 新**：a=5,b=3 → 选 A。
- **B 新（含回绕）**:a=1,b=65000 → `(int16)(1-65000) = (int16)(-64999)`。注意 65000 在 u16 范围内；`1-65000=-64999`;`-64999 & 0xFFFF = 0x0139 = 313`? 错。重算：65000 = 0xFDE8;1-0xFDE8 = 1-65000 = -64999;`-64999 mod 65536 = 537`;`(int16)537 = 537 > 0`?这意味着 a-b 经 int16 转换后会得到正数。

  正确语义：`(int16)((uint16)a - (uint16)b)`。`(uint16)1 - (uint16)65000 = (uint16)1 - (uint16)65000`，Python 中 `1-65000 = -64999`;`(uint16)(-64999)` = `(-64999) & 0xFFFF` = `537`;`(int16)537` = 537，>0 → 选 A。**这反而表示 A 新**——因为 u16 回绕下，b=65000 视为 "比 1 早 1537"，所以 A 更新。

  要构造"B 新"回绕场景:让 b 在回绕意义上更新，即 a 在"很旧"位置而 b 刚回绕回小值但更新于 a 之后：
  - 例 a=65530,b=5：`(uint16)65530-(uint16)5 = 65525`;`(int16)65525 = -11 < 0` → B 新。✅
  - 例 a=65535,b=0：`(uint16)65535-(uint16)0=65535`;`(int16)65535=-1<0` → B 新。✅

  所以采用：
  - `B_wrap_newer`: a=65530, b=5 → expect B。
- **相等且双合法**:a=7,b=7 → 选 A。

- 补一例 **单合法**:a_invalid+b_valid → 选 B（无 seq 参与，直接选有效者，契约 §3.2 第 3 条）。

## 5. 打包器侧单测设计（test_vectors.py）

复用 P0-2 etu_unpack.py 的解析函数（不重写解析，确保与契约一致）。断言：

1. 字节比对：`etu_unpack` 解出的 candidate 与 `toy-new.bin` `cmp` 一致（全量）。
2. 差分：`etu_unpack --old toy-old.bin toy-patch.etu` 解出的 candidate 与 `toy-new.bin` `cmp` 一致。
3. `expected.json` 所有字段与 `etu_unpack` 实解析值逐字段相等（package_sha256、header_crc32、flags、target_vcode、base_vcode、base_sha8、payload_len、aes_nonce、image_sha256、ph_* 全字段）。
4. `toy-old.bin` / `toy-new.bin` 的 fw_header（0x400 处）按 `etu_pack.build_fw_header` 规则可复算 image_sha256 双零法 + header_crc32，与 expected.json 一致。
5. seq 仲裁函数 4 个 case 全过。
6. 数值样例契约交叉校验：直接比对 P0-2 已经过验收的 `contract §8.2 全量外层头 CRC=0x14D0AA63` / `§8.5 ETRJ CRC=0xC0178C87`，作为 contracts.py 与 etu_pack.py CRC 实现一致的回归（防止 pycryptodome/lzma 升级或环境漂移使 P0-2 通过的手段退步）。

## 6. 风险/红线

- **只读契约**: 不改 `docs/ota-binary-contracts.md` / `PLAN-OTA.md`；发现矛盾走 §9 阻塞。
- **复用 P0-2 工具**：golden vectors 不重写打包/解包；只在生成与测试里 `import` 或 `subprocess` 调用 `tools/etu_pack.py` / `tools/etu_unpack.py`。若 envelope 字段补齐（如内层头 40B 解析）需走 etu_unpack.py 内部函数 `parse_patch_header`——已存在，直接复用。
- **AES key 一致性**: gen_vectors 与 test_vectors 都不显式设 OTA_AES_KEY，默认用 vendor 示例 key（开发用，契约 §0.6 开发允许）。expected.json 记录 key_source 字段。
- **不 commit/push**（OTA 规约 §5）。
- **不自验收置完成**：留非实现会话验收。
- **为 P2/P3 预留**: expected.json 字段名与契约文档术语严格对齐；解析比对以 etu_unpack.py 为单一真实源，P2 MCU / P3 Flutter 各自实现解析后应能对同一 expected.json 跑过（这是"预留同一套向量"的语义）。
