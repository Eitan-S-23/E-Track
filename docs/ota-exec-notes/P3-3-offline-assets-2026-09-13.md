# P3-3 离线资产准备执行记录：toy 3.2.1(30201) / 真包 3.2.2(30202) —— 2026-09-13

> 依据：用户 2026-09-13 分项批复第 5 条——资产准备现在推进离线准备，不必等
> 正式 FROZEN；允许同一合格生产镜像经正式 finalize/pack 工具生成两个不同
> 版本的受控资产；分别记录 pre-finalize SHA、最终完整镜像 raw SHA、fw_header
> 双零摘要、ETU SHA/size。
>
> **性质**：离线制包与离线验证，零真机操作、零云端写入、零产品代码改动。
> 离线准备完成 **不等于** 资产已获独立准入——上板/上传仍按各自授权执行。

## 1. 源镜像 provenance（按已批准组件 profile 的真实依赖核对）

- 源镜像：主 worktree `MDK-ARM_F435/cmake-generated/build-gcc-release/app-gcc/X-Track-App-GCC.bin`
  （602984 B，SHA-256 `7328c1b15feff7214378065ca3e7d556ac803b59ebed7029a892d64f15e2153f`，
  2026-09-03 08:12 构建 @ `c89c58f`）。
- **板上同源证明**：P3-2 板识别轮（2026-09-12，只读）确认板上 App 区 =
  该 bin + finalize 头；板识别文档 §2.2 的双零法全镜像摘要重算一致。
- **固件输入零变化核对**：按 Production profile 的 root_patterns 逐目录 +
  top_files 逐项 `git diff c89c58f HEAD`——全部固件源码根（USER/、Libraries/、
  boot/、cmake/、ArduinoAPI/、segger_rtt/、vendor/、bsdiff_lzma_AES128-main/、
  MDK-ARM_F435/Platform/、MDK-ARM_F435/RTE/、MDK-ARM_F435/cmake-generated/cmake/、
  Simulator/LVGL.Simulator/、.github/scripts/）零变化；top_files 唯一变化
  `.github/workflows/build.yml`（endpoint 改造）不被固件构建消费（CMakeLists
  无引用）。**c89c58f..HEAD 共 12 提交 35 文件，落入固件构建输入的变化为零。**
- **结论**：磁盘 `7328c1b1…` 即板上运行 3.2.0 的原镜像，无需重建，直接作为
  toy/真包的 finalize 源。冻结时若 freeze_commit 源码树变化，按资产方案
  §2.3 的基线规则重建。

## 2. 密钥路径声明（构建输入的一部分，如实记录）

- 封包密钥：**开发密钥（vendor 教科书示例 key）**，key_id=1。
  `etu_pack.py DEFAULT_KEY_HEX = 2b7e151628aed2a6abf7158809cf4f3c`，
  与固件 `Libraries/OTA/ota_keys.c` 的 key_id=1 默认密钥
  （`2B7E1516/28AED2A6/ABF71588/09CF4F3C` big-endian 拼接）逐字节一致。
- 板上 3.2.0 固件构建未注入 `OTA_AES_KEY_1_WORDx`（CMakeLists 与 firmware
  workflow 均无定义）→ 板上固件 `ota_keys_get_aes128(1,…)` 返回的就是该
  开发密钥，`ota_keys_uses_development_key()` 为真。P1-3 实机 TEST_BOOT
  闭环（20801）即走此路径成功。
- 本轮制包命令未设 `OTA_AES_KEY` 环境变量（输出含预期 `[warn] OTA_AES_KEY
  未设，使用 vendor 示例 key` 警告行，两包各一次）。

## 3. 制包命令与工具身份

```
# 两份资产各自从 pre-finalize 源副本出发（避免头污染），源副本复制自主 worktree 原件
python Tools/etu_pack.py finalize \
  --app .cache/p3-3-assets/toy-3.2.1-pre-finalize.bin \
  --out .cache/p3-3-assets/toy-3.2.1-30201-final.bin \
  --ver-name 3.2.1 --build-ts 1789275891 --hw-rev 1 --layout-id 1 --min-boot 1

python Tools/etu_pack.py pack-full \
  --app .cache/p3-3-assets/toy-3.2.1-30201-final.bin \
  --out .cache/p3-3-assets/toy-3.2.1-30201-full.etu --target-vcode 30201

python Tools/etu_pack.py finalize \
  --app .cache/p3-3-assets/real-3.2.2-pre-finalize.bin \
  --out .cache/p3-3-assets/real-3.2.2-30202-final.bin \
  --ver-name 3.2.2 --build-ts 1789275891 --hw-rev 1 --layout-id 1 --min-boot 1

python Tools/etu_pack.py pack-full \
  --app .cache/p3-3-assets/real-3.2.2-30202-final.bin \
  --out .cache/p3-3-assets/real-3.2.2-30202-full.etu --target-vcode 30202
```

| 工具 | git blob SHA-1 | 最后修改提交 |
| --- | --- | --- |
| `Tools/etu_pack.py` | `8a413ed35914801006b734eb673347b20c1dccc3` | `d2c851a`（2026-07-25） |
| `Tools/etu_unpack.py` | `86409ec3756388690e41bd375a8998829b2079b7` | — |

finalize 参数沿用 P3-2 板上 3.2.0 同款口径（`--hw-rev 1 --layout-id 1
--min-boot 1`）；build_ts 取制包时刻（两份同为 `1789275891`，2026-09-13）。

## 4. 资产身份四元组（两份分开记录，不混用）

| # | 项 | toy 3.2.1（30201） | 真包 3.2.2（30202） |
| --- | --- | --- | --- |
| 1 | pre-finalize 源 SHA-256 | `7328c1b15feff7214378065ca3e7d556ac803b59ebed7029a892d64f15e2153f`（602984 B） | 同左（同一源镜像，两份独立副本） |
| 2 | 最终完整镜像 raw SHA-256 | `43ee943a185f63d70284c7c5a9992d677a9bf8c518dacd2e63df8ec7e5809b55`（602984 B） | `c958221392fade8b40520df2d7fd4278632d64bcdd8261b0ac7536c6468a7f39`（602984 B） |
| 3 | fw_header 双零摘要 | `a7ae03872dbeb62f1167f16701d57eee0666bab547d94ef08a5f2c603dd755d9` | `85d19304bcc8f40be99e544705f4100c7b9d2702882773f32a46226c1be9d327` |
| 4 | ETU 包 SHA-256 / size | `fc4ae5a9fd1a9c131b548188a7bb66643703cdea7b7007f66c8a71e304d479a2` / 284092 B | `0a2eb26a481d8c462b5316a67a151c8241de354d00797fa22f11e77056538ce5` / 284112 B |

ETU 外层属性：toy `target_vcode=30201 flags=0x000b key_id=1 nonce=9bd604eca9bb22f06de7f0a1114a6f0e`；
真包 `target_vcode=30202 flags=0x000b key_id=1 nonce=ae2c76498bebcc8760779327b73e941d`。

### 4.1 规范文件名（OTA-XC-ASSET-NAMING，冻结）

冻结命名规则要求 full 资产固定为 `e-track-at32f435-v{targetVersion}-full.etu`。
制包时的原始产物名（`toy-3.2.1-30201-full.etu` / `real-3.2.2-30202-full.etu`）
不符合该模式；已按规范名补齐副本并核对与原始产物逐字节一致（SHA 不变，
文件名是登记/R2 键元数据、不改包字节）：

| 资产 | 规范文件名（登记/R2 键用） | size | SHA-256（同第 4 节第 4 行） |
| --- | --- | --- | --- |
| toy 3.2.1 | `e-track-at32f435-v3.2.1-full.etu` | 284092 B | `fc4ae5a9…04d479a2` |
| 真包 3.2.2 | `e-track-at32f435-v3.2.2-full.etu` | 284112 B | `0a2eb26a…56538ce5` |

配套身份（按 P4-2 fixture 固定值模式 `mcu-e-track-at32f435-v{ver}` 推导）：
toy releaseTag=`mcu-e-track-at32f435-v3.2.1`，真包
releaseTag=`mcu-e-track-at32f435-v3.2.2`；`targetImageSha256` = 第 4 节
第 2 行（最终镜像 raw SHA）。云端登记获准时一律使用规范名与上述身份。

**GET_INFO 终点比对标准 = 表第 2 行（最终完整镜像 raw SHA）**——C-TOY-LOOP
绑 43ee943a…，C-REAL-LOOP 绑 c9582213…（各自终点核对，互不替代）。

## 5. 离线验证结果（全部本机复算，rc=0）

| 验证 | toy 30201 | 真包 30202 |
| --- | --- | --- |
| `etu_unpack.py --verify-fw-header` | OK（candidate_len=602984、target_vcode=30201、image_sha256 与封包一致） | OK（target_vcode=30202、同左） |
| candidate 与 finalize 镜像逐字节比对 | **一致** | **一致** |
| fw_header 头字段独立解码（magic=ETFW / vcode / version_name / build_ts / image_len / hw_rev / layout_id / min_boot） | 全部通过 | 全部通过 |
| 双零摘要独立复算（0x400+40..71、0x400+92..95 置 0 后整镜像 SHA-256 == 头内 off40..71 域值） | 通过（a7ae0387…） | 通过（85d19304…） |
| header_crc32 独立复算（zlib.crc32 头前 92B == 头内 off92..95 LE 域值） | 通过（0x133fcef5） | 通过（0x9a7d0750） |
| finalize 与 pre-finalize 差异范围 | 仅 0x400..0x45F（fw_header 96B 内 78 字节），本体零差异 | 同左 |
| `ota_backup.c:410` 升级检查模拟 | 30201 > 板上镜像 30200 ✔ | 30202 > toy 后镜像 30201 ✔ |

补充核查：**toy 与真包两份最终镜像之间仅 38 字节差异，全部位于
0x408..0x45F（fw_header 内 vcode/version_name/双零摘要/CRC 等版本身份
字段）**——两资产功能本体逐字节相同，版本身份是唯一区分，与用户裁定
「同一合格生产镜像生成两个不同版本受控资产、不同包改名重复计算」一致。

## 6. 落盘位置与可复现性边界

- 全部产物在 admission worktree 项目内被忽略目录
  `.cache/p3-3-assets/`（gitignore `/.cache/` 覆盖），共 8 个文件：
  2×pre-finalize、2×final、2×etu、2×verify-candidate。
- **最终镜像可确定性复现**：pre-finalize 源 SHA + ver-name + build-ts +
  finalize 参数 → 输出逐字节确定，文档四元组可独立复核。
- **ETU 实物不可从文档复现**：pack-full 的 AES nonce 每包随机（P0-2 验收
  已确认同输入两次打包 nonce 不同）。`.cache/p3-3-assets/` 内的两份 ETU
  是唯一实物——获批上传云端时必须使用该实物且 SHA 对应本表第 4 行；若
  丢失重打包，ETU SHA 变化须重新登记并重走资产核对（最终镜像 SHA 不变）。
- **不清理该目录**：在资产获准入库或上传前，`.cache/p3-3-assets/` 是这些
  受控资产的唯一持有处。

## 7. 边界声明

- 本轮零真机操作（未连 J-Link、未读写设备/BCB）、零云端写入（未上传、
  未登记 fixture、未动 D1/R2）、零产品代码改动、零 CI 触发。
- golden vectors（`tests/ota-vectors/`）与本资产无关，仍不具上板资格。
- 资产离线准备完成 ≠ 独立准入：实机升级闭环仍被 BCB 阻断
  （`ota_backup.c:385`，恢复方案见 `P3-3-bcb-recovery-plan-2026-09-13-v2.md`）；
  云端登记与上传按 D1 写入单另行审批；上板按合并操作单另行审批。
- 若 freeze_commit 源码树与 c89c58f 在 Production profile 范围内不一致，
  按资产方案 §2.3 重建源镜像并重新制包（本记录四元组随之作废重出）。
