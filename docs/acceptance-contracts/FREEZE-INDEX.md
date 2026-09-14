# 冻结包冻结点索引

本文件是已冻结验收包的机器校验索引。`bundle_commit` 定位合同、矩阵和证据包字节；
`freeze_commit` / `freeze_tree` 定位被验实现输入。治理测试逐行核对对象类型、tree 一致性
及 `freeze_commit -> bundle_commit -> HEAD` 的祖先关系。

- 本文件不在任何 manifest profile 内（`Tools/provenance/manifest_profiles.json`
  只枚举本目录的两份 template），所以在此登记提交 SHA 不构成自指环。
- 证据包先单独提交为 `bundle_commit`，索引行再由后续收口提交追加；只增不改。已登记行
  对应的冻结包字节不许回改，禁止让包提交记录自身 SHA。
- v2 合同（`etrack-acceptance-contract-v2`）不含冻结点字段，只能靠本索引复校，
  且必须用冻结提交**自带**的 `Tools/acceptance/validate_bundle.py`（v3 校验器
  已不再接受 v2 合同）。v3 合同自身带 `freeze_commit` / `freeze_tree` /
  `profile_config_blob`；索引额外记录无法写进合同自身的 `bundle_commit`。

## 复校方法

```
git worktree add --detach .cache/freeze-check/wt-<id> <bundle_commit>
python -X utf8 -B .cache/freeze-check/wt-<id>/Tools/acceptance/validate_bundle.py \
  --contract .cache/freeze-check/wt-<id>/docs/acceptance-contracts/<id>.contract.json \
  --matrix   .cache/freeze-check/wt-<id>/docs/acceptance-contracts/<id>/<id>.evidence-matrix.json \
  --repo-root .cache/freeze-check/wt-<id>
git worktree remove --force .cache/freeze-check/wt-<id>
```

期望输出末行 `VALIDATION=PASS contract=<id> ...`。

## 索引

| contract_id | 合同 schema | bundle_commit | freeze_commit | freeze_tree | 复校结果（2026-09-04 实测） |
|---|---|---|---|---|---|
| P2-6-v1 | v2 | `d27200d6e0e203ae4b4c83f248393c7d112bb53b` | `d27200d6e0e203ae4b4c83f248393c7d112bb53b` | `1659b328b5ce3d1d9a950cf413531504181a719d` | PASS |
| P2-6-v2 | v2 | `9afd51e0ae369db2c554cd48948d576ac5481143` | `9afd51e0ae369db2c554cd48948d576ac5481143` | `40074c70f55bca4259f01e74db79fd596e794a9f` | PASS |
| P2-6-v3 | v2 | `bc13f184dd00ca9690f597e62199b9059a59d226` | `bc13f184dd00ca9690f597e62199b9059a59d226` | `6184b522e9200b6c0145ef937bf9e64ee503f3a9` | PASS |
| P3-1-v2 | v2 | `1db4fc6d6d8f86d091c026392960d67a7e2e9a05` | `1db4fc6d6d8f86d091c026392960d67a7e2e9a05` | `a0c1a6ddc60deb45793421af97bbed181f17d194` | PASS |
| P3-2-v1 | v2 | `cb2ebdde6ff210906e06c293c891c13eae5c626f` | `cb2ebdde6ff210906e06c293c891c13eae5c626f` | `771431d10cb6099c2d34f8d3ff8ffd02f2b22b85` | PASS |
| P3-6-v1 | v2 | `fa320bead2cce90b38bf211ca757f846822ded25` | `fa320bead2cce90b38bf211ca757f846822ded25` | `2787fa0e529ee32009c614f761e81ae28e2a9728` | PASS |
| P3-7-v1 | v2 | `fcb77158425f2ade3733f9a5237013aaf7bb51f4` | `fcb77158425f2ade3733f9a5237013aaf7bb51f4` | `26b0a97f42f1c51bfef669b6d27b765cf274fcf3` | PASS |
| P3-3-v3 | v3 | `421bd290b0f5e30b385a17c2ab82a2b3d8844dc2` | `a178ecc1dca3929e1bca702fb11344f3c5bd2872` | `2ce26b29c395aebdd75b49376755d16c3706feea` | PASS（2026-09-13 FROZEN+NOT_RUN 执行前检查；O 序列执行后另行最终验收） |
| P3-3-v4 | v3 | `a548d4325d6651264b0867e865e3ee40695aa372` | `bed3aa06f99c3d99291b081069a72ffd426a4e3d` | `6b971c71abcf7ebaa271aee9f6eac6f4ceb66b80` | PASS（2026-09-14 FROZEN+NOT_RUN 执行前检查；冻结办理经用户授权由实现会话代办，如实记录授权链；O1-O5 冻结后重跑，另行最终验收） |
| P3-3-v5 | v3 | `b2fc1cebfc9c2585026489ac366315e4e89d38d8` | `6415226b8c30abcffa2b9bab52f0db717f8f7cb9` | `4bcf18a82a03f16c813e1b46938962538876ddbd` | PASS（2026-09-14 FROZEN+NOT_RUN 执行前检查；冻结办理依修复轮整体授权由实现会话代办，如实记录授权链；O1-O5 冻结后重跑，另行最终验收） |
| P3-3-v6 | v3 | `3f7ca7e124c8cc36cbf78fb0eeea9a14b3fe88dc` | `0fb167cf4c44a6e4741e5a42fcd4945cf29f7780` | `b3d1d311645d584c48419b546a061c5648da740f` | PASS（2026-09-15 FROZEN+NOT_RUN 执行前检查；冻结办理经用户授权由实现会话代办，如实记录授权链；合同 SHA-256 B445C209C20DA0BC52473950C47D6E1807EF74C23377495F7CB48C6A2B70C171，矩阵 37A64A107DFE84A531909865B02C90CA25E3CCCC26634BF575744459E62EF6B9；r6 实机闭环等事实证据由验收会话复核，正式验收另行） |
| P3-3-v7 | v3 | `c4a38f802ec81928f1182136ccee9d457068ed1b` | `0fb167cf4c44a6e4741e5a42fcd4945cf29f7780` | `b3d1d311645d584c48419b546a061c5648da740f` | PASS（2026-09-15 FROZEN+NOT_RUN 执行前检查；勘误轮：修正 v6 独立验收 EVIDENCE_GAP 两阻断 G01（五条冻结命令执行轮口径）与 G02（EXT 指纹遗留 v5 身份），freeze 三元组与 v6 相同零实现变化；冻结办理经用户授权（治理质疑答复后「你继续起草吧」，五条命令与指纹改动过目后「冻结吧」）由实现会话代办，如实记录授权链；合同 SHA-256 38279B9FC9F2EBB7E6C18831FF4D8A0DDD719BED1EBDF4CAFB637FE68D721B9B，矩阵 0AE4ABA9ADF63AB3386F807C100D4796E11DB9CA8B61EF9EBCA776C502D07F1B；parent 绑定 v6 合同 B445C209C20DA0BC52473950C47D6E1807EF74C23377495F7CB48C6A2B70C171；后继验收轮 validate 须携带 v6 合同/矩阵为前驱） |

备注：

- P2-6-v1 的初冻提交 `85e98a6` 已被 `d27200d`（修复证据包入库完整性）整体重写，
  在 `85e98a6` 上复校为 475 条错误，故有效冻结点是 `d27200d`。
- P3-6-v1 的实现提交 `7833303` 经 PR #14 squash 后只剩 `fa320be`，两者 tree 相同
  （`2787fa0e…`）。这是 v3 起禁止 squash 合并的直接原因：squash 会让
  `freeze_commit` 不可达，只有 tree 能幸存。
- P3-3-v3 行按「只增不改」保留原样，但该轮判定已被 v4 取代：用户 2026-09-13
  决策「现在立刻修，验收重来」（受验 App 码表设备页为演示稿），v3 冻结包作废
  （freeze_commit `a178ecc` 后 profile 内出现新提交，执行门禁必红）。v4 合同经
  `parent_contract_sha256` 绑定 v3 合同；v3 包字节不动，仍可在其 `bundle_commit`
  上复校。
- P3-3-v4 行按「只增不改」保留原样，但该轮判定已被 v5 取代：v4 冻结约 40 分钟后
  r3 Quick Tunnel 域名随进程死亡（EXT-HTTP 事实基础失效），O2 在旧缺陷 toy
  （源 7328c1b1…，未含 BCB STAGED 提交修复）上实测 PRODUCT_FAIL
  （REBOOT_RECONNECT_FAILED），修复轮重建烧板又经烧录事故与恢复轮 20260914-r2；
  v5 合同经 `parent_contract_sha256` 绑定 v4 合同（4AABC513…D20A2），资产从
  1894f9d 修复版源重制；v4 包字节不动，仍可在其 `bundle_commit` 上复校。
