# P3-3 v5 重制包与受控服务 fixture 切换 —— 2026-09-14

> 依据：修复轮整体授权（用户 2026-09-14 批准：O2 缺陷修复 `1894f9d` → 重建 →
> finalize 烧板 → BCB 恢复 r2 → **重制包** → 合同升 v5 重冻结 → O 序列重跑）
> + 同批恢复轮授权（「授权，此外你说的超授权问题也一并授权」）。
>
> **性质**：离线制包 + 宿主受控服务 fixture 切换。零真机操作（未连 J-Link、
> 未读写设备/BCB/App 区）、零云端写入（D1/R2/CF 生产后台未动）、零产品代码
> 改动（唯一 tracked 改动 = `service_config.json` fixture 身份）。
>
> 前置：板上 3.2.0-fixed App(30200) + 生产 Boot（全区原样）+ BCB
> CONFIRMED/30200（恢复轮 r2 终态，S5 快照 app_sha256 与 finalize 头
> image_sha256 `24fc02ea…728126` 全等）。

## 1. 源镜像 provenance（为什么必须重制 + 源身份）

- **源镜像**：`.cache/bg/app-gcc/X-Track-App-GCC.bin`（`1894f9d` 的 GCC 构建，
  603,764 B，SHA-256
  `4b16048f5970c9cef924690a62031e232cd1d2fb8c1b8af85c18993cfdf830ec`）。
- **身份链闭合**：该 bin 与 3.2.0-fixed finalize 镜像（`d7cc4194…a38e488`）
  仅差 0x400-0x45F 头区（主执行笔记 §16.4 逐字节核验）；板上 S5 快照 SHA
  与 finalize 头 image_sha256 `24fc02ea…` 全等 → **该 bin 即当前板上运行
  3.2.0-fixed（含 O2 修复）的本体**。
- **为什么旧 v4 资产不能沿用**：旧 toy/真包源 = `7328c1b1…`（O2 缺陷版
  3.2.0，未含 `session_handle_end` 的 BCB STAGED 提交+复位）。按资产方案
  §2.3，板上(30200)→toy(30201)→真包(30202) 是同源升级链三环：O2 重跑若
> 下载旧 toy，升级后接收端固件退回缺陷代码，O3（真包升级）必然复现
> REBOOT_RECONNECT_FAILED。**toy 与真包都必须从修复版源重建**。
- 固件无需再次重建：`1894f9d` 的 GCC 构建已存在（`.cache/bg/app-gcc/`），
  且其 finalize 产物已烧板并经恢复轮 r2 验证。

## 2. 密钥路径（如实记录，与原轮一致）

- 封包密钥 = 开发密钥（vendor 教科书示例 key），key_id=1
  （`etu_pack.py DEFAULT_KEY_HEX = 2b7e1516…`，与固件 `ota_keys.c` key_id=1
  一致）。制包命令未设 `OTA_AES_KEY` 环境变量，两包各出现一次预期
  `[warn] OTA_AES_KEY 未设，使用 vendor 示例 key` 行。

## 3. 制包命令与工具身份

```
# 两份资产各自从 pre-finalize 源副本出发（避免头污染），源副本复制自 bg 构建原件
python Tools/etu_pack.py finalize \
  --app .cache/p3-3-assets-v5/toy-3.2.1-pre-finalize.bin \
  --out .cache/p3-3-assets-v5/toy-3.2.1-30201-final.bin \
  --ver-name 3.2.1 --build-ts 1789387723 --hw-rev 1 --layout-id 1 --min-boot 1

python Tools/etu_pack.py pack-full \
  --app .cache/p3-3-assets-v5/toy-3.2.1-30201-final.bin \
  --out .cache/p3-3-assets-v5/toy-3.2.1-30201-full.etu --target-vcode 30201

python Tools/etu_pack.py finalize \
  --app .cache/p3-3-assets-v5/real-3.2.2-pre-finalize.bin \
  --out .cache/p3-3-assets-v5/real-3.2.2-30202-final.bin \
  --ver-name 3.2.2 --build-ts 1789387723 --hw-rev 1 --layout-id 1 --min-boot 1

python Tools/etu_pack.py pack-full \
  --app .cache/p3-3-assets-v5/real-3.2.2-30202-final.bin \
  --out .cache/p3-3-assets-v5/real-3.2.2-30202-full.etu --target-vcode 30202
```

finalize 参数沿用 P3-2 板上 3.2.0 与原轮同款口径（`--hw-rev 1 --layout-id 1
--min-boot 1`）；build_ts 取制包时刻（两份同为 `1789387723`，2026-09-14 20:0x）。

| 工具 | git blob SHA-1（本轮 `git hash-object` 实测） | 最后修改提交 |
| --- | --- | --- |
| `Tools/etu_pack.py` | `8a413ed35914801006b734eb673347b20c1dccc3` | `d2c851a`（2026-07-25） |
| `Tools/etu_unpack.py` | `86409ec3756388690e41bd375a8998829b2079b7` | — |

与原轮（P3-3-offline-assets-2026-09-13.md §3）登记的工具身份完全一致，
工具零改动。

## 4. 资产身份四元组（两份分开记录，不混用）

| # | 项 | toy 3.2.1（30201） | 真包 3.2.2（30202） |
| --- | --- | --- | --- |
| 1 | pre-finalize 源 SHA-256 | `4b16048f5970c9cef924690a62031e232cd1d2fb8c1b8af85c18993cfdf830ec`（603,764 B） | 同左（同一源镜像，两份独立副本） |
| 2 | 最终完整镜像 raw SHA-256 | `aeafc96e77d372aea1e893a979f2368ba9176c4999a61090ceb2956cd4085298`（603,764 B） | `ab0585f71b9a523863b582e8ed4cc47a279bf6e57c4a1038635593306746ab7e`（603,764 B） |
| 3 | fw_header 双零摘要 | `9d7a3cdca4f8612908a13c538796cddcb9bb0e27c8b3d06ae21769dcbe123371` | `c57eb4cbd5d903b67f443f60daf82d5463008fc9d5146fd89333a9d854773ff0` |
| 4 | ETU 包 SHA-256 / size | `0219899dd993f61f2c75eaec7002bc9c24e0fc629a60e87046e74266d55410c5` / 284,540 B | `0c8ae468948d8e85af0e8eaf3ec52e046f1b6a3cdba88f9bd8478790f0590f6f` / 284,573 B |

- ETU 外层属性：toy `target_vcode=30201 flags=0x000b key_id=1
  nonce=4d3bfb84015032a9af2610930ef3782f`；真包 `target_vcode=30202
  flags=0x000b key_id=1 nonce=f2daa90ed2056608e0a0ef2b5e20330e`。
- fw_header crc32（头前 92B）：toy `0x138BA318` / 真包 `0xACFD2124`。
- **口径说明**（与原轮 §4 表格同构）：finalize 工具 stdout 打印的
  `image_sha256=` 行 = **整镜像 raw SHA**（对应本表第 2 行）；头内
  off40..71 域值 = **双零摘要**（对应第 3 行，独立复算相等）。二者是
  两个不同字段，登记时不得混用。

### 4.1 规范文件名（OTA-XC-ASSET-NAMING，沿用冻结规则）

| 资产 | 规范文件名（登记/R2 键用） | size | SHA-256（同第 4 节第 4 行） |
| --- | --- | --- | --- |
| toy 3.2.1 | `e-track-at32f435-v3.2.1-full.etu` | 284,540 B | `0219899d…d55410c5` |
| 真包 3.2.2 | `e-track-at32f435-v3.2.2-full.etu` | 284,573 B | `0c8ae468…0590f6f` |

规范名副本已补齐并核对与原始产物逐字节一致（cmp 全等，文件名是登记键
元数据、不改包字节）。配套身份：toy releaseTag=`mcu-e-track-at32f435-v3.2.1`、
真包 `mcu-e-track-at32f435-v3.2.2`（云端登记获准时使用；当前云端写入
B0-B4 仍暂停）。

**GET_INFO 终点比对标准 = 表第 2 行（最终完整镜像 raw SHA）**——v5 合同
C-TOY-LOOP 绑 `aeafc96e…`，C-REAL-LOOP 绑 `ab0585f7…`（各自终点核对，
互不替代；同时取代 v4 合同中的旧值 `43ee943a…`/`c9582213…`）。

## 5. 离线验证结果（verify_v5.py 全 PASS，rc=0，报告落盘）

验证脚本 `.cache/p3-3-assets-v5/verify_v5.py`、完整输出
`.cache/p3-3-assets-v5/verify_v5_report.txt`。判据复刻原轮 §5 全表：

| 验证 | toy 30201 | 真包 30202 |
| --- | --- | --- |
| pre-finalize 副本 == bg 构建原件（`4b16048f…`） | PASS（逐字节相等） | PASS |
| finalize 与 pre-finalize 差异范围 | 仅 0x400..0x45F（78 字节），本体零差异 | 同左 |
| fw_header 头字段独立解码（magic=ETFW/header_ver=1/vcode/version_name/build_ts=1789387723/hw_rev=1/layout_id=1/min_boot=1/image_len=603764） | 全部 PASS | 全部 PASS |
| 双零摘要独立复算（0x400+40..71、0x400+92..95 置 0 后整镜像 SHA-256 == 头内 off40..71 域值） | PASS（`9d7a3cdc…`） | PASS（`c57eb4cb…`） |
| header_crc32 独立复算（zlib.crc32 头前 92B == 头内 off92..95 LE 域值） | PASS（0x138BA318） | PASS（0xACFD2124） |
| `etu_unpack.py --verify-fw-header` | OK（candidate_len=603764、target_vcode=30201、image_sha256 与封包一致） | OK（target_vcode=30202、同左） |
| candidate 与 finalize 镜像逐字节比对 | **一致** | **一致** |
| 规范名副本与原始产物逐字节比对 | **一致** | **一致** |
| `ota_backup.c:410` 升级检查模拟 | 30201 > 板上 30200 ✔ | 30202 > toy 后镜像 30201 ✔ |

补充核查（本轮新增判据）：

1. **toy 与真包两份最终镜像之间仅 38 字节差异，全部位于 0x408..0x45F**
   （fw_header 内 vcode/version_name/双零摘要/CRC 等版本身份字段）——
   与原轮完全同构，两资产功能本体逐字节相同，版本身份是唯一区分。
2. **板上 3.2.0-fixed 与新 toy 本体逐字节同源**：差异 41 字节全部位于
   0x408..0x45F 头身份字段（vcode/build_ts/摘要/CRC），功能本体零差异——
   O2/O3 升级烧写的镜像与当前板上运行代码本体一致，仅版本身份不同，
   排除「升级后本体回退」风险。

## 6. 落盘位置与可复现性边界

- 新产物全部在 admission worktree 项目内被忽略目录
  `.cache/p3-3-assets-v5/`，共 12 文件：2×pre-finalize、2×final、2×etu、
  2×规范名副本、2×verify-candidate、`verify_v5.py`、`verify_v5_report.txt`。
- **旧 `.cache/p3-3-assets/`（v4 轮 8 文件）原样保留不动**——v4 冻结包证据
  完整性所需；其四元组仍按原轮登记，不因 v5 作废而清理。
- **最终镜像可确定性复现**：pre-finalize 源 SHA + ver-name + build-ts +
  finalize 参数 → 输出逐字节确定，本文四元组可独立复核。
- **ETU 实物不可从文档复现**：pack-full 的 AES nonce 每包随机。v5 两份
  ETU 是唯一实物——服务 fixture 与未来云端登记一律使用该实物且 SHA 对应
  本表第 4 行；若丢失重打包，ETU SHA 变化须重新登记并重走资产核对
  （最终镜像 SHA 不变）。

## 7. 受控服务 fixture 切换（宿主操作，已执行并验证）

- **配置改绑**：`Tools/ota/p3-3-service/service_config.json` 两个 release 的
  `targetImageSha256`、`asset.sha256/sizeBytes/path` 改绑 v5（路径指向
  `.cache/p3-3-assets-v5/`），`releaseNotes`/`_comment` 同步指向本文档。
- **服务换启**：先按 PID 精确核验并停止旧实例（PID 23040，17:01:54 起，
  供旧 toy `fc4ae5a9`，其期间 O1/O2 请求日志完整保留于
  `service-r4-20260914.log`），再脱离托管起 v5 实例（20:21:05 起，
  PID 22316，`--active-release toy-30201`，r4 隧道域名
  `describing-substance-databases-past.trycloudflare.com` 不变）。
- **启动横幅**（`service-v5-restart.stdout`）：双 fixture 逐字节核验通过
  ——`real-30202:e-track-at32f435-v3.2.2-full.etu:284573:0c8ae468948d,
  toy-30201:e-track-at32f435-v3.2.1-full.etu:284540:0219899dd993`
  （失配拒绝启动的 fail-closed 语义下，即资产身份成立）。
- **本机 `/latest` 验证**：200，`updateAvailable=true`，
  `versionName=3.2.1/versionCode=30201`，
  `targetImageSha256=aeafc96e…`，asset `0219899d…/284540`，签名 downloadUrl
  指向 r4 隧道域名。
- **公网隧道全链路验证（App 实际链路）**：经隧道域名 `/latest` 200 同身份；
  再经其签名 downloadUrl 下载得 284,540 B，SHA-256 `0219899d…`，与本地
  实物逐字节全等（探针落盘 `.cache/p3-3-v2-service/v5-download-probe.etu`）。
- 请求日志：`.cache/p3-3-v2-service/service-v5-20260914.log`。

## 8. 后续（已授权修复轮计划衔接）

1. **本证据批次提交**（恢复脚本参数化 + 恢复/重制留证 + 台账 + 服务配置
   + 看板回写）→ 作为 v5 合同 `freeze_commit` 候选。
2. **合同升 v5 重冻结**：task_id 不变、版本加一、`parent_contract_sha256`
   绑 v4 `4AABC513…`；EXT-HTTP-TEST-SERVICE 改绑 v5 服务事实（新 fixture
   身份 + v5 实例），C-TOY-LOOP/C-REAL-LOOP 绑新四元组第 2 行，
   C-RELEASE-BUILD/C-APK-INSTALL 绑第五轮 APK（r4 endpoint 注入，在装）。
3. **O 序列重跑**：O2 toy 升级复测（当前服务已供 v5 toy，直接可用）；
   O3 切真包按操作单以 `--active-release real-30202` 重启服务；D4 只停
   服务不动隧道。O1 因 fixture 身份变化（targetImageSha256/asset sha 变），
   按 v5 rerun plan 判定重测范围。
4. O 序列执行需用户手机侧配合，届时按操作单协调。

## 9. 边界声明

- 零真机操作：未连 J-Link，未读写设备、BCB、App 区、QSPI 槽。
- 零云端写入：D1/R2/CF 生产后台未动；受控测试服务为宿主本地进程 +
  Quick Tunnel 转发，属既有 B 路线授权范围内的宿主操作。
- 零产品代码改动：固件/App 源码零变化；唯一 tracked 改动为
  `service_config.json`（fixture 身份，v5 合同将重绑其指纹）。
- 全部制包/验证/服务命令在 admission worktree 项目内执行，产物落项目内
  忽略目录。执行中一次 cwd 漂移（服务换启命令后 shell 停留服务子目录，
  相对路径 `cat` 落空报 No such file）即时发现并以显式 `cd` 纠正，
  未产生任何项目外写入（该次 cat 为只读且未命中任何文件）。
