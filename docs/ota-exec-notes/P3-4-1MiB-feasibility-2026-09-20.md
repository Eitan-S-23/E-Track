# P3-4：1 MiB 合法 ETU 可行性验证（2026-09-20）

本会话承接 2026-09-19 中断的 host 研究。目标是实际验证完整 ETU 能否达到
1,048,576 字节，并交付可复现方法；P3-4 仍为进行中，Claude 的实现认领不变。
本记录不构成正式验收、真机准入或设备操作授权。

## 开工依据与待验证方案

- OTA-XC-BLE-TUNING 冻结 referencePackageBytes=1048576，指完整合法 ETU。
- 二进制合同 §0.5：ETU 上限 0x180000；目标镜像上限 0xF0000。
- 差分解码器要求 decoded_size = image_size + 24 * control_groups，
  且 1 <= control_groups <= image_size。镜像长度上限不直接等于差分流上限。
- 使用冻结 P3-3-v9 的真实 v3.2.4 / v3.2.5 镜像，保持每个镜像字节不变。
  先测试有输出进展的合法控制分段，再用真实 ota_patch_apply 和 Boot 校验器验证。
- 不追加解析器忽略的字节、不使用空操作凑长度，不修改冻结大小或产品代码。
  非最短编码是否适合正式测量，与格式可达性、真机准入分别记录。
- 本仓库无 .trellis/、prd.md、design.md、implement.md；按 before-dev 读取根规范、
  看板、二进制合同、跨系统条款及既有 host 测试入口。

## 输出与保护边界

唯一活动根：D:\github\my\E-Track。
新输出：.cache/p3-4-size-check-20260920/（scripts、cases、bin、logs、proof、tmp）。
旧 .cache/p3-4-size-check-20260919/ 和 host-audit-20260919/ 只读。
TEMP/TMP/TMPDIR 及编译器临时产物固定在新输出的 tmp/。
实现 worktree 只读；已有改动的基线哈希保存在新输出 baseline.json。

## 当前结果

**完整合法 ETU 可以恰好达到 1,048,576 字节。** 本轮生成了实际 PATCH 包，
用未修改的真实 `ota_patch_apply()`、AES/LZMA 及 Boot 头/摘要/向量校验代码在
host 执行，合成的 603,764 字节逐字节等于冻结的 v3.2.5 镜像。
随后以相同编码参数和新随机 nonce 独立重生成，再次得到相同长度并通过同一真实解码器。

这是格式与现有解码实现的可达性证明，不是 P3-4 完成、真机准入或独立验收 PASS。
它也没有证明 FULL 包可达 1 MiB。旧两个 FULL 样本的最大值 996,536 字节仍只是样本值，
不能据此断言所有合法 ETU 不可达，不能修改冻结的 `referencePackageBytes`。

## 1. 输入身份

源码根为本主工作树；HEAD `ba8675b194e99e478f02b7731ebd9ce6a216da62`。
产品源码未修改，未进入实现 worktree 写文件。实际参与构建/解释的文件逐一绑定
在 `.cache/p3-4-size-check-20260920/proof/build-v1.json`，并在验证/复现前重算核对。

输入均来自 `docs/acceptance-contracts/P3-3-v9/artifacts/` 的既有真实 FULL 包；
只读解包，不重建固件，不改变镜像内容或版本号。

| 身份 | 基版 | 目标 |
|---|---|---|
| 文件 | `e-track-at32f435-v3.2.4-full.etu` | `e-track-at32f435-v3.2.5-full.etu` |
| 版本码 | 30204 | 30205 |
| 镜像字节数 | 603764 | 603764 |
| 完整镜像 SHA-256 | `43faf0cac092f54d862a4266e661fbf739db973a224180744d85c0169ff3fc13` | `ab8528ecb8c4bc756dc2d12fddeb2eb454fa3c91472129f1881edecdff2bcfb4` |
| 输入 ETU SHA-256 | `81a773363711adff31cd788217ba18445b462e675042682bdd22302123f0228b` | `32577aa5d0d98cab071440b455151bcc536f33a9a9d930e832f8bb140a607d77` |

基版与目标分别经真实 `boot_fw_header_validate()` 返回 `ok`。正例合成结果又经过
`ota_patch_apply()` 内部验证以及 harness 的直接 Boot 校验、全镜像 `memcmp`。

## 2. 编码方法与完整字节账

该包采用**有意非最短的合法差分编码**，不是仓库默认 vendor `bsdiff.exe` 的输出。
只改变表示同一对真实镜像的控制分段与基版读取位置；没有补零扩容固件、空操作组、
容器尾部填充或被解码器忽略的数据。它用于尺寸可达性和潜在压力资产研究，
不能被描述成普通高效发布差分包。

固定参数：`count=212295, seed=1931, salt=18`。

1. 前 212,295 组各输出 1 个真实目标字节。每组为 `(diff_len=1, extra_len=0, seek=z)`；
   diff 字节为 `(target[i] - base[oldpos]) mod 256`，下一次基版读取位置由确定性生成器给出。
2. 位置生成器为 `state=(1664525*state+1013904223) mod 2^32`，`nextpos=state % base_len`。
   最后 8 个前缀组将位置改为 `(nextpos + salt*(i+1)*7919) % base_len`。
   控制字段 `z=nextpos-oldpos-1`，按冻结的 64 位 sign-magnitude 形式编码。
3. 最后一组为 `(1, 391468, 0)`：先按最后一次 seek 读取基版并输出 1 个目标字节，
   再输出剩余目标字节为 extra。这样最后一次 seek 也实际参与输出，不是无用位置调整。
4. 使用原 `etu_pack.lzma_alone_encode()`：16 KiB 字典，`lc=2, lp=0, pb=0`；
   `MODE_NORMAL / MF_BT4 / nice_len=64 / depth=0`。内层保存 5 字节 props，
   只将 Alone 头之后的真实 LZMA 流放入 PATCH payload。
5. 复用 `normalize_patch_header()`、`aes_ctr_xcrypt()`、`build_etu_header()` 和
   `check_limits()` 生成正常规范化内层头、AES-CTR 密文和外层头。使用仓库公开开发
   fixture 密钥；每次封包都取新的 OS 随机 nonce，不输出密钥，不复用固定 nonce。

| 项目 | 实测字节数/数量 |
|---|---:|
| 控制组 | 212296 |
| 控制字节 | 5095104 |
| diff 数据 | 212296 |
| extra 数据 | 391468 |
| LZMA 解码后总长 | 5698868 |
| LZMA 压缩流 | 1048472 |
| 规范化内层头 | 40 |
| 加密 payload | 1048512 |
| ETU 外层头 | 64 |
| **完整 ETU** | **1048576** |
| 未消费的解码字节 | **0** |
| 每组最少实际输出字节 | **1** |

关键等式：`603764 + 24*212296 = 5698868`，满足设备要求的
`1 <= control_groups <= image_size`；`64 + 40 + 1048472 = 1048576`。
所有 diff 引用均在真实基版界内；完整 LZMA EOS、压缩输入消费量和控制流消费量均检查。
`selftest.py:account()` 独立遍历实际 raw 流做字节账，不以生成器自报代替。

已测 75 个唯一编码，日志保留在 `logs/measure-*.json`。搜索预算为 128 个候选，
不依赖扩大随机试验来证明上界；找到实际见证后停止。定位完成后无需重跑搜索。

## 3. 实物与哈希

证据根：`.cache/p3-4-size-check-20260920/`。

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `cases/reference-1MiB.etu` | 1048576 | `131624717d5972039ee76847d4a410fc21edebf9a5b4730d37b9dfe2ab04573e` |
| `cases/reference.raw-patch` | 5698868 | `3f74b06deb52aecfeb3d479d3e1fd6f7d6422a4b96a4bc39c824f6847ba5b083` |
| `cases/reference.lzma` | 1048472 | `4c9105258980c19c942e2de7d40c2afbaac22a21e8d336652aa4f36ed7fab51c` |
| `cases/reproduced-r2.etu` | 1048576 | `e444644a979910290afd0f8bf412f231c3ab6dabc7e5c4fac7ea4d7388bc32cb` |

两个 ETU 的密文摘要不同是新 nonce 的正常结果；实际验证其压缩明文完全一致、
总长相同、目标镜像完全相同。不能把这解释成未经控制的不可复现问题。

主要机器证据：`proof/inputs.json`、`selection.json`、`witness.json`、`build-v1.json`、
`validation-r1.json`、`generator-selftest.json`、`control-byte-accounting.json`、
`reproduce-r2.json`；命令、退出码、stdout/stderr 见 `logs/`。

## 4. 实际验证

宿主工具链：MinGW GCC 15.2.0，`-std=c99 -Wall -Wextra -Werror -O2`。
两个宿主程序编译均 **0 errors / 0 warnings**。没有重建 GCC MCU 或模拟器，
不把这个数字覆盖历史实验固件的 459 warnings。

`patch_host.c` 只替代 package/base/candidate 存储回调和 workspace 获取；
真实参与链接的是 `ota_patch.c`、`ota_keys.c`、`LzmaDec.c`、AES、CRC、SHA 和 Boot 校验代码。
宿主内存数组代表 Flash 内容，不是对 MCU RAM 开销的完整模拟。

| 检查 | 实际结果 |
|---|---|
| 基版 Boot 校验 | `ok` |
| 目标 Boot 校验 | `ok` |
| 1 MiB 正例 | `ota_patch_apply=ok`；全镜像逐字节一致；Boot/guard/workspace 生命周期通过 |
| 密文翻转 1 bit | `payload_crc`，candidate 未准备/未写 |
| 截断 1 字节 | `package_length`，candidate 未写 |
| 错误真实基版 | `base_sha8`，candidate 未写 |
| 错误 payload 长度 | `package_length`，candidate 未写 |
| 流尾新增字节并重算各层长度/CRC | `lzma_data`，candidate 未写 |
| 声明长度之外另有解码输出 | `decoded_length`，candidate 未写 |
| 首控制组改为 `(0,0,0)` | `patch_control`，candidate 准备后零写入 |
| 将比较目标改错 1 字节 | 解码仍 `ok`，但全镜像比较失败，harness **exit=1** |

以上 11 项均符合预期。最后一项证明 harness 不会只看到解码器返回 `ok` 就报告通过。
另有生成器 11 项 unittest 全通过，覆盖 count/salt 边界、sign-magnitude、消费量、
EOS/截断、无进展控制、输出路径拒绝和语法；固定参数重生成 1 次也通过真实 C 校验。

正例 host 观测：`workspace_peak=34136`，`programmed_bytes=603764`，
`program_calls=212679`，`max_write=1024`，`base_reads=212886`，`package_reads=4609`。
34,136 是本次 **host ABI** 的工作区观测，不是新增 MCU 实测内存证据。
212,679 是 candidate 回调次数，不等于已实测的物理 Flash 写入次数或耗时。

## 5. 复现入口

所有命令从 `D:\github\my\E-Track` 用 `cmd.exe` 执行，不启动 PowerShell。
运行前对实际输出及其父链重新做路径预检。原见证和日志只读保留。

最快复现（本轮已以 `r2` 执行成功；再次运行必须选未使用的 label）：

```bat
python -I -S -X utf8 -B .cache\p3-4-size-check-20260920\scripts\reproduce.py --label r3
```

该命令读取已固定的选择参数，不搜索；重新编码、校验明文摘要、使用新 nonce 封包、
生成 `cases/reproduced-r3.etu`，然后运行已绑定哈希的真实 C 解码器，日志与结果保存到
`logs/reproduce-r3.json` 和 `proof/reproduce-r3.json`。保留 `r2`，不得覆盖原见证。

本轮实际执行的开发命令（以下是记录，已存在的证据文件不会被工具静默覆盖）：

```bat
python -I -S -X utf8 -B .cache\p3-4-size-check-20260920\scripts\size_proof.py measure 65536 131072 196608
python -I -S -X utf8 -B .cache\p3-4-size-check-20260920\scripts\size_proof.py search --budget 128
python -I -S -X utf8 -B .cache\p3-4-size-check-20260920\scripts\host_validation.py build --label v1
python -I -S -X utf8 -B .cache\p3-4-size-check-20260920\scripts\host_validation.py validate --build v1 --label r1
python -I -S -X utf8 -B .cache\p3-4-size-check-20260920\scripts\selftest.py
python -I -S -X utf8 -B .cache\p3-4-size-check-20260920\scripts\reproduce.py --label r2
```

Python 依赖沿用本机已安装的 PyCryptodome 与标准库 lzma；未安装新依赖。
模板并非任意项目通用工具，活动根与输出根被刻意锁定。跨目录移植必须重新预检并
绑定实际源码/工具链，不修改路径守卫来绕过项目边界。

## 6. 给实现会话的方法与剩余门槛

1. 撤回“冻结规格下所有合法 ETU 无法达到 1 MiB”的结论，引用本轮实物与真实解码证据；
   保留旧 FULL 样本作为当时观测，不改 `referencePackageBytes=1048576` 或吞吐公式。
2. 若需要复现尺寸方法，直接使用 §5 的 `reproduce.py`，或审查并移植
   `size_proof.py:patch_stream()` 与既有封包函数的组合，不再跑随机 FULL 扩样。
   当前 `count/seed/salt` 只对这里绑定的两个镜像和编码器输入有效，不是任意基版的通用参数。
3. 进入正式实验前单独审查这份**非最短压力编码**是否适合 reference 资产。
   它增加解压量和小块 candidate 写回调，不能隐藏这些代价、混用普通差分成绩，
   也不能将 host 的成功转换成吞吐、可靠性或 MCU 应用时间结论。
4. 本包严格绑定基版 **v3.2.4 的完整镜像身份**和目标 v3.2.5。
   必须待获授权 B1 核对实际设备基版；若设备已经是 v3.2.5 或其他构建，不能直接使用，
   更不能为迁就研究包擅自降级。应以实际基版及获批准的新目标重新制包和离线验证。
5. 本证据不修复先前 host 复核中的实验/恢复镜像 finalize、AT 原始字节观测、busy/epoch
   隔离、UART TX 隔离、速率转换与恢复操作单问题；这些仍按既有整改指令继续实施。

参考包真机准入、B1-B5、S1-S7、R1-R6、OTA throughput/reliability campaign、
独立验收均保持 **NOT_RUN**。没有连接设备、发 AT、J-Link、安装、烧录、OTA、
CI dispatch、commit/push、release/deploy 或远端删除。

## 7. 保护与写入审计

开工保护集 399 个既有文件在回写本报告/看板前逐一哈希核对，无变化。
旧 size-check-20260919 输出、产品源码、现存脏文件与冻结包不作改写；
看板仅追加本次研究记录并保留原认领、状态、既有文字与混合行尾。
新脚本、包、编译物、日志及编译临时文件均限定在本项目新证据目录。
最终清册/复核结果见 `proof/SHA256SUMS.json` 与 `proof/final-audit.json`。
