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

备注：

- P2-6-v1 的初冻提交 `85e98a6` 已被 `d27200d`（修复证据包入库完整性）整体重写，
  在 `85e98a6` 上复校为 475 条错误，故有效冻结点是 `d27200d`。
- P3-6-v1 的实现提交 `7833303` 经 PR #14 squash 后只剩 `fa320be`，两者 tree 相同
  （`2787fa0e…`）。这是 v3 起禁止 squash 合并的直接原因：squash 会让
  `freeze_commit` 不可达，只有 tree 能幸存。
