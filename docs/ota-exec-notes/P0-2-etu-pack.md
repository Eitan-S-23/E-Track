# P0-2 research — 打包/解包工具实现口径（编码前落盘）

认领: Claude(实现 agent) / 2026-07-24
输入契约: `docs/ota-binary-contracts.md` v1.0（P0-1 已冻结）;`bsdiff_lzma_AES128-main/` + DRAFT 四坑。
产物: `tools/etu_pack.py`、`tools/etu_unpack.py`（新建）。

## 1. 契约要点回号（编码依据,逐条对契约文档锚点）

- fw_header 96B(§1.1):off0 magic "ETFW";off8 version_code(`major*10000+minor*100+patch` u32 LE);off12 version_name(16B ASCIIZ 0-pad);off28 build_ts(u32 LE UNIX 秒);off32 hw_rev=1;off36 image_len(含头,上限 0xF0000);off40 image_sha256(32B);off72 layout_id=1;off73 min_boot_ver=1;off74 pad 18B 0xFF;off92 header_crc32(CRC32-IEEE 覆盖 off 0..91 前 92B, LE 存储)。
- SHA 双零法(§1.2):image_sha256 计算时 off40..71 与 off92..95 全按 0 参与全镜像 SHA-256。制包序:占位头→填 ver/ts/len/layout/min_boot→算 SHA 回填 off40→最后算前 92B CRC 回填 off92。
- .etu 外层头 64B(§2.1):off0 magic "ETU1";off4 header_len=64(u16 LE);off6 flags(u16 LE,全量=0x000B=bit0 AES+bit1 LZMA+bit3 全量;差分=0x0007=bit0+bit1+bit2,bit2/bit3 互斥必居其一);off8 alg_id=1 u32 LE;off12 key_id=1 u32 LE;off16 aes_nonce 16B **每包随机**;off32 payload_len u32 LE(off64 起 payload 字节);off36 payload_crc32(CRC32 覆盖**加密后** payload);off40 target_vcode u32 LE;off44 base_vcode u32 LE(全量=0);off48 hw_rev=1 u16 LE;off50 layout_id=1 u8;off51 min_boot_ver=1 u8;off52 base_sha8 8B(差分=基版 SHA-256 前 8B;全量全 0);off60 header_crc32(CRC32 覆盖前 60B, LE 存储)。
- payload 两种形态(§2.2):全量明文=5B LZMA props + u64 LE 原始长度 + LZMA 流(即标准 LZMA-Alone `.lzma` 形态);差分明文=40B 规范化内层头(§2.3)+ LZMA 流(为 bsdiff 控制/数据流的 LZMA 压缩)。上限:字典 16KB（CI 制包固定;但差分用 bsdiff.exe 默认 4KB）。
- 40B 规范化内层头(§2.3):off0 ph_hcrc BE(CRC32 覆盖规范化 40B 全头,本字段 off0..3 置零参与);off4 ph_psize BE(差分包 LZMA 流字节,= payload_len - 40);off8 ph_osize LE(基版镜像字节);off12 ph_nsize LE(目标镜像字节);off16 ph_ocrc BE(基版内容 CRC32);off20 ph_ncrc BE(合成后 candidate CRC32);off24 ph_lzma_props 原始 5B;off29 pad 显式 0x00×3;off32 ph_original_size u64 LE(LZMA 解压后 bsdiff 流长度)。
- CRC(§0.2):CRC32-IEEE 反射 0xEDB88320 初值 0xFFFFFFFF 出 0xFFFFFFFF(= zlib/binascii.crc32 & 0xFFFFFFFF;与 vendor `bsdiff/lib/crc32.c` 表逐项一致)。存储端序:除 BE 字段外全 LE。
- 三处上限(§0.5):.etu 包总长 ≤0x180000(1.5MB);image_len ≤0xF0000(960KB);staging 512 块(隐含包总长 ≤2MB-4KB=0x1FF000,但外层头未强制 second check,契约只列前两条 + 512 块=包尾块数语义)。制包端拒超限。
- version_code(§0.6,PRE-1):`major*10000+minor*100+patch`;minor/patch∈0..99;nightly 去后缀编码。降级拒绝在 MCU 侧,制包侧只写正确 value。

## 2. bsdiff 工具链实测（2026-07-24 实跑确认,锚 DRAFT）

实测印证（与本卡契约完全自洽,DRAFT 第 8 行 36B 描述已作废,真实 patch_header_t=40B）:

- `bsdiff.exe old.bin new.bin patch.bin -aes 0` 实产 40B 原生头 + LZMA 流。
- 原生头字节布局(C struct,8B 对齐):
  - off0 hcrc 大端(BE)= BigtoLittle32(crc32(40B 全头 with hcrc=0));
  - off4 psize BE = LZMA 压缩流字节数;
  - off8 osize LE = 旧文件字节;off12 nsize LE = 新文件字节;
  - off16 ocrc BE = crc32(old);off20 ncrc BE = crc32(new);
  - off24 props[5](原样 LZMA props);off27..29 自然 3B ABI 对齐填充(可能不是 0,需规范化);
  - off32 ph_original_size u64 LE = bsdiff 未压缩差分流字节。
- hcrc 校验:用 0 替换 off0..3 算 CRC32(version 端序无关),取 BE 即匹配字段字节。

四坑(DRAFT §290-)→ 本工具处置:
1. PC 工具 exit code 恒 0 → `etu_pack.py` 在 `-aes 0` 产出后**自验**:把 patch 原料反向 bspatch 比对? 不,工具侧只做规范化头重写 + 自检 hcrc;P0-3 golden vectors 才在工具侧单测跑 pack→unpack 往返(本卡验收命令之一)。CI 制包(`--ci`)target 自链由 P4-1 走;本卡只保证 pack→unpack 往返字节一致。
2. 36B 头无补丁体自身 CRC → 契约 ph_ncrc BE 二重兜底 + candidate 全镜像 SHA 双零复核;打包端写真实 ph_ocrc/ph_ncrc。
3. PC bspatch 靠文件名 `_encrypt` 判断解密 → 与本工具无关(本工具直接构造 .etu,不走 bspatch.exe 文件名嗅探);unpack 用 Python 自解。
4. AES key 硬编码教科书 key → 默认值同 vendor(`2b7e1516...`)仅开发;生产 env `OTA_AES_KEY` 32 hex chars 注入;key_id=1。

## 3. AES-CTR 实现（与 vendor 工具链字节对齐）

- vendor `Aes128_Ctr`(bsdiff/main.c:251):nonce_counter = 12B 随机 + 4B counter=0;AES-128-CTR,块递增 counter(后 4B 大端?实测 C 实现 SmallCounter inc 是 LE 16 进制)。
- 关键:vendor `_encrypt` 文件布局 = 前 16B nonce_counter + 密文。但 .etu 契约 §2.1 把 16B aes_nonce 放**外层头**,payload 全是密文(无 nonce 前缀)。即打包器**不复用** vendor 的 `_encrypt.bin` 包装,自管 AES-CTR:nonce 16B 放外层头,counter 起始=nonce 自身(treat whole 16B as IV)。
- vendor `AES_CTR_encrypt/decrypt` 内部:每 16B 块加密 (counter)→XOR 明文→counter+1(native 字节序? 解密侧 `AES_CTR_decrypt` 同 increment)。为保证 Python CTR 与 vendor 互校可用,本工具默认 key 与 początk counter 字节序说明见注释;真实三轮互校 = pack 的 payload 经 unpack 自解能还原明文(自洽),vendor 兼容性由 P0-3/P2 验证。本卡验收仅要求 pack→unpack Python 自包自解字节一致。
- AES 库:`pycryptodome` `AES.new(key, AES.MODE_CTR, initial_value=nonce, nonce=b'')`(需测试 pycryptodome CTR IV 取 16B 全 nonce 行为);若无 pycryptodome,fallback 用 `cryptography`。优先 pycryptodome(`pip` 更轻)。
- LZMA-Alone 全量:用 `lzma` 模块 `FORMAT_ALONE`(Python 3.13+ 可能移除;fallback 用 `pylzma` 不便)。决定:**全量明文 LZMA-Alone 形态(5B props+u64 LE+流)直接用 `pylzma` 不行**;Python `lzma` 标准库 `LZMACompressor(format=lzma.FORMAT_RAW, filters=[{id: lzma.FILTER_LZMA1, ...}])` 产的是 raw 流,需手动拼 5B props + u64 + 流。props 用 `LzmaCompressor`?用 `lzma.FORMAT_ALONE` 最简:Python 3 仍支持 `lzma.LZMACompressor(format=lzma.FORMAT_ALONE)` 产出 .lzma 文件(5B props + 8B size + 流),正好匹配契约 §2.2 全量明文形态。决定全量用 `lzma.FORMAT_ALONE`。
- 差分 LZMA:bsdiff.exe 已用其自带 LZMA 产压缩流(4KB dict),`etu_pack.py` **不重压**,直接复用 bsdiff.exe 产物的 LZMA 流字节 + 重写规范化头。即差分流程:调用 `bsdiff.exe` 产 40B 头+流 → 解析原生头 → 用规范化 40B 头 + 同一段 LZMA 流作为 payload 明文。MCU 解 bspatch 时需 props(规范化头保留 vendor 原始 props[5])。

## 4. CLI 设计

`etu_pack.py`:
- `etu_pack.py finalize --app APP_BIN --out APP_BIN` 原地回填 fw_header(SHA 双零 + CRC)。参数:--ver-name, --build-ts, --hw-rev=1, --layout-id=1, --min-boot=1, --image-len(auto=len)。
- `etu_pack.py pack-full --app APP_BIN --out FULL.etu --target-vcode N --base-vcode 0 --key-hex|env OTA_AES_KEY` AES-CTR + LZMA-Alone + 外层头。
- `etu_pack.py pack-patch --old OLD.bin --new NEW.bin --out PATCH.etu --target-vcode N --base-vcode N --base-sha8 (auto from old) --bsdiff-exe PATH --key-hex|env`
- `--ci` 模式:dict=16KB,复用 P4-1。
- 超 .etu 1.5MB / image_len 960KB 立即 exit 1 + 明确 stderr。

`etu_unpack.py`:
- `etu_unpack.py unpack IN.etu --out candidate.bin [--old OLD.bin for patch]` 解外层头→CRC→AES 解密→(全量 LZMA-Alone 解压 / 差分需 old + bspatch)→candidate;再复核 candidate 全镜像 SHA 双零对应 fw_header.image_sha256? 不,unpack 复核 = ph_ncrc(差分) 或 candidate crc 全量,以及 fw_header.header_crc32。
- 不自验升级合法性(那是 MCU/App 的事),只做"逆向解析+校验,供三方比对"。

## 5. 验收命令与执行结果（2026-07-24 实跑）

### 5.1 产物

| 路径 | 大小 | mtime | sha256[:16] |
|---|---|---|---|
| `tools/etu_pack.py` | 18475B | 2026-07-24 23:10:08 | 60034884b7ff6e89 |
| `tools/etu_unpack.py` | 17358B | 2026-07-24 23:11:20 | 1cc363894e5a717b |

### 5.2 契约 §8 样例 CRC 交叉校验（实现侧与契约文档一致）

- §8.2 全量外层头(60B)=`4554553140000b0001000000010000000000000000000000000000000000000064000000111111114051000000000000010001010000000000000000` → `zlib.crc32`=**0x14D0AA63** ✅ (=契约)
- §8.5 ETRJ(40B=ETRJ+32B0+u32 LE 100) → **0xC0178C87** ✅ (=契约)
- §1.1 fw_header §8.1 样例 `header_crc32=0xFE1DCBD1` 已在 P0-1 验收通过,本卡 finalize 输出格式与之一致(本卡实跑 build_ts=1720000000 → hdr CRC=0x0cb91a45,自洽)。

### 5.3 finalize + 全量 pack→unpack 往返

```
toy header(96B ETFW+0xFF pad)+toy-new 4096B → app-placehold.bin 4192B
python tools/etu_pack.py finalize --app /tmp/ota2/app-placehold.bin --out /tmp/ota2/app-finalized.bin --ver-name 2.8.0 --build-ts 1720000000
  → image_len=4192 vcode=20800 image_sha256=e9ed5739221d7a704c6b74c73f6b3680b1099db270075c9a72ab35704384b9cd header_crc32=0x0cb91a45
python tools/etu_pack.py pack-full --app /tmp/ota2/app-finalized.bin --out /tmp/ota2/full.etu --ver-name 2.8.0
  → app_len=4192 payload_len=719 etu_total=783 flags=0x000b aes_nonce=7ead3888b11ed1a70b2e056dcdf83efa header_crc32=0xa8f0b959
python tools/etu_unpack.py /tmp/ota2/full.etu --out /tmp/ota2/cand-full.bin --verify-fw-header
  → candidate_len=4192 image_sha256=e9ed5739221d7a704c6b74c73f6b3680b1099db270075c9a72ab35704384b9cd (与 finalize 输出一致)
cmp /tmp/ota2/app-finalized.bin /tmp/ota2/cand-full.bin
  → ROUNDTRIP_FULL_OK  ✅
```

### 5.4 差分 pack→unpack 往返

```
toy-old.bin 4KB / toy-new.bin 4KB(200 处 ±1)
python tools/etu_pack.py pack-patch --old /tmp/ota2/toy-old.bin --new /tmp/ota2/toy-new.bin --out /tmp/ota2/patch.etu --ver-name 2.8.0 --base-ver-name 2.7.0
  → old_len=4096 new_len=4096 payload_len=327 etu_total=391 flags=0x0007 target_vcode=20800 base_vcode=20700
    base_sha8=c8f5d0341d54d951 aes_nonce=96092bed4f777a6a7cb29965ea8aabd8
    new_sha256=a47d58b237e294c206a09e57ee4442feccf5ae0fe3673c63ba22ba43eaf5f752 header_crc32=0x4ca1ffcb
python tools/etu_unpack.py /tmp/ota2/patch.etu --out /tmp/ota2/cand-patch.bin --old /tmp/ota2/toy-old.bin
  → candidate_len=4096 base_sha8(etu)=c8f5d0341d54d951 old_sha8=c8f5d0341d54d951 (一致)
    candidate_sha256=a47d58b237e294c206a09e57ee4442feccf5ae0fe3673c63ba22ba43eaf5f752 (= pack 侧)
cmp /tmp/ota2/toy-new.bin /tmp/ota2/cand-patch.bin
  → ROUNDTRIP_PATCH_OK  ✅
```

### 5.5 nonce 每包随机

两次 `pack-full` 同输入:
- a.etu nonce(off16..31) = `a5a78854dc9a410e09d4b90ebe602304`
- b.etu nonce(off16..31) = `b4994fd22e03e73ad3dbe8115aecc081`
- `NONCE_DIFFER=True` ✅；header_crc32 也随之不同(0x75176fa2 / 0x97cd02df)。

### 5.6 超限与损坏拒绝(returncode=1 + stderr 明确)

- `pack-full --app big.bin(1MB > 960KB)` → rc=1 stderr `[err] image_len=1048576 超 960KB` ✅
- `unpack corrupt.etu(改 off60 1B 破外层头 header_crc32)` → rc=1 stderr `[err] 外层头 header_crc32 不匹配：stored=a8f0b9a6 calc=a8f0b959` ✅
- `unpack corrupt2.etu(改 off80 1B 破 payload)` → rc=1 stderr `[err] payload_crc32 不匹配（密文损坏）` ✅

### 5.7 实现侧自检小结

- pack→unpack 全量/差分往返字节一致；同输入两次 nonce 不同；超限 input 与损坏外层头/payload 均被拒并明确错误(rc=1)。满足卡验收三条。
- 不自验收置完成；待非实现会话独立验收。
- 已知未覆盖:vendor `bsdiff.exe/bspatch.exe` 原生 C 工具与本工具的 .etu 互操作(P0-3 golden vectors 卡职责);CI finalize 正式链(P4-1 职责);真机/App 解析(P2-2 职责)。本卡范围严格限定 pack/unpack Python 自包自解闭环。

## 6. 首轮验收打回整改（2026-07-24，应对 P0-2-acceptance-2026-07-24.md 阻断）

### 6.1 阻断点

非实现会话独立验收发现:`finalize` 与 `unpack --verify-fw-header` 未遵守冻结的 `FW_HEADER_OFFSET=0x400` 布局契约(§0.4/§1):实现把 fw_header 写在镜像 `0x00`,覆盖向量表;`0x400` 处仍为占位 `0xa5`;真实头 CRC/SHA 双零复算失败;`0..0x3ff` 向量表区被改写。源码锚点 `etu_pack.py` 旧 `image[:FW_HEADER_SIZE]` / `etu_unpack.py` 旧 `image[:FW_HEADER_SIZE]`。

### 6.2 整改

- `etu_pack.py build_fw_header/cmd_finalize`:`hdr` 取自 `image[0x400:0x460]`,回填写回 `image[0x400:0x460]`;`image_len` = 整镜像字节数(含 0x400 向量表与头);SHA 双零法把镜像内 `0x400+40..71` 与 `0x400+92..95` 置零;前置长度校验改 `0x400+96`。
- `etu_pack.py` 增 `FW_HEADER_OFFSET=0x400` 常量校验注释(此前常量已定义但未用,现实际使用)。
- `etu_unpack.py verify_fw_header`:`hdr = image[0x400:0x460]`,magic/CRC/SHA 双零(置零用绝对偏移 `0x400+40/0x400+92`)/image_len 全部按 0x400 偏移校验;`FW_HEADER_OFFSET=0x400` 同步定义。

### 6.3 整改后回归(夹具:0x0000..0x03FF 向量表哨兵 `DEAD0000+i`;0x400..0x45F 占位 `0xa5`;0x460..end 本体,12KB)

| 检查 | 结果 |
|---|---|
| `finalize` 后 `image[0:4]` | `0000adde`(向量表区哨兵,非 ETFW) ✅ |
| `finalize` 后 `image[0x400:0x404]` | `45544657` = `ETFW` ✅ |
| 向量表区 `0..0x3ff` 保持原样 | 是(与 sentinel 比对一致) ✅ |
| 0x400 处 header_crc32 stored=`7e5774ad` calc=`7e5774ad` | 一致 ✅ |
| 0x400 处 image_sha256 双零法 stored=`a61b2143…` calc=`a61b2143…` | 一致 ✅ |
| image_len field=12288 == 实际 12288 | 一致 ✅ |
| `pack-full` + `unpack --verify-fw-header` + `cmp` | `ROUNDTRIP_FULL_OK`;candidate `0x400` 头 = ETFW;VT 区与原 app 一致 ✅ |
| candidate image_sha256 双向 | `221e444c…`(pack/unpack 一致) ✅ |
| `pack-patch`(toy-new,无真实头) + `unpack --old` + `cmp` | `ROUNDTRIP_PATCH_OK` ✅ |
| 差分 candidate 套真实头(toy-new-hd) `--verify-fw-header` | 通过 + `cmp` 一致 ✅;无真实头差分 candidate `--verify-fw-header` 正确拒绝 `magic 非 ETFW (got a5a5a5a5)` ✅ |
| 同输入两次 `pack-full` nonce | `bbe66fa6…` / `e7a7b7d8…` `NONCE_DIFFER=True` ✅ |
| 超限(983041B>960KB):`finalize`/`pack-full`/`pack-patch` | 三入口 rc=1 + 明确 stderr ✅ |
| 短于 0x400+96(100B):`finalize` | rc=1 `[err] app.bin 短于 0x400+96` ✅ |
| 损坏外层头 CRC / 损坏 payload | `unpack` rc=1 + 明确 stderr ✅ |

### 6.4 产物

| 路径 | 大小 | mtime | sha256[:16] |
|---|---|---|---|
| `tools/etu_pack.py` | 19085B | 2026-07-24 23:52:30 | 6539f67897956be5 |
| `tools/etu_unpack.py` | 17826B | 2026-07-24 23:53:50 | 100cacd8343eee97 |

`git diff --check` 通过(仅 PLAN-OTA-EXEC.md LF/CRLF 提示,非实现文件空白错误)。未 commit/push;未自验收置完成;契约与 PLAN-OTA.md 未动。待非实现会话重新验收。


## 6. 注意/红线

- **只读契约**:不改 `docs/ota-binary-contracts.md` / `PLAN-OTA.md`;发现矛盾走看板 §9 阻塞,不就地改。
- bsdiff.exe 路径默认 `bsdiff_lzma_AES128-main/bsdiff/build/bin/bsdiff.exe`(--	bsdiff-exe 覆盖)。
- AES key:env `OTA_AES_KEY`(32 hex)优先;缺省用 vendor 示例 key 并 stderr warn。
- 不 commit/push;留主会话收口。
- 不自验收置完成;待非实现会话验收。
