# ota-binary-contracts.md — OTA 五契约字节级定义（实现唯一依据）

> 版本:**v1.0(2026-07-24,P0-1 产出)**。本文档是 fw_header / .etu / BCB / ETSL+ETRJ / BLE 帧五组二进制契约的**唯一定义点**;`PLAN-OTA.md` v1.3.2 为其只读输入。产出后本文档同样冻结:任何字段、数值、端序、CRC 覆盖范围的改动只允许走 `PLAN-OTA-EXEC.md` §9 变更登记回审,禁止就地修改。
> 规则:方案(`PLAN-OTA.md`)引用的每个字段/数值在本文档**有且仅有一处定义**;其他文档与代码一律引用本文档,不复制字段表。

---

## 0. 全局约定

### 0.1 端序

- **默认小端(LE)**:除显式标注"BE(大端)"的字段外,本文档全部多字节整数一律小端。
- 唯一的大端例外:§2.3 规范化内层头的 `ph_hcrc` / `ph_psize` / `ph_ocrc` / `ph_ncrc` 四字段(BE),继承自 bsdiff 工具链注释约定。

### 0.2 CRC 算法(冻结参数)

| 名称 | 用途 | 多项式 | 初值 | 输入反射 | 输出反射 | 异或出值 |
|---|---|---|---|---|---|---|
| CRC32-IEEE | fw_header / .etu 外层头 / BCB / ETRJ / payload / ETSL payload_crc / recovery 尾部 | 反射 `0xEDB88320` | `0xFFFFFFFF` | 是 | 是 | `0xFFFFFFFF` |
| CRC16-CCITT-FALSE | BLE 帧尾 crc16 | `0x1021` | `0xFFFF` | 否 | 否 | `0x0000` |

- CRC32-IEEE 与 `bsdiff_lzma_AES128-main/bsdiff/lib/crc32.c` 查表实现逐项一致(表首项 `0x00000000, 0x77073096, 0xEE0E612C, ...`),即 zlib `crc32()` 同参数。等效调用:`binascii.crc32(data) & 0xFFFFFFFF`(Python)、`zlib.crc32`、vendor `crc32(buf,size)`。
- CRC16-CCITT-FALSE 等效实现:初值 `0xFFFF`,逐字节 `crc ^= b<<8` 后 8 次左移,高位出则异或 `0x1021`,不反射,无最终异或。
- **凡本文档写"crc32"均指 CRC32-IEEE;写"crc16"均指 CRC16-CCITT-FALSE。** 存储端序均为小端。

### 0.3 魔数一览

| 魔数 | ASCII | 所在结构 | 偏移 |
|---|---|---|---|
| `ETFW` | 45 54 46 57 | fw_header(§1) | 0 |
| `ETU1` | 45 54 55 31 | .etu 外层头(§2) | 0 |
| `ETBC` | 45 54 42 43 | BCB(§3) | 0 |
| `ETSL` | 45 54 53 4C | 外部槽头(§4.1) | 0 |
| `ETRJ` | 45 54 52 4A | staging 接收日志固定头(§4.2) | 0x040 |

### 0.4 地址与尺寸常量(四方唯一来源)

| 常量 | 值 | 说明 |
|---|---|---|
| `BOOT_ORIGIN` | `0x08000000` | boot 64KB,链接 ORIGIN |
| `APP_ORIGIN` | `0x08010000` | app 960KB,链接 ORIGIN |
| **`FW_HEADER_OFFSET`** | **`0x400`** | **fw_header 相对 APP_ORIGIN 的偏移;linker / CI finalize / boot 解析 / recovery 校验四方唯一共享常量,任何代码/脚本不得另写数值字面量,一律引用本常量** |
| `FW_HEADER_ADDR` | `0x08010400` | = `APP_ORIGIN + FW_HEADER_OFFSET`(派生,不另定义) |
| `EXT_CANDIDATE` | `0x000000` | 外部 flash 候选槽,1MB |
| `EXT_BACKUP` | `0x100000` | 备份槽,1MB |
| `EXT_RECOVERY` | `0x200000` | 黄金镜像槽,1MB(可选) |
| `EXT_STAGING` | `0x300000` | .etu 暂存槽,2MB |
| `EXT_SELFTEST` | `0x7F0000` | QSPI 自检保留区 64KB,永久避让 |
| `SLOT_HEADER_SIZE` | `0x1000`(4KB) | 外部槽头页尺寸;镜像/payload 本体从槽起始+4KB 对齐处存放 |
| `EEPROM_BCB_A` | `0x00` | AT24C02 内 BCB-A 地址 |
| `EEPROM_BCB_B` | `0x40` | BCB-B 地址 |
| `EEPROM_INIT_MAGIC` | `0xFF` 处 = `0x55` | 现有初始化魔数,**保持不动** |

### 0.5 容量上限(三处强制检查)

| 上限 | 值 | 约束来源 |
|---|---|---|
| .etu 包总长 | ≤ `0x180000`(1.5MB) | staging 净容量 2MB-4KB=`0x1FF000` ≥ 包长 |
| `image_len`(含 fw_header) | ≤ `0xF0000`(960KB) | candidate/backup 净容量 1MB-4KB=`0xFF000` ≥ image_len |
| staging 块数 | 512 块 × 4KB | 与 §4.2 位图 512 位一一对应 |

三处检查点(任一超限立即拒绝):①CI 制包(`etu_pack.py` 拒超限);②App 收包(BEGIN 的 `total_len` 与 .etu 头 `payload_len`);③boot 搬运前(槽头 `payload_len` 界内)。

### 0.6 version_code 编码(PRE-1 冻结)

`version_code = major*10000 + minor*100 + patch`(u32)。

- `version_name` 为 ASCIIZ,规范形如 `X.Y.Z`(可带可选 `v` 前缀;两段式 `X.Y` 等价 `X.Y.0`;CI nightly 可追加 `-nightly.<n>`,编码只取连字符前数字段)。
- 约束:`minor`/`patch` ∈ 0..99;结果必须落入 u32。
- 示例:`2.8.0→20800`、`2.8.1→20801`、`2.7`/`2.7.0→20700`。
- 单调迁移:旧公式 `major*1000+minor` 产物(如 `v2.7→2007`)严格小于同版本新编码(`2.7.0→20700`),设备侧 `target_vcode > cur_vcode` 向后兼容;**旧公式作废**,CI/CF/fw_header/.etu 一律用新公式。
- MCU OTA 拒绝 `target_vcode ≤ cur_vcode`(降级拒绝);唯一例外为 §6 物理 recovery。

### 0.7 JEDEC ID 白名单

`EF4018`(W25Q128/16MiB)、`1C4018`(EN25QH128A/16MiB)、`1C4017`(EN25QH64A/8MiB)、`EF4017`(W25Q64/8MiB)。开机读 JEDEC ID 不在白名单 → 置 OTA 禁用旗标(既有功能不受影响)+UI 提示;BLE BEGIN 以 §5.7 `ERR_OTA_DISABLED` 拒绝。

---

## 1. fw_header(App 镜像内嵌,96B)

位置:`APP_ORIGIN + FW_HEADER_OFFSET` = `0x08010400`。linker 定义专用 `.fw_header` 段 @ ORIGIN+0x400,并 `ASSERT(SIZEOF(.isr_vector) <= 0x400)` 防回归(GCC 向量表实测 `0x20C`)。

### 1.1 字段表(96B,小端)

| off | size | 字段 | 说明 |
|---|---|---|---|
| 0 | 4 | magic | `"ETFW"` |
| 4 | 4 | header_ver | 恒 `1` |
| 8 | 4 | version_code | §0.6 编码 |
| 12 | 16 | version_name | ASCIIZ,不足 16B 以 `0x00` 填充 |
| 28 | 4 | build_ts | UNIX 秒 |
| 32 | 4 | hw_rev | 恒 `1` |
| 36 | 4 | image_len | 含本头,字节数;上限 §0.5 |
| 40 | 32 | image_sha256 | 全镜像 SHA-256(计算规则见 §1.2) |
| 72 | 1 | layout_id | 恒 `1`(分区布局代) |
| 73 | 1 | min_boot_ver | 恒 `1`;boot 版本低于此值拒绝 |
| 74 | 18 | pad | `0xFF` |
| 92 | 4 | header_crc32 | CRC32,覆盖 off 0..91(前 92B) |

### 1.2 校验依赖消解(固定填充顺序,boot/CI/vectors 三方一致)

1. `image_sha256` = 全镜像 SHA-256,计算时 **`image_sha256`(off 40..71)与 `header_crc32`(off 92..95)两字段均按全零参与**("SHA 双零法")。
2. 制包顺序:构建含占位头 app.bin → 填版本/时间/长度/layout/min_boot → 算 SHA 回填 off 40..71 → 最后算前 92B CRC32 回填 off 92..95。
3. boot 校验顺序(擦 App 前统一执行,任一项失败即拒绝):
   ① magic+header_crc32 → ② image_sha256(双零重算) → ③ hw_rev==本机 → ④ layout_id==本机 → ⑤ min_boot_ver ≤ boot 版本 → ⑥ 向量表首项(MSP 初值落 RAM 区 `0x20000000..0x20080000`)与 Reset_Handler(落 app 区 `0x08010000..0x080FFFFF`)范围合法。

---

## 2. .etu 容器(64B 外层头 + payload)

### 2.1 外层头字段表(64B,小端)

| off | size | 字段 | 说明 |
|---|---|---|---|
| 0 | 4 | magic | `"ETU1"` |
| 4 | 2 | header_len | 恒 `64` |
| 6 | 2 | flags | bit0=AES bit1=LZMA bit2=差分 bit3=全量;**bit2/bit3 互斥且必居其一**;v1 产物恒含 bit0+bit1 |
| 8 | 4 | alg_id | 恒 `1`(AES-128-CTR + LZMA) |
| 12 | 4 | key_id | v1 恒 `1`;换 key 递增 |
| 16 | 16 | aes_nonce | AES-CTR nonce,**CI 每包随机生成**(禁止固定 nonce) |
| 32 | 4 | payload_len | off 64 起 payload 字节数;包总长 = 64 + payload_len,上限 §0.5 |
| 36 | 4 | payload_crc32 | CRC32,覆盖**加密后** payload 字节(传输/存储完整性早失败) |
| 40 | 4 | target_vcode | 目标版本码,§0.6 编码 |
| 44 | 4 | base_vcode | 差分基版版本码;**全量 = 0** |
| 48 | 2 | hw_rev | 恒 `1` |
| 50 | 1 | layout_id | 恒 `1`(分区布局代) |
| 51 | 1 | min_boot_ver | 恒 `1` |
| 52 | 8 | base_sha8 | 差分基版镜像 SHA-256 前 8B;**全量 = 全 0**(基准身份防"同版本码不同构建") |
| 60 | 4 | header_crc32 | CRC32,覆盖 off 0..59(前 60B) |
| 64 | .. | payload | AES-CTR 密文(形态见 §2.2) |

flags 合法组合(v1):全量 = `0x000B`(bit0+bit1+bit3);差分 = `0x0007`(bit0+bit1+bit2)。其余组合拒绝。

### 2.2 payload 两种形态(解密后明文布局)

- **差分 payload 明文** = 40B 规范化内层头(§2.3) + LZMA 流(bsdiff 控制/数据流,解压长度 = `ph_original_size`)。
- **全量 payload 明文** = LZMA-Alone 形态:5B props + u64 原始长度(小端) + LZMA 流;解压结果即最终 app.bin(含 fw_header)。
- LZMA 字典上限 **16KB**(CI 制包固定 `-dict 16`;差分包工具默认 4KB 字典)。解压写回以 candidate 净容量(`0xFF000`)做**溢出安全钳制**:offset+len 逐次检查,超限即中止置错。

### 2.3 差分内层头(40B 规范化形式,逐字段冻结)

背景:bsdiff 工具原生 `patch_header_t` 为 40B(6×u32=24B + 5B LZMA props + 3B ABI 对齐填充 + u64=8B),且工具按宿主 sizeof/端序直写。**打包器(`etu_pack.py`)解析原生头后必须按下表重新序列化;MCU 只认本表规范化形式,逐字段解析,禁止 struct memcpy。**

| off | size | 字段 | 端序 | 说明 |
|---|---|---|---|---|
| 0 | 4 | ph_hcrc | **BE** | 头 CRC:CRC32 覆盖规范化 40B 全头,计算时本字段(off 0..3)按全零参与 |
| 4 | 4 | ph_psize | **BE** | 差分包 LZMA 压缩流字节数(off 40 起) |
| 8 | 4 | ph_osize | LE | 旧文件(基版镜像)字节数 |
| 12 | 4 | ph_nsize | LE | 新文件(目标镜像)字节数 |
| 16 | 4 | ph_ocrc | **BE** | 旧文件内容 CRC32(二重兜底) |
| 20 | 4 | ph_ncrc | **BE** | 新文件内容 CRC32(合成后复核) |
| 24 | 5 | ph_lzma_props | — | LZMA-Alone props 原始 5B(lc/lp/pb + 字典尺寸,编码器原样输出) |
| 29 | 3 | pad | — | 显式置 `0x00 0x00 0x00`(原 ABI 对齐填充位的规范化) |
| 32 | 8 | ph_original_size | LE | u64,LZMA 解压后 bsdiff 流长度 |

- 全部 CRC 按**规范化后字节**重算(打包器不得沿用工具原值)。
- MCU 侧校验顺序:ph_hcrc(置零重算) → ph_psize 与 .etu `payload_len-40` 一致 → 解压长度 == ph_original_size → bspatch 前 ph_osize/ph_ocrc 对基版 → 合成后 ph_nsize/ph_ncrc 对 candidate。

### 2.4 App 收包校验清单(顺序执行,任一失败即拒并回对应 §5.7 状态码)

① 外层头 magic+header_len+header_crc32 → ② flags 合法组合 → ③ alg_id/key_id 受支持 → ④ hw_rev==本机 → ⑤ layout_id==本机 → ⑥ min_boot_ver ≤ 当前 boot 版 → ⑦ target_vcode > cur_vcode(降级拒绝) → ⑧ 差分:base_vcode==cur_vcode 且 base_sha8==当前镜像 SHA-256 前 8B → ⑨ 包长/payload_len 上限(§0.5) → ⑩ payload_crc32(收齐后)。

---

## 3. EEPROM BCB(64B × 2,seq 仲裁)

布局:BCB-A @ `0x00`,BCB-B @ `0x40`,`0x80` 起保留 127B,`0xFF` = `0x55` 初始化魔数(保持不动)。

### 3.1 字段表(64B,小端)

| off | size | 字段 | 说明 |
|---|---|---|---|
| 0 | 4 | magic | `"ETBC"` |
| 4 | 1 | schema_ver | 恒 `1` |
| 5 | 1 | state | 0=IDLE 1=STAGED 2=APPLYING 3=TEST_BOOT 4=CONFIRMED 5=ROLLBACK |
| 6 | 1 | boot_try | 初始 `3`;TEST_BOOT 每试启一次先持久化 try-- |
| 7 | 1 | copy_phase | 0=无 1=apply 搬运中 2=rollback 搬运中 |
| 8 | 2 | seq | 仲裁序号,见 §3.2 |
| 10 | 2 | resume_block | 断点续搬:**已完成读回验证**的 4KB 块数(下次从此块起重擦重写) |
| 12 | 4 | cand_addr | 候选镜像在外部 flash 的绝对地址(= `EXT_CANDIDATE + SLOT_HEADER_SIZE`) |
| 16 | 4 | cand_len | 候选镜像字节数(= fw_header.image_len) |
| 20 | 4 | cand_crc32 | 候选镜像 CRC32 |
| 24 | 4 | cand_vcode | 候选版本码 |
| 28 | 4 | cur_vcode | CONFIRMED 时同步 = cand_vcode;ROLLBACK 完成时 = backup_vcode |
| 32 | 4 | backup_len | |
| 36 | 4 | backup_crc32 | |
| 40 | 4 | backup_vcode | |
| 44 | 12 | pad | `0xFF` |
| 56 | 4 | reserved | `0x00000000` |
| 60 | 4 | crc32 | CRC32,覆盖 off 0..59(前 60B) |

合法判定:magic 匹配 且 schema_ver==1 且 crc32 校验通过,三者齐备该块才为"合法块"。

### 3.2 seq 仲裁(冻结规则)

- 比较规则:`(int16)(a.seq - b.seq) > 0` 者新;**相等且双合法取 A**。
- 仅一合法取合法者;**双块均坏**:app fw_header CRC+SHA 有效 → 直接引导;否则恢复模式。镜像真伪始终以 fw_header SHA 为准。
- 写序:**单次事务 = 写非活动块(带 seq+1)→ 读回比对 → 通过后即生效**(活动块由 seq 仲裁决定,无二次改写)。

### 3.3 安全写事务(P0-4 实现依据)

逐 8B 页写(AT24C02 页 8B,写周期 ~5ms):每页写后 ACK polling(≤10ms 超时)→ 错误返回;全块写完后整 64B 读回逐字节比对,不符即错误返回。boot/App 共用 `eeprom_bcb.c`。byte 255 = `0x55` 初始化魔数不参与本事务,保持不动。

### 3.4 关键状态转换的原子写要求(R4-1)

- STAGED→APPLYING:`{state=APPLYING, copy_phase=1, resume_block=0}` 一次事务写入。
- **ROLLBACK 首转:`{state=ROLLBACK, copy_phase=2, resume_block=0}` 必须一次原子事务写入**,禁止分字段多次写。
- TEST_BOOT 试启:**先持久化 try-- 再跳 app**(首跳即消耗,共 3 次)。
- backup 槽锁定:STAGED→CONFIRMED 期间不得重写 backup;下轮升级自拷仅在 CONFIRMED 态允许。

---

## 4. 外部槽头 ETSL(32B)与 staging 接收日志 ETRJ

### 4.1 ETSL 槽头字段表(32B,小端,置于各外部槽起始)

| off | size | 字段 | 说明 |
|---|---|---|---|
| 0 | 4 | magic | `"ETSL"` |
| 4 | 1 | slot_type | 1=candidate 2=backup 3=staging 4=recovery |
| 5 | 3 | pad | `0xFF` |
| 8 | 4 | payload_len | 槽内 payload 字节数(本体位于槽起始+`SLOT_HEADER_SIZE`) |
| 12 | 4 | payload_crc32 | payload 内容 CRC32 |
| 16 | 4 | vcode | 槽内镜像版本码 |
| 20 | 8 | sha8 | 镜像 SHA-256 前 8B |
| 28 | 4 | commit_marker | 完整提交标记,见下 |

- `commit_marker` 冻结值:u32 `0x434F4D54`;**片上字节序(小端存储)为 `54 4D 4F 43`**。擦除态 `0xFFFFFFFF` = 未提交。半写槽以 commit_marker 缺失判无效。
- ETSL 自身无 CRC;有效性 = magic + commit_marker;内容完整性由 payload_crc32 承担。

### 4.2 staging 槽头 4KB 页内完整偏移表(BLE 断点续传唯一依据)

| 页内 off | size | 内容 |
|---|---|---|
| 0x000 | 32B | ETSL 槽头(§4.1;staging 槽的 payload_len/payload_crc32 在包终验时随 commit_marker 一并填写) |
| 0x020 | 32B | 保留,`0xFF` |
| 0x040 | 44B | ETRJ 固定头(字段表见 §4.2.1) |
| 0x06C | 4B | pad,`0xFF`(对齐位图至 0x070) |
| 0x070 | 64B | block_bitmap(512 位,1 位 = 1 个 4KB 块) |
| 0x0B0 | 3920B | 留白至 0xFFF,`0xFF` |

#### 4.2.1 ETRJ 固定头(44B,小端)

| off | size | 字段 | 说明 |
|---|---|---|---|
| 0 | 4 | magic | `"ETRJ"` |
| 4 | 32 | package_sha256 | 整个 .etu 包(含 64B 外层头)的 SHA-256,会话身份 |
| 36 | 4 | total_len | .etu 包总长(= 64 + payload_len) |
| 40 | 4 | hdr_crc32 | CRC32,**仅覆盖 off 0..39(40B 不可变前缀)** |

#### 4.2.2 block_bitmap(64B = 512 位)

- 位编号:块 `n` ↔ 字节 `n>>3` 的位 `n&7`(字节内 LSB 优先)。staging 共 512 块(2MB/4KB),与位图一一对应。
- 初始(整页擦除后)全 `0xFF`;块落盘且读回验证后对应位 **1→0**(NOR 单调翻转,免擦除)。位图**无 CRC**——单调 1→0 + 写后读回保证。
- `durable_off` = 自首位起连续 0 位块数 × 4KB(包尾块按实长计入)。

### 4.3 擦写序(marker-last,R4-3 / R8-2)

1. 先擦槽头扇区(commit_marker 保持擦除态 `0xFF`);
2. ETRJ 固定头先写并读回校验;
3. 接收过程只动位图(清位后读回);
4. ETSL 的 payload_len/payload_crc32/vcode/sha8 在包终验通过后先写并读回;
5. **commit_marker 最后单独写入**(禁止复用旧 marker;禁止实现成与其他字段一次同时提交)。

### 4.4 重传与清位规则(R8-1)

**重传已部分写入的块前必须先扇区擦除,写完读回成功后方可清位图位。** 跨复位持久化状态只有整 4KB 块进度;不足一块的接收进度仅存 RAM,断电/重连后该块整块重传(代价 ≤4KB)。包尾块按 `total_len` 定界的实际长度落盘置位。

### 4.5 会话恢复策略(R4-3,二选一已选定)

**选定"持久化会话恢复"**:重连后新 BEGIN 携带 package_sha256;MCU 查 staging 页:package_sha256 匹配且 ETRJ hdr_crc32 合法 → 按位图续传(回 durable_off+当前块位图);日志缺失/不合法/sha 不匹配 → 整页擦除从零重传。**禁止以尾部 CRC 猜测进度**;新会话(不同 package_sha256)才整页擦除重建。

---

## 5. BLE 帧协议(FFF2 下行 / FFF1 上行,透传 UART)

### 5.1 帧布局

```
A5 5A | u8 cmd | u8 session | u16 seq | u16 len | payload[len] | u16 crc16
```

- `len` = payload 字节数(不含帧头 8B、不含 crc16)。
- `crc16` = CRC16-CCITT-FALSE,**覆盖 cmd..payload**(不含 `A5 5A`,不含自身),小端存储。
- `seq` = 会话内帧序号,初值 0,每发一帧 +1;16bit 回绕比较 `(int16)(a-b)`;ACK 回显被应答帧的 seq。
- 顶层分流:UART 收到 `A5 5A` 进入二进制 OTA 处理器,其余字节走现有 TinyBTPlus 文本协议。**OTA 会话期间(BEGIN 成功→END/ABORT/超时)**:关闭文本回显、关闭 200ms `X-Trace\r\n` 周期上行、暂停调试透传——上行只允许 ACK/事件帧。
- 硬件流控不存在(BRTS/CTS 接地),**禁启用 UART 硬件流控**;流量控制全靠 §5.5 credit 窗口。MCU UART 环形缓冲 ≥4KB;Flutter 按协商 MTU-3 分片。

### 5.2 命令表

| cmd | 名称 | 方向 | payload | 应答 |
|---|---|---|---|---|
| 0x00 | GET_INFO | 下 | 空 | 0x80 INFO |
| 0x01 | BEGIN | 下 | §5.3 | 0x81 ACK(含 session) |
| 0x02 | DATA | 下 | §5.4 | 0x82 ACK |
| 0x03 | END | 下 | `package_sha256`(32B,复述) | 0x83 ACK |
| 0x04 | ABORT | 下 | 空 | 0x84 ACK |
| 0x80 | INFO | 上 | §5.2.1 | — |
| 0x81..0x84 | ACK | 上 | §5.6 | — |

- **GET_INFO 以 session=0 发送**(升级前必查:APP 读设备身份→上报 CF latest 选包,差分基准匹配则 patch,否则退 full)。
- **session**:BEGIN 由 MCU 分配返回(非零),后续 DATA/ACK/END 均携带;不匹配即丢弃。

#### 5.2.1 INFO payload(50B,顺序小端)

| off | size | 字段 | 说明 |
|---|---|---|---|
| 0 | 8 | model | ASCIIZ(如 `X-Track\0`) |
| 8 | 2 | hw_rev | u16 |
| 10 | 1 | layout_id | |
| 11 | 1 | boot_ver | |
| 12 | 4 | cur_vcode | u32 |
| 16 | 32 | image_sha256 | 当前镜像完整 SHA-256 |
| 48 | 1 | proto_ver | 恒 `1` |
| 49 | 1 | max_window_segs | 恒 `32`(协议扩展预留) |

### 5.3 BEGIN payload(101B,顺序小端)

| off | size | 字段 | 说明 |
|---|---|---|---|
| 0 | 1 | proto_ver | 恒 `1` |
| 1 | 4 | total_len | .etu 包总长(u32) |
| 5 | 32 | package_sha256 | 整包 SHA-256(与 §4.2.1 同值) |
| 37 | 64 | etu_header | .etu 64B 外层头逐字节副本 |

### 5.4 DATA payload

`u32 off`(LE)+ `data`(恒 128B;**仅包尾段可短**)。off 非 128 对齐 → NAK(ACK 回 `ERR_OFFSET`)。

### 5.5 分段与 credit 窗口(冻结,R4-4 / R8-3 / R8-4)

- 段净荷恒 **128B**,4KB 块 = **恰 32 段**,段不跨块;唯一例外 = 包尾段(**off 仍 128 对齐,仅长度可短**)。
- **credit 窗口 = 当前块**:发送端在途段 ≤ 当前 4KB 块未确认段数(≤32);聚合缓冲恒 4KB 与窗口精确匹配(活跃窗口 ≤ 缓冲实际容量,无 4080/4096 缺口)。
- ACK 的 `block_bitmap`(u32)= durable_off 所在块的 32 段接收位图(bit i = 块内第 i 段,已收=1);块收齐 → 落盘读回 → §4.2.2 位图清位 → durable_off 前移 4KB → 窗口滑至下一块。
- **durable_off** = MCU 已落盘 staging 且读回验证通过的整块进度(4KB 粒度,包尾块按实长)——与 §4.2 位图严格一致;"已收未落盘"只反映在 ACK 的 block_bitmap,不推进 durable_off。
- **对 durable_off 之前(已提交)offset 的重复 DATA 必须幂等:直接重发当前 ACK,不重写 staging**(R8-4)。
- 活性规则:①块收齐即落盘 ACK;②500ms 无新段 → ACK 重发当前 block_bitmap(发送端据此补传缺段;500ms 为初值非契约);③包尾块按 total_len 定界收齐即落盘。
- 断连重连:按 §4.5 恢复;超时/重传参数 P3 实测标定。

### 5.6 ACK payload

| cmd | payload | 长度 |
|---|---|---|
| 0x81(BEGIN 应答) | `u8 status, u8 session, u32 durable_off, u32 block_bitmap` | 10B |
| 0x82/0x83/0x84 | `u8 status, u32 durable_off, u32 block_bitmap` | 9B |

BEGIN 失败时 session 字段回 `0x00`。BEGIN 重连续传成功时,durable_off/block_bitmap 即 §4.5 恢复值。

### 5.7 状态码表(唯一来源)

| status | 名称 | 含义 / 发送端处置 |
|---|---|---|
| 0x00 | OK | 成功 |
| 0x01 | ERR_FRAME | 帧格式/长度非法;校正后重发 |
| 0x02 | ERR_CRC | crc16 校验失败;重发该帧 |
| 0x03 | ERR_SEQ | seq 不连续且非重发;按 ACK 回显对齐 |
| 0x04 | ERR_SESSION | session 不匹配(丢弃前的应答);重新 BEGIN |
| 0x05 | ERR_STATE | 状态机不允许(如未 BEGIN 先 DATA);重新 BEGIN |
| 0x06 | ERR_OFFSET | off 非 128 对齐 / 越过 total_len;按 durable_off+bitmap 续传 |
| 0x07 | ERR_LEN | total_len/payload_len 超 §0.5 上限;换包 |
| 0x08 | ERR_HDR | .etu 头非法(magic/CRC/flags/alg/key);换包 |
| 0x09 | ERR_HW_REV | hw_rev 不匹配;放弃 |
| 0x0A | ERR_LAYOUT | layout_id 不匹配;放弃 |
| 0x0B | ERR_BOOT_VER | min_boot_ver > 当前 boot 版;先升级 boot |
| 0x0C | ERR_VERSION | target_vcode ≤ cur_vcode(降级拒绝);放弃 |
| 0x0D | ERR_BASE | 差分基准不匹配(base_vcode/base_sha8);改投全量包 |
| 0x0E | ERR_BUSY | TEST_BOOT 期间拒绝新 OTA;待 CONFIRMED 后重试 |
| 0x0F | ERR_FLASH | staging 写/读回失败;重试,持续失败放弃 |
| 0x10 | ERR_SHA | END 包 SHA-256 复核失败;整页擦除重传 |
| 0x11 | ERR_OTA_DISABLED | JEDEC 白名单外,OTA 已禁用;放弃 |
| 0x12 | ERR_PROTO | proto_ver 不支持;APP 升级协议 |
| 0xFF | ABORTED | 对端中止/会话超时;状态已清理,可重新 BEGIN |

未列出值保留;发送端收到未知 status 按不可恢复错误处理(中止会话)。

---

## 6. recovery 资产与尾部容器(8B)

`recovery-vX.Y.Z.bin` = 最终 app.bin + 尾部 8B,CI 每正式版产出;J-Link 直刷或 UART-Ymodem 传输,boot 固定写 `0x08010000`。

| off | size | 字段 | 说明 |
|---|---|---|---|
| image_len+0 | 4 | image_len | u32 LE,= 前段 app.bin 字节数(== fw_header.image_len) |
| image_len+4 | 4 | crc32 | u32 LE,CRC32 覆盖前段 app.bin 全字节(0..image_len-1) |

- **两层校验职责分离**:尾部 len/CRC 仅为**传输容器校验**(判断收全没收坏);写入后启动前仍强制执行 §1.2 fw_header 全项校验(SHA/hw_rev/layout_id/min_boot_ver/向量范围)——recovery 不绕过防错板。
- **版本例外(显式声明)**:物理 recovery **允许降级**(不比较 vcode;救砖场景黄金镜像常旧于损坏的当前版;"防旧版误刷"保证的适用范围 = OTA 通道,物理在场按键 ≥3s 的 recovery 不在其内)。
- J-Link 直刷用脚本剥离尾部 8B 后烧写(或直接烧最终 app.bin),不得把容器尾写入 App 分区(R4-5)。
- 进入条件:仅**持续按住编码器按键 ≥3s** 的物理在场条件下允许进入 raw recovery。

---

## 7. R4 / R8 条款对号表

### 7.1 R4 五条固化约束(遗漏任一重新阻断 P1/P2)

| 编号 | 条款 | 本文档锚点 |
|---|---|---|
| R4-1 | ROLLBACK 首转原子写 copy_phase=2+resume_block=0 | §3.4 |
| R4-2 | layout_id/min_boot_ver 拒绝规则入 §4 契约与 vectors | §1.2③④⑤、§2.4④⑤⑥(golden vectors 由 P0-3 按此生成) |
| R4-3 | 槽头 marker-last 擦写序 + BLE 收包中复位的会话恢复二选一策略 | §4.3(marker-last)、§4.5(已选定持久化会话恢复,禁尾部 CRC 猜进度) |
| R4-4 | 活跃窗口 ≤ 聚合缓冲实际容量 + 溢出处理 | §5.5(窗口=当前块恰 32 段=4KB 缓冲;溢出 → §5.7 ERR_OFFSET/ERR_LEN) |
| R4-5 | CI 明确基版 raw bin 来源 + J-Link recovery 脚本剥尾 | §6(尾部 8B 容器定义+剥尾要求;基版来源 = PLAN-OTA.md §6.1 正式发布③,本契约不另定义) |

### 7.2 R8 五条实现验收项

| 编号 | 条款 | 本文档锚点 |
|---|---|---|
| R8-1 | 重传块先擦 + 读回后清位 | §4.4 |
| R8-2 | ETSL 先写校验 + commit_marker 最后单独写 | §4.3 第 4/5 步 |
| R8-3 | 尾段 off 对齐仅长度短 | §5.5 第 1 条 |
| R8-4 | 重复 DATA 幂等(直接重发当前 ACK,不重写 staging) | §5.5 |
| R8-5 | D1 SQL 验证"每 release 恰一 full"(插入第二个 full 必须被拒) | CF 侧验收项,非二进制契约;锚 PLAN-OTA.md §6.2/§8-P4,本文档仅对号不落字节 |

---

## 8. 数值样例(供三方实现互校;golden vectors 由 P0-3 扩展)

> 以下样例中 SHA/nonce 等字段以全零示意,仅用于核对字段 offset、端序与 CRC 覆盖范围;真实包以 P0-3 golden vectors 为准。

### 8.1 fw_header(v2.8.0,image_len=96 示意)

```
45544657 01000000 40510000 322e382e300000000000000000000000
001e8566 01000000 60000000 00000000...00000000(32B sha=0)
01 01 ffffffffffffffffffffffffffffffffffff d1cb1dfe
```
- version_code = `0x00005140` = 20800;build_ts = `0x66851E00` = 1720000000(LE 字节 `00 1e 85 66`)。
- hw_rev = `0x00000001`(LE `01 00 00 00`);image_len = `0x00000060` = 96(LE `60 00 00 00`)。
- header_crc32 = **`0xFE1DCBD1`**(覆盖前 92B;LE 存储 `d1 cb 1d fe`)。

### 8.2 .etu 外层头(全量,flags=0x000B;payload_len=100,payload_crc32=0x11111111 示意)

```
45545531 4000 0b00 01000000 01000000 00000000000000000000000000000000
64000000 11111111 40510000 00000000 0100 01 01 0000000000000000 63aad014
```
- header_crc32 = **`0x14D0AA63`**(覆盖前 60B;LE 存储 `63 aa d0 14`)。
- 同字段差分包(flags=`0x0007`,base_vcode=20700,base_sha8=`0011223344556677`):header_crc32 = **`0x4CFFA9FF`**。

### 8.3 BCB(STAGED,cand @0x1000 长 0x96000,crc 0x11223344,cand_vcode=20800,cur_vcode=20700,seq=1)

```
45544243 01 01 03 00 0100 0000 00100000 00600900 44332211 40510000
dc500000 00000000 00000000 00000000 ffffffffffffffffffffffff 00000000 ac7b7f50
```
- crc32 = **`0x507F7BAC`**(覆盖前 60B;LE 存储 `ac 7b 7f 50`)。

### 8.4 ETSL

- 未提交(staging,marker 擦除态):
  `4554534c 03 000000 00000000 00000000 00000000 0000000000000000 ffffffff`
- 已提交(payload_len=100,crc=0x22222222,vcode=20800,sha8=`0011223344556677`):
  `4554534c 03 000000 64000000 22222222 40510000 0011223344556677 544d4f43`
  (commit_marker u32 值 `0x434F4D54`,片上字节 `54 4d 4f 43`)

### 8.5 ETRJ(package_sha256 全零示意,total_len=100)

`4554524a 00000000...00000000(32B) 64000000 878c17c0`
- hdr_crc32 = **`0xC0178C87`**(覆盖前 40B;LE 存储 `87 8c 17 c0`)。

### 8.6 BLE 帧

- GET_INFO(session=0,seq=0,len=0):**`a5 5a 00 00 00 00 00 00 10 0e`**(crc16=`0x0E10`,LE 存储 `10 0e`)。
- ACK 0x82(status=OK,session=1,seq=0,durable_off=0,bitmap=0):**`a5 5a 82 01 00 00 09 00 00 00 00 00 00 00 00 00 00 ae 56`**(19B;len=9,payload 9B;crc16=`0x56AE`)。
- INFO payload 恒 50B(§5.2.1);BEGIN payload 恒 101B(§5.3)。

---

## 9. 引用关系

- 上游(只读):`PLAN-OTA.md` v1.3.2 §1/§2/§3/§4/§5.1/§6.1;`PLAN-OTA-REVIEW-LOG.md` R4/R8。
- 下游(必须引用本文档,不得另定字段):`tools/etu_pack.py` / `tools/etu_unpack.py`(P0-2)、`tests/ota-vectors/`(P0-3)、`Libraries/EEPROM/eeprom_bcb.c`(P0-4)、bootloader 与 App 解析代码(P1/P2)、BLE 帧层(P3)、CI finalize 脚本(P4)。
- `FW_HEADER_OFFSET=0x400`、version_code 新编码、CRC 参数、状态码表如有改动需求 → `PLAN-OTA-EXEC.md` §9 变更登记,禁止就地修改。
