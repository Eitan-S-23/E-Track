# PLAN-OTA.md — E-Track 单片机 BLE/SD OTA 全链路方案

> 版本:**v1.3(2026-07-23,审查收敛冻结版)**。历程:v1.0 → v1.1 自审 12 项 → v1.2 A 组 8 项重写 → v1.2.1 codex 18 条 → v1.2.2 修 R3 五高危(R4 同意)→ v1.2.3 C 组 10 条 → v1.2.4 修 R6 六高危 → v1.2.5 修 R7 阻断二项 → **R8 codex 复审"同意收敛"**,其 5 条实现验收项已固化进 §2.3/§5.1/§8-P4。**本版为 P0 契约冻结基线**;"同意收敛"指方案层面(codex 未跑构建/真机),实现与生产发布按 §8 各阶段验收。v1 威胁模型(不防主动伪造)为已接受的产品风险(§0.2)。
> 决策历史与验证记录见 `PLAN-OTA-DRAFT.md`;两轮审查记录见 `PLAN-OTA-REVIEW-LOG.md`。
> **实施顺序:P0(契约冻结+基建)→ P1(bootloader)→ P2(MCU App)→ P3(BLE+Flutter)→ P4(CI/CF)→ P5(联调)。P0 未完成不得进入 P1/P2。**

## 0. 需求映射与威胁模型

### 0.1 需求映射(用户六条 → 方案落点)
| # | 需求 | 落点 |
|---|---|---|
| 1 | Action 编译→推 CF→APP 查版本→BLE 传→MCU 更新 | §6 CI/CF、§5 传输、§4 状态机 |
| 2 | bsdiff_lzma 验证 + 差分升级 + boot/app1/app2 | 验证✅(草稿)、§2 分区、§3 格式 |
| 3 | CF 后台管理固件发布 | §6.2(API/admin 大部已有,补真实缺口) |
| 4 | 完善方案 | 全文 + §9 风险 |
| 5 | 边问边写文件 | DRAFT + 本文 + REVIEW-LOG |
| 6 | 第二步群组调 codex | 两轮审查完成(见 REVIEW-LOG) |

### 0.2 威胁模型与保证等级(v1 明确声明)
**v1 保证**:防偶发损坏(误码/断电半写/坏块)、防旧版误刷(版本码单调)、防错板(hw_rev)。
**v1 不保证**:防主动伪造——SHA-256/AES-CTR 均非签名,AES 对称密钥嵌入固件可被提取;BLE/SD/UART 输入视为**半可信**(家用单人场景)。
**v2 可选**:Ed25519 签名(公钥入 boot)。按项目全局准则(安全最低优先级)不进 v1。
**恢复模式约束**:raw recovery(仅 CRC 的裸恢复)只允许在**持续按住编码器按键 ≥3s** 的物理在场条件下进入。

## 1. 硬件与存储现状(实测锁定,含 v1.2 盘点修正)

| 项 | 事实 | 来源 |
|---|---|---|
| MCU | AT32F435RGT7:内部 flash 1MB(sector 4KB)、RAM 384KB(App 现用 82.96%) | 链接报告 |
| 外部 flash | PCB 网表 = W25Q128JVSIQ(16MiB);用户口头 = 实焊 8MB 兼容片;代码注释矛盾 → **运行时读 JEDEC ID 定容量,分区表固定用前 8MiB 保守窗口,白名单按实读 ID** | Trace.enet:2169、HAL_W25Q128.cpp:58 |
| QSPI 驱动 | **已在生产链**:`HAL_Init()` 开机即调 `Qspi_Init()`(HAL.cpp:88),且自检**擦写窗口末尾 64KB**(0x7F0000 起)→ P0 改 `CONFIG_QSPI_SELFTEST_ENABLE` 默认 0,该 64KB 永久划为自检保留区 | HAL_W25Q128.cpp:58-66 |
| EEPROM | AT24C02 256B(页 8B,写周期 ~5ms);**byte 255 = 0x55 初始化魔数(现有逻辑,勿动)**;现有驱动多字节写无页边界/无 ACK polling/忽略返回值(EEPROM.cpp:46)→ **P0 重写安全写接口后方可承载 BCB** | Libraries/EEPROM |
| BLE | XY-MBO35A 透传(FFF0/FFF1 Notify/FFF2 Write),115200 起步可 AT 提速 921600,`+READY/+CONNECTED` 事件;**网表实测 Pin5(BRTS)/Pin6(CTS)均接地——硬件流控不存在,禁启用 UART 硬件流控,流量控制全靠协议 credit 窗口(§5.1)** | Doc/ble.pdf、Trace.enet |
| App 链接地址 | 现 `0x08000000`(generated_linker.ld:11)→ 迁 `0x08010000`,**首次部署必须 J-Link bootstrap(§7),App 无法自迁移** | linker.ld |
| bsdiff_lzma | PC 闭环✅(603KB 固件+200 处改动 → 补丁 1,062B;加密解密还原字节一致);4 坑已纳入 §3/§6 设计 | 草稿任务2 |

## 2. 分区与数据布局(字节级,P0 冻结)

### 2.1 内部 flash 1MB
```
0x08000000  boot  64KB   BCB 状态机/QSPI 读/内 flash 编程/CRC+SHA/按键/恢复 UI(无 LZMA/bspatch/BLE/AES)
0x08010000  app   960KB  唯一运行槽(fw_header @app+FW_HEADER_OFFSET=0x400;现 603KB,余 37%)
```

### 2.2 外部 flash 前 8MiB 窗口
```
0x000000  candidate  1MB    候选镜像(bspatch 输出/全量解包输出,明文 bin)
0x100000  backup     1MB    当前版本备份(升级前 App 自拷)
0x200000  recovery   1MB    黄金镜像(可选,J-Link 首刷写入;空则跳过该级)
0x300000  staging    2MB    .etu 原始包暂存(BLE/SD 两来源统一落此)
0x500000  空闲       ~2.9MB 未来资源区
0x7F0000  selftest   64KB   QSPI 自检保留区(生产自检默认关,区域永久避让)
```
- 各槽自描述(32B 槽头,见 §2.3),清单类状态全部在 EEPROM BCB,**外部 flash 整片故障不影响启动决策**。
- **净容量与上限检查(三处强制)**:staging 净 2MB-4KB(槽头页)≥ .etu 上限 1.5MB;candidate/backup 净 1MB-4KB ≥ image_len 上限 960KB。检查位置:①CI 制包(etu_pack 拒超限)②App 收包(BEGIN 的 total_len 与 .etu 头 payload_len)③boot 搬运前(槽头 payload_len 界内)。任一超限立即拒绝。
- JEDEC ID 白名单(P0 定):`EF4018`(W25Q128/16MiB)、`1C4018`(EN25QH128A/16MiB)、`1C4017`(EN25QH64A/8MiB)、`EF4017`(W25Q64/8MiB)。ID 不识别 → OTA 禁用(既有功能不受影响)+UI 提示。

### 2.3 EEPROM 布局(AT24C02 256B)
```
0x00  BCB-A 64B  主控制块
0x40  BCB-B 64B  备控制块(seq 仲裁)
0x80  保留 127B
0xFF  0x55       现有初始化魔数,保持不动
```
BCB(64B,小端):
```
off size field
0    4   magic "ETBC"
4    1   schema_ver=1
5    1   state  0=IDLE 1=STAGED 2=APPLYING 3=TEST_BOOT 4=CONFIRMED 5=ROLLBACK
6    1   boot_try(初 3)
7    1   copy_phase  0=无 1=apply 搬运中 2=rollback 搬运中
8    2   seq         比较规则:(int16)(a-b)>0 者新;相等且双合法取 A
10   2   resume_block 断点续搬:**已完成读回验证**的 4KB 块数(下次从此块起重擦重写)
12   4   cand_addr / 16 4 cand_len / 20 4 cand_crc32 / 24 4 cand_vcode
28   4   cur_vcode(CONFIRMED 时同步=cand_vcode;ROLLBACK 完成时=backup_vcode)
32   4   backup_len / 36 4 backup_crc32 / 40 4 backup_vcode
44   12  pad 0xFF
56   4   reserved
60   4   crc32(前 60B)
```
- P0 安全写:逐 8B 页写+每页 ACK polling(≤10ms 超时)+全块读回比对;**单次事务=写非活动块(带 seq+1)→读回→通过后即生效**(活动块由 seq 仲裁决定,无二次改写)。boot/App 共用 `eeprom_bcb.c`。
- BCB 双块均坏:app CRC 有效 → 直接引导;否则恢复模式。镜像真伪始终以 fw_header SHA 为准。
- **外部槽自描述头(32B,置于各槽起始,P0 冻结)**:`magic "ETSL"(4)+slot_type(1)+pad(3)+payload_len(4)+payload_crc32(4)+vcode(4)+sha8(8)+commit_marker(4,写 0x434F4D54 表示完整)`——半写槽以 commit_marker 缺失判无效;**擦写序 marker-last**:先擦槽头扇区(marker 保持擦除态 0xFF)→写 payload/其余头字段并读回→最后单独写 marker,禁止复用旧 marker。镜像本体从槽起始+4KB 对齐处存放。
- **staging 接收日志(staging 槽头 4KB 页内,P0 冻结,BLE 断点续传唯一依据;页内完整偏移表)**:
```
0x000  ETSL 槽头(32B,§上文;staging 槽的 payload_len/crc 字段在包终验时随 commit_marker 一并填写)
0x020  (保留 32B,0xFF)
0x040  ETRJ 固定头(44B):magic "ETRJ"(4)+package_sha256(32B)+total_len(4)+hdr_crc32(4,仅覆盖前 40B 不可变前缀)
0x070  block_bitmap(64B=512 位,1 位=1 个 4KB 块;初始 0xFF,块落盘且读回验证后对应位 1→0;无 CRC——单调 1→0+写后读回保证)
0x0B0  (留白至 0xFFF,0xFF)
```
- **进度模型 = 纯整块位图(消除 NOR 可变值更新)**:跨复位持久化状态**只有整 4KB 块进度**;不足一块的接收进度仅存 RAM,断电/重连后该块整块重传(代价 ≤4KB)。**重传已部分写入的块前必须先扇区擦除,写完读回成功后方可清位图位**(R8 验收项)。包尾块按实际长度(total_len 定界)落盘置位。无 journal、无页内擦除;新会话(不同 package_sha256)才整页擦除重建。**写入次序**:ETRJ 固定头先写并读回校验→接收过程只动位图→包终验通过后 ETSL 的 payload_len/crc 随 commit_marker **最后单独写入**(R8 验收项)。
- 重连:package_sha256 匹配且 hdr_crc 合法 → 按位图续传(durable_off=自首位起连续 0 位块数×4KB,尾块按实长);否则整页擦除从零重传。**禁止以尾部 CRC 猜测进度**。

## 3. 镜像与升级包格式(字节级,P0 冻结)

### 3.1 fw_header(App 镜像内嵌 @app+0x400,96B,小端)
```
off size field
0   4   magic "ETFW"      4  4  header_ver=1
8   4   version_code      12 16 version_name(ASCIIZ)
28  4   build_ts(UNIX)    32 4  hw_rev=1
36  4   image_len(含头)
40  32  image_sha256
72  1   layout_id=1       73 1  min_boot_ver=1
74  18  pad 0xFF
92  4   header_crc32
```
- **位置 0x400 而非 0x200**:GCC 向量表实测 0x20C(X-Track.map `.isr_vector`),0x200 会覆盖末 3 个向量;0x400 同时是 VTOR 对齐边界。**`FW_HEADER_OFFSET=0x400` 为四方共享常量(linker/CI 注入器/boot 解析/recovery 校验唯一来源,P0 契约文档定义,全文其他数字引用一律以此为准)**。linker 定义专用 `.fw_header` 段 @ ORIGIN+0x400,并 `ASSERT(SIZEOF(.isr_vector) <= 0x400)` 防回归。
- **校验依赖消解(固定填充顺序,boot/CI/vectors 三方一致)**:
  1. `image_sha256` = 全镜像 SHA-256,计算时 **image_sha256 与 header_crc32 两字段均按全零参与**;
  2. 制包:构建含占位头 app.bin → 填版本/时间/长度/layout/min_boot → 算 SHA 回填 → 最后算前 92B CRC32 回填;
  3. boot 校验(擦 App 前统一执行):header_crc → image_sha(双零重算)→ hw_rev → layout_id==本机 → min_boot_ver≤boot 版本 → 向量表首项(MSP 初值落 RAM 区)与 Reset_Handler(落 app 区)范围合法。

### 3.2 .etu 容器(64B 头+payload,小端)
```
off size field
0   4   magic "ETU1"      4  2  header_len=64
6   2   flags  bit0=AES bit1=LZMA bit2=差分 bit3=全量(bit2/3 互斥)
8   4   alg_id=1          12 4  key_id(v1 恒 1,可换 key 递增)
16  16  aes_nonce         **CI 每包随机生成(修复现工具固定 nonce)**
32  4   payload_len       36 4  payload_crc32(加密后字节)← 传输/存储完整性早失败
40  4   target_vcode      44 4  base_vcode(差分基版;全量=0)
48  2   hw_rev            50 1  layout_id=1(分区布局代)  51 1  min_boot_ver=1
52  8   base_sha8(差分基版镜像 SHA-256 前 8B;全量=0)← 基准身份防"同版本码不同构建"
60  4   header_crc32(前 60B)
64  ..  payload
```
- 差分 payload = AES-CTR(bsdiff 工具输出经 `etu_pack.py` **规范化重写的 40B 内层头** + LZMA 流)。实测原生 `patch_header_t` 为 **40B 非 36B**(6×u32=24B + 5B props + **3B ABI 对齐填充** + u64=8B),且工具按宿主 sizeof 直写;打包器解析后重新序列化:逐字段显式布局、padding 显式置零、**ph_hcrc/ph_psize/ph_ocrc/ph_ncrc 为大端**、ph_osize/ph_nsize 小端、u64 原始长度小端,CRC 按规范化后字节重算;MCU 只认规范化头,按文档逐字段解析,禁 struct memcpy。
- 全量 payload = AES-CTR(**LZMA-Alone 形态**:5B props + u64 原始长度(小端) + LZMA 流)。**字典上限 16KB**(CI 制包固定 `-dict 16`;64KB 经 RAM 预算核算不可行,见 §9 内存表;差分包工具默认 4KB 字典实测已够);解压写回以 candidate 净容量做**溢出安全钳制**(offset+len 逐次检查,超限即中止置错)。40B 规范化内层头的逐字段精确 offset/CRC 覆盖范围表由 P0 契约文档冻结并入 golden vectors。
- AES 生产 key:CI Secrets → 打包器;固件 `ota_keys.c` 编译期注入不入库。**库内示例 key 仅限开发**。

### 3.3 golden vectors(P0 产出)
`tests/ota-vectors/`:toy-old/new.bin(4KB)、toy-patch.etu、toy-full.etu、expected.json(SHA+关键字段)。打包器/MCU 解析/Flutter 解析三方同 vectors 单测。

## 4. 升级状态机(端到端,断电任意点可恢复)

```
[App] 收包(BLE/SD→staging)
 → .etu 头 CRC+payload_crc32+hw_rev+**layout_id==本机+min_boot_ver≤当前 boot 版**+target_vcode>cur_vcode(降级拒绝)
 → 差分:base_vcode==cur_vcode 且 base_sha8==当前镜像 SHA 前 8B?→解密+解压+bspatch 流式合成→candidate(内层 ph_ocrc 二重兜底);全量:解密解压直写 candidate
 → candidate 全镜像 SHA-256 复核(fw_header 置零法)→不符即弃(BCB 不动)
 → 当前版自拷 backup(读回 CRC)→ BCB=STAGED → 提示重启
[boot] BCB 仲裁读(QSPI 每次事务前带超时探测,失败按 fail-closed 跳过外部槽分支)
 STAGED→复验 candidate 槽头(commit_marker+CRC)→BCB={APPLYING,copy_phase=1,resume_block=0}→**逐块**处理:擦该 4KB 块→写→读回验证→resume_block++ 持久化;**重启重入 APPLYING 时从 resume_block 继续,绝不再整区擦除**→全部完成→内部 fw_header 统一校验(§3.1 全项)→BCB=TEST_BOOT(try=3)→**先持久化 try--(首跳即消耗,共 3 次试启动)**→开 IWDG→跳 app
 TEST_BOOT→try>0:先持久化 try--再跳 app;try==0→ROLLBACK。**TEST_BOOT 期间 App 拒绝发起新 OTA**
 ROLLBACK→backup 槽头有效→BCB={ROLLBACK,copy_phase=2,resume_block=0 原子写}→同法逐块续搬→**完成后同样执行内部 fw_header 统一校验**→CONFIRMED(cur_vcode=backup_vcode);无效→recovery 槽→仍无效→恢复模式(按键≥3s;接收 recovery 资产,传输层验 len/CRC,**写完后启动前仍走 fw_header 统一校验——不绕过完整性/防错板/boot ABI;vcode 按 §5.3 物理 recovery 降级例外处理**)
[App] 自检过(HAL 全初始化+主循环 30s+IWDG 喂狗正常)→写 BCB=CONFIRMED(cur_vcode=cand_vcode)
```
boot 永不含 LZMA/bspatch(合成全在 App 侧),64KB 可控。**boot→App 交接冻结(P1 契约,字级)**:①NVIC 层面清源——`ICER[0..7]=0xFFFFFFFF` 禁全部外设中断、`ICPR[0..7]=0xFFFFFFFF` 清全部 pending,**另清 SCB->ICSR 的 PENDSTCLR/PENDSVCLR(系统级 pending)**(**不用 PRIMASK 屏蔽做跳转**);②SysTick CTRL=0、VAL 清零;③跳转前寄存器交接值:PRIMASK=0、BASEPRI=0、FAULTMASK=0、CONTROL=0(特权态+MSP);④`SCB->VTOR=0x08010000`→**DSB+ISB**→MSP=向量表[0]→**DSB+ISB**→跳向量表[1]。**双工程隔离断言**:boot 工程 VECT_TAB_OFFSET=0 且链接 ORIGIN=0x08000000;App 工程 `system_at32f435_437.c` 的 `VECT_TAB_OFFSET` **必须改为 0x10000**(实测 SystemInit:100 以 OFFSET=0 重写 VTOR,boot 设置会被覆盖;0x10000 为 0x400 倍数)且链接 ORIGIN=0x08010000——两侧各以链接 ASSERT+启动期自检(读 VTOR 与预期比对)双保险。**backup 槽锁定**:STAGED→CONFIRMED 期间不得重写 backup;下轮升级自拷仅在 CONFIRMED 态允许。

## 5. 传输通道

### 5.1 BLE 帧协议(FFF2 下行/FFF1 上行,透传 UART)

**顶层分流(demux,P3 落地)**:UART 收到 `A5 5A` 帧头进入二进制 OTA 处理器,其余字节走现有 TinyBTPlus 文本协议。**OTA 会话期间(BEGIN 成功→END/ABORT/超时)**:关闭文本回显、关闭 200ms `X-Trace\r\n` 周期上行(HAL_Bluetooth.cpp:67)、暂停调试透传——上行只允许 ACK/事件帧。

```
A5 5A | u8 cmd | u8 session | u16 seq | u16 len | payload | crc16-ccitt(cmd..payload)
cmd:0x00 GET_INFO{} → 0x80 INFO{model(8B ASCIIZ),hw_rev,layout_id,boot_ver,cur_vcode,image_sha256(32B),proto_ver,max_window_segs=32(恒 32,协议扩展预留)}
    0x01 BEGIN{proto_ver,total_len,package_sha256(32B),etu 头副本} 0x02 DATA{u32 off,data=128B(仅包尾段可短)} 0x03 END{sha 复核} 0x04 ABORT
    0x81-84 ACK;ACK 载荷={u8 status,u32 durable_off,u32 block_bitmap}
```
- **GET_INFO(升级前必查)**:APP 读设备身份(机型/硬件/布局/boot 版/当前 vcode/**完整 image SHA**)→ 上报 CF latest 选包(差分基准匹配则 patch,否则退 full),消除 Flutter 硬编码机型/0.0.0。GET_INFO 以 session=0 发送。
- **session**:BEGIN 由 MCU 分配返回(非零),后续 DATA/ACK/END 均携带;不匹配即丢弃。
- **durable_off**:MCU **已落盘 staging 且读回验证通过的整块进度**(4KB 粒度,包尾块按实长)——与 §2.3 位图严格一致;"已收未落盘"只反映在 ACK 的 block_bitmap,不推进 durable_off。
- **分段策略(冻结,消除跨块与 34×120 死锁)**:段净荷恒 **128B**,4KB 块=**恰 32 段**,段不跨块;唯一例外=包尾段(**off 仍 128 对齐,仅长度可短**)。off 非 128 对齐即 NAK。**对 durable_off 之前(已提交)offset 的重复 DATA 必须幂等:直接重发当前 ACK,不重写 staging**(R8 验收项)。
- **credit 窗口 = 当前块**:发送端在途段 ≤ 当前 4KB 块未确认段数(≤32);ACK 的 `block_bitmap`(u32)= durable_off 所在块的 32 段接收位图(bit i=块内第 i 段,已收=1);块收齐→落盘读回→位图 1→0 置位→durable_off 前移 4KB→窗口滑至下一块。缓冲恒 4KB 与窗口精确匹配,无 4080/4096 缺口。
- **活性规则**:①块收齐即落盘 ACK;②500ms 无新段→ACK 重发当前 block_bitmap(发送端据此补传缺段);③包尾块按 total_len 定界收齐即落盘。
- 断连重连:新 BEGIN 带同 package_sha256 → MCU 查 staging 接收日志(§2.3)合法则回 durable_off+位图续传;日志缺失/不合法/sha 不匹配 → 清 staging 从零重传。seq 16bit 回绕比较 `(int16)(a-b)`。
- Flutter 按协商 MTU-3 分片;MCU UART 环形缓冲 P0 定容 ≥4KB。
- 吞吐:115200≈8KB/s(603KB 全量 ~80s,差分几十 KB~10s);AT 提速后 3-4×。超时/重传 P3 实测标定(500ms 初值非契约)。

### 5.2 SD 通道(菜单改造)
"关于设备"→**"文件管理"**(复用 RouteSelect 框架,过滤 `.etu`)→选中→二次确认弹窗(现版/目标版对比)→读文件写 staging→同一状态机。

### 5.3 恢复资产与外部 flash 故障兜底
- **recovery 资产(统一定义,CI 每正式版产出)**:`recovery-vX.Y.Z.bin` = 最终 app.bin + 尾部 8B(image_len u32 + crc32 u32,小端)。J-Link 直刷或 UART-Ymodem 传输,boot 固定写 0x08010000。**两层校验职责分离**:尾部 len/CRC 仅为**传输容器校验**(判断收全没收坏);写入后**启动前仍强制执行 §3.1 fw_header 全项校验**(SHA/hw_rev/layout_id/min_boot_ver/向量范围)——recovery 不绕过防错板。**版本例外(显式声明)**:物理 recovery **允许降级**(不比较 vcode——救砖场景黄金镜像常旧于损坏的当前版;"防旧版误刷"保证的适用范围=OTA 通道,物理在场按键≥3s 的 recovery 不在其内)。J-Link 直刷用脚本剥离尾部 8B 后烧写(或直接烧最终 app.bin),不得把容器尾写入 App 分区。
- 外部 flash 故障(JEDEC 失败/坏块):v1 = UI 提示 + 上述 recovery 路径指引;BLE 直刷内部区列 v2 评估。

## 6. CI/CD 与 CF 后台

### 6.1 firmware-build.yml(v1.2 修订核心)
- **nightly(push master+paths)**:GCC 构建 → 仅上传 Actions artifact(14 天)。**不建 Release、不注册 CF**——D1 `UNIQUE(app_id,device_model,version_code)` 与 worker `FORMAL_RELEASE_REQUIRED`(firmware.ts:157)决定 nightly 注册不可行,显式放弃。
- **正式发布(workflow_dispatch)**:输入 version_name/version_code/notes → **GitHub environment `firmware-production` 保护(需人工审批)** → 校验 vcode>CF 现值 → **制包顺序(消解 fw_header 依赖)**:①构建含占位头 app.bin → ②`etu_pack.py --finalize` 回填 fw_header(SHA 双零法+CRC,§3.1 顺序)得最终 app.bin → ③以最终 app.bin 产 full.etu + patch.etu(基=上一正式版**最终** bin,从 R2/Release 取,记录 from_image_sha256)→ ④**bspatch 自验**:补丁应用于基版 bin,输出与最终 app.bin 逐字节比对(工具 exit code 恒 0,以 stdout+比对判定)→ ⑤产 recovery 资产 `recovery-vX.Y.Z.bin`(最终 app.bin+尾部 8B:len u32+crc32 u32)→ ⑥GitHub Release(full/patch/recovery 三资产)→ 复用 `mcu-firmware-release.yml` 链(R2+worker 注册,isFormalRelease=true)。
- paths 过滤与 Flutter build.yml 互不触发(已验证)。

### 6.2 CF 后台(v1.2.3 缺口重估)
- **已有勿重建**:worker latest/注册 API、R2 签名下载、**admin Pages Functions 固件列表/渠道/发布/回滚路由([[path]].ts:231-300)**、审计基础。
- **结构性缺口(P4,v1.2.3 升级为必做)**:
  1. **多资产模型**:现固件表每 release 仅一组 file_name/sha256/r2_key(0003 migration:14),latest 仅返回单下载地址(firmware.ts:100)→ 新增 D1 迁移 `firmware_release_assets`(release_id/kind∈{full,patch,recovery}/file_name/sha256/size_bytes/r2_key/base_image_sha256/base_vcode)。**唯一性(消 SQLite NULL 陷阱——UNIQUE 对 NULL 不去重)**:`base_image_sha256` 定义为 NOT NULL,非 patch 资产用固定哨兵空串 `''`,加 `CHECK(kind='patch' ↔ base_image_sha256≠'')`,唯一键 `(release_id,kind,base_image_sha256)` → 每 release 恰一 full/一 recovery、patch 按基版唯一。注册脚本与 latest API 改造为资产数组;recovery 资产**不自动分发**(仅 admin 手动下载)。**release-ready 原子门槛**:release 带 draft/ready 状态,D1 事务内校验`恰好一个 full 且全部资产 R2 digest 验证通过`才置 ready,渠道晋升仅接受 ready release,旧单资产数据迁移回填为 full。
  2. **差分选包数据流**:latest 增加 `currentImageSha` 查询参数;选包=存在 base_image_sha256 匹配的 patch 则返回,否则**自动退 full**;Flutter 升级前先 BLE GET_INFO 读设备真实身份(机型/hw/layout/boot 版/vcode/image SHA),替换硬编码机型与 0.0.0(ota_upgrade_page.dart:593)。
  3. 渠道停发开关 UI、发布/撤回 reason 必填、差分基版包保留策略、transport=ble 标注、R2 对象不可变验证、渠道晋升 D1 事务原子性验证。
- **"回滚"语义修正(消解与设备拒降级的冲突)**:后台动作更名为**撤回(retract)**——渠道指针退回旧版仅影响**尚未升级**的设备;**已升级设备无法降级**(MCU 严格拒绝 target_vcode≤cur_vcode),救治手段=发布更高 vcode 的修复版。admin UI 文案与 API 注释按此表述,能力边界写入操作确认弹窗。

### 6.3 Flutter(P3)
已有 ota_service(查询/下载/SHA)+页面;新增:BLE 帧层、进度/续传 UI、minAppVersionCode 兼容提示。

## 7. 首次部署(J-Link bootstrap,一次性)
1. 烧 boot.bin @0x08000000;2. 烧重链接 app.bin @0x08010000(ORIGIN=0x08010000/LENGTH=960K,VTOR 由 boot 设);3. boot 首启见 BCB magic 无效→自动初始化 CONFIRMED(cur_vcode 读自 app fw_header);4.(可选)写 recovery 槽。此后全走 OTA;AC5 工程仅本地对照,**OTA 产物一律 GCC**。

## 8. 实施阶段(P0 硬门槛)

| 阶段 | 内容 | 验收 | 估时 |
|---|---|---|---|
| **P0 契约+基建** | 五契约字节级成文 `docs/ota-binary-contracts.md`;`tools/etu_pack.py`/`etu_unpack.py`;golden vectors;EEPROM 安全写(页/ACK/超时/读回);QSPI API 超时+错误返回;自检 CONFIG 默认关;JEDEC 判定;**R4 五条固化约束**(①ROLLBACK 首转原子写 copy_phase=2+resume_block=0 ②layout_id/min_boot_ver 拒绝规则入 §4 契约与 vectors ③槽头 marker-last 擦写序+BLE 收包中复位的会话恢复二选一策略 ④活跃窗口≤聚合缓冲实际容量+溢出处理 ⑤CI 明确基版 raw bin 来源+J-Link recovery 脚本剥尾) | vectors 三方一致(含 seq 回绕/相等场景);EEPROM/QSPI 压测 1000 次零错;**R4 五条全落文,遗漏任一重新阻断 P1/P2** | 3d |
| P1 bootloader | 64KB boot;linker 双份;bootstrap 文档 | 注错试验(候选 CRC 坏/搬运断电/三连失败)全回滚;断电矩阵 20 点 | 5-7d |
| P2 MCU App | staging 写入、.etu 解析(按文档,禁 struct memcpy)、bspatch 三函数集成、SD 文件管理页+二次确认、backup 自拷 | **P0 打包器产物**真机 SD 升级闭环 | 4-6d |
| P3 BLE+Flutter | MCU 帧层(滑窗/续传)、Flutter 传输+UI、AT 提速实测 | 真机 BLE 闭环;断连×10 续传成功 | 5-7d |
| P4 CI/CF | firmware-build 修订、fw_header 回填、CF 缺口(§6.2 三组) | 正式发布→推送→BLE 升级全链演练;**D1 迁移以实际 SQL 约束验证"每 release 恰一 full"(插入第二个 full 必须被拒)**(R8 验收项) | 2-3d |
| P5 联调 | 双通道回归、故障注入矩阵、文档 | **注入点=每个持久化提交点/擦写/窗口 ACK/重连**,每例输出状态轨迹+最终版本哈希+"可启动或进恢复"二判;弱信号/低电/满 staging/降级/坏包/错板全过 | 3-5d |

## 9. 风险与开口项
- **升级态峰值内存预算(P2 实测验收,R6-4 闭环)**:App 总 RAM 384KB,常态占用 82.96%(≈319KB,余 ~65KB)。升级独占页(关闭 LiveMap/地图行缓存等大页面)预计释放 ≥30KB。升级态预算:LZMA 字典 16KB + LZMA 解码状态 ~16KB + bspatch 堆 ~20KB + BLE/staging I/O 缓冲 4KB + 栈余量 4KB ≈ **60KB ≤ 65KB 常态余量**(不动用释放量即可行,释放量作安全垫)。P0 在契约文档中列各分配来源(堆/静态池),P2 以 StackInfo+堆水位实测回填;若实测超限,字典降 8KB(制包端同步)。
- BLE 吞吐待实测,协议已留提速参数位。
- recovery 槽启用与否 P1 按坏块率定。
- **boot 单级不可变**:v1 接受(家用单台+J-Link 在手+boot 仅"校验/搬运/回滚"极简);现场 boot 缺陷=J-Link 重刷。二级 boot A/B 不做(空间不允许),风险留档。
- v2 项:Ed25519 签名、外部 flash 故障 BLE 直刷、A/B 无缝升级(不做)、CI OIDC 短期凭证+Action 摘要固定、CF 分阶段灰度。
