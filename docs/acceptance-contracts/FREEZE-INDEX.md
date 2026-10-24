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
| P3-3-v8 | v3 | `5695abc5d7cd1402bd0815017a3e383c57571662` | `ceaf8d2b7bb8e78968462af51a57ff1250731b61` | `4fd600a48a25654fe82db3cb6fd6f6338392bc48` | VALIDATION=PASS，overall=EVIDENCE_GAP（2026-09-15 原独立验收 R1 历史终态；四项原始 EXECUTED PASS 为 v9 直接复用来源；R2 准备仍为 NOT_RUN，未替代 R1） |
| P3-3-v9 | v3 | `5695abc5d7cd1402bd0815017a3e383c57571662` | `ceaf8d2b7bb8e78968462af51a57ff1250731b61` | `4fd600a48a25654fe82db3cb6fd6f6338392bc48` | VALIDATION=PASS，overall=PASS（2026-09-15 当前有效独立验收，五项全部 PASS；本次主会话按移交命令完整性复校通过，非新验收轮次） |
| P3-4-v14 | v3 | `15a025b9c2690e864456a32fb2820422846fb85b` | `fcbace8b3f782714a139a77a12cb9305dbaef7cc` | `7038ea9de58dba625d487caee57c6dfb130d04b6` | VALIDATION=PASS, overall=EVIDENCE_GAP(2026-10-14 partial offline round; native FC failure and one reference EXECUTED PASS preserved; zero device actions) |
| P3-4-v15 | v3 | `15a025b9c2690e864456a32fb2820422846fb85b` | `fcbace8b3f782714a139a77a12cb9305dbaef7cc` | `7038ea9de58dba625d487caee57c6dfb130d04b6` | VALIDATION=PASS, overall=PASS(2026-10-14 candidate stage only; one direct reference reuse and three offline criteria; P3-5/P5 and production release excluded) |
| P4-1-v1 | v3 | `7f014a8887dc79646ff392ee8cfa6a1ce2c9cf67` | `2d3daae4ac5441d3eb736b654c237ae53760067c` | `b51a3ba2f22ff86caea394464747171db60ecb51` | VALIDATION=PASS, overall=PRODUCT_FAIL(2026-10-16 canonical staging run 38897470681 attempt 1; P41-NATIVE-01 blocks R2 upload; original failures and partial byte checks preserved; no production/device action or merge) |
| P4-1-v2 | v3 | `00041e535a89c238a7dde9b035663b82b1fe4698` | `b9d7d18c76e6495fbebf6758df6e4427e79e97b5` | `618e4761f8fc4ee99182d0e503b44baeea1d9c47` | VALIDATION=PASS, overall=HARNESS_FAIL(2026-10-17 canonical run 38946949709 succeeded; relative artifact argument broke evaluator result construction; original failure and successful absolute-path preparation preserved; no repeated staging for the caller correction) |
| P4-1-v3 | v3 | `8f154a0f1078cbeaa3505af428c46190f0b648f8` | `b9d7d18c76e6495fbebf6758df6e4427e79e97b5` | `618e4761f8fc4ee99182d0e503b44baeea1d9c47` | VALIDATION=PASS, overall=ENV_BLOCKED(2026-10-17 three direct v2 PASS reuses and BYTES EXECUTED PASS; independent recovery GET timed out at 573440/605080 bytes after HTTP 200; partial originals retained, STATE not observed, no new staging or remote mutation) |
| P4-1-v4 | v3 | `7f136c07505f56582640761944ab5add093252e4` | `b9d7d18c76e6495fbebf6758df6e4427e79e97b5` | `618e4761f8fc4ee99182d0e503b44baeea1d9c47` | VALIDATION=PASS, overall=PASS(2026-10-17 pre-P5 implementation/staging boundary; four direct original reuses plus complete independent R2 readback and offline state evaluation; previous failures retained, two staging workflows total, no production/gate/device action) |
| P4-3-v1 | v3 | `7e11e96c4acb2735710d626682a6d1a018efadf6` | `1ddd948bbf7d0dc2097c14d87def767314342f8f` | `855c15853c572b83d9684235dbf69a247d4968b2` | VALIDATION=PASS, overall=PASS(2026-10-18 P43-20261018-01; seven required criteria, four independent offline evaluations of source and retained originals; governance CI 39110429390 passes; P43-ACCEPT-02 closed, failures and role/deployment/dependency/private-retrieval limits retained; no repeated cloud campaign, new deployment, main merge or device action) |
| P4-4-v1 | v3 | `e5994fb28466e46c99a1f247494473e6cba9cc03` | `08afb97ddae316b3b305354f1582afdb836d7633` | `0fbb1b610a6e09155a10e2d9b3b3d12e26725da7` | VALIDATION=PASS, overall=EVIDENCE_GAP(P44-20261019-01; final matrix P4-4-v1/final-evidence-matrix.json; HISTORY/CONFIGURATION/HYGIENE pass, six criteria not observed; protected D1 page incomplete at HTTP 200; 31 complete responses and original partial bytes preserved; zero A/B dispatch, production publication or device action; gate=false) |
| P4-4-v2 | v3 | `84268ac2ad34727b76250ff944211b7efba1cfb3` | `70193ce7fb7cc4e426029d07cf7b50c1fcbfef1c` | `e97e9b44d4e06efc9133add82502a55241c9af55` | VALIDATION=PASS, overall=EVIDENCE_GAP(P44-20261019-02; final matrix P4-4-v2/final-evidence-matrix.json; actual V1 predecessor supplied; HISTORY/CONFIGURATION/HYGIENE pass, six not observed; four complete new pages retained, rows8 OFFSET32 remains incomplete HTTP200; 35 complete observations and both failures preserved; zero A/B, production publication or device action; gate=false) |
| P4-4-v3 | v3 | `20febda2ac2e05e5f4b761a9f365091b177516b6` | `ba952497948a03c40cbd8baebbfc9228621fb44b` | `5427f4728cfc0e6a3b4760548fb6e03385922c6b` | VALIDATION=PASS, overall=EVIDENCE_GAP(P44-20261019-03; final matrix P4-4-v3/final-evidence-matrix.json; actual V2 predecessor supplied; HISTORY/CONFIGURATION/HYGIENE pass, six not observed; 12 new strict gzip responses complete, then patches rows8 OFFSET0 pre-response ECONNRESET; 47 complete observations and three failures preserved; zero A/B, production publication or device action; gate=false) |
| P4-4-v4 | v3 | `da37711799a21c4eb2c5d082dab1a7b81d028511` | `2756ca95e26ec636216313271708b3304d61a5cc` | `77549b4b756f1e88de8b854b4673857021a65783` | VALIDATION=PASS, overall=EVIDENCE_GAP(P44-20261020-04; final matrix P4-4-v4/final-evidence-matrix.json; actual V3 predecessor supplied; six EXECUTED PASS and three NOT_OBSERVED; owner-rejected A 39313672925 and owner-approved successful B 39351100037, both attempt 1; byte/readback/preflight passed; 31 after responses complete before one pre-response connect timeout; originals retained, no repeated rehearsal, production publication or device action; gate=false) |
| P4-4-v5 | v3 | `21fa17f7da91a0d336ae1f1a7f1a93910beb2ab7` | `9bfc48573a5eed190583411ac465bd847424a286` | `bd28d777ee526166d9c1050c23e487dddf8eac0a` | VALIDATION=PASS, overall=EVIDENCE_GAP(P44-20261020-05; final matrix P4-4-v5/final-evidence-matrix.json; actual V4 predecessor supplied; four direct C4 REUSED PASS, two new EXECUTED PASS and three NOT_OBSERVED; formal-after exit 1 at auxiliary token verify ECONNRESET, HTTP receive phase unknown; zero new business reads, original 31 after responses and all failures preserved; product remains C4/3.2.9, no repeated A/B or release/device action; gate=false) |
| P4-4-v6 | v3 | `90c5924f74e3c1fe3ca88576a16a9ba18b39856d` | `6fffaa25442bdcd863f3a3f4e93e20ebe180a2c1` | `8f077f4c2f74acc453d279cc9b21a74ca68776a8` | VALIDATION=PASS, overall=EVIDENCE_GAP(P44-20261020-06; final matrix P4-4-v6/final-evidence-matrix.json; actual C5 predecessor and direct C4 origins; four REUSED PASS, two EXECUTED PASS and three NOT_OBSERVED; formal-after exit 1 at protected-patches-rows8-16, pre-response UND_ERR_SOCKET with zero body bytes and no retry; 39 new complete responses plus 31 C4 responses retained; closed 1411-file privacy inventory unchanged; no repeated A/B, upload, registration, readback, production release or device action; gate=false) |
| P4-4-v7 | v3 | `98c1d053227d437e9ec71c3ee622926b8ad4f116` | `371baeeb8519a0340a79c96b6a7cd6406b2e0346` | `085b095982054ecf45c1a23ff21031760376cb2b` | VALIDATION=PASS, overall=EVIDENCE_GAP(P44-20261021-07; final matrix P4-4-v7/final-evidence-matrix.json; actual C6 predecessor, complete C5 lineage and direct C4 origins; four REUSED PASS, two offline EXECUTED PASS and three NOT_OBSERVED; P44-SUCCESSOR-05: formal-after slot 1 exited before request/attempt creation because startAttempt passed a trailing-slash directory to makeIO.exists; zero new cloud requests, slot 2 not used, no blind continuation; 70 complete after responses and all failures retained; closed 1439-file privacy inventory unchanged; product C4/3.2.9, no business replay, production release, main integration or device action; gate=false) |
| P4-4-v8 | v3 | `e93ea8e9966b2b0e37921ae1dd2384cb5438e35e` | `640cb359db7672cdab1e40bc5853a9ab311e35fa` | `a343caba4c7d2a5976ebf7674017e7352b938626` | VALIDATION=PASS, overall=PASS(P44-20261021-08; final matrix P4-4-v8/final-evidence-matrix.json; all 9 required criteria pass, 4 direct C4 REUSED and 5 EXECUTED; actual v7 previous pair and complete C4/C5/C6 reuse chain; SUCCESSOR-05 independently closed; 70 original plus 73 new complete after responses, 74 new request attempts including one admitted pre-response ECONNRESET retry, all failures retained; only invocation slot 1 used; approvals, isolation and 1824-file privacy scan pass; product C4/3.2.9, pre-P5 configuration/staging qualification only, no successful business replay, main integration, production release or device action; gate=false) |

| P3-8-v1 | v3 | `cf1ffd5fb8f658dd32ae4e676ad893b3bbe8b6a8` | `981572e4e6a138063a25d10aaaeef3e155a90092` | `7110859e736ea6efb914d6bb70f3a036b400f5e0` | VALIDATION=PASS, overall=EVIDENCE_GAP; P38-HOST-ENTRY-01; software originals verified, no physical transfer |
| P3-8-v2 | v3 | `6149c1b122302c9cc93275ea5226b017f7181c5b` | `af2429199410b42b4ea428662bf8cd2e928d72a7` | `82bde295c23433ade842974db4950af4c225d83a` | VALIDATION=PASS, overall=EVIDENCE_GAP; actual v1 predecessor supplied; P38-RUNTIME-ADMISSION-02, D1 reader failed before ready, zero upgrade starts |
| P3-8-v3 | v3 | `8a1ff7260159c02258698e753cd8557b2d1de801` | `60cb25c459bcde95f2be42edc28ef3fdb2448111` | `f595375dd8ce982610eaa53cf8496ac0af293462` | VALIDATION=PASS, overall=EVIDENCE_GAP; actual D1 fallback passed; D2 ran with notifications still denied; no END or installation |
| P3-8-v4 | v3 | `8a1ff7260159c02258698e753cd8557b2d1de801` | `60cb25c459bcde95f2be42edc28ef3fdb2448111` | `f595375dd8ce982610eaa53cf8496ac0af293462` | VALIDATION=PASS, overall=EVIDENCE_GAP; v3 software/fallback reused; actual acquired background, sleep, notification return and cancellation passed; planned disconnect recorded, final resume/identity NOT_RUN |

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
- P3-3-v7 原索引行仍绑定其 FROZEN+NOT_RUN 前检提交，不改写该行。后续独立验收的
  EVIDENCE_GAP 终态矩阵、原始记录和报告按交付原样归档于 `5695abc5d7cd1402bd0815017a3e383c57571662`；
  不把 v9 PASS 追溯写入 v7/v8，也不要求旧冻结输入在当前 HEAD 上全部变绿。
- P3-3-v9 复校必须同时传入同一归档提交内的 `P3-3-v8.contract.json` 和
  `P3-3-v8/P3-3-v8.evidence-matrix.json`。实际上一终态为 v8 R1，
  矩阵 SHA-256 `634a57b09ab94cee46f013ccb888884040dc95c23f2a42435b2b3641e35f409f`；
  不得改用 v8 R2 NOT_RUN 准备矩阵。v9 合同 SHA-256
  `8b0fd07a8e01070d2eda5745ea73ec0e6759911c45796c3289dadce54a44950f`，
  终态矩阵 SHA-256 `26ea1e0d9fa54da3837bdfcbe551e9fdf07b621a4b03f10ef326bd4aff8264c2`。
  验收结论见 `docs/ota-exec-notes/P3-3-v9-acceptance-2026-09-15.md`；
  Git 收口状态单独记录于 `docs/ota-exec-notes/P3-3-git-closeout-2026-09-15.md`。
