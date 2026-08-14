# P2-5 F4 final-r5 独立验收报告 R4

## 0. 最终结论

本轮结论为 **BLOCKED，不通过**。

- P2-5 保持“阻塞”。
- P2 保持 `4/6`。
- 不更新 `PLAN-OTA-EXEC.md`。
- 本结论只表示本轮未形成满足 R2 的完整独立证据链，不等同于判定此前用户观察到的 OTA 功能异常。

证据矩阵最终统计：`8 PASS / 3 FAIL / 55 NOT_OBSERVED`。R2 要求全部条件为 PASS 才能通过，任一 FAIL 或 NOT_OBSERVED 均阻止整卡通过。

用户已明确确认拍照就绪，但本轮没有启动决定性 fresh 真机 OTA，也没有取得照片原件及 SHA-256。验收执行未在用户就绪后及时给出明确停机结论，造成了不必要的等待；这是本轮验收执行问题。由于 R2 前置条件已经出现确定性失败，继续要求用户拍照也不能使本轮整卡通过。

## 1. 身份、标准与证据目录

| 项目 | 值 |
|---|---|
| 活动根目录 | `D:\github\my\E-Track-p2-5-20260801` |
| HEAD | `0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e` |
| 唯一标准 | `.claude/prompt-P2-5-verification-r2.md` |
| R2 SHA-256 | `8393D99B094ACEAFE8F2639C3BD0F717DED9AA95E4FB82A3947A18414099FB9A` |
| 主证据目录 | `.acceptance-p2-5-f4/20260812-232411/` |
| 证据矩阵 | `.acceptance-p2-5-f4/20260812-232411/evidence-matrix.md` |
| 机器可读矩阵 | `.acceptance-p2-5-f4/20260812-232411/evidence-matrix.json` |
| Harness 审计 | `.acceptance-p2-5-f4/20260812-232411/harness-audit.txt` |
| 命令日志 | `.acceptance-p2-5-f4/20260812-232411/command-log.txt` |
| 收尾审计 | `.acceptance-p2-5-f4/20260812-232411/closure-audit.txt` |

开场证据已记录完整 status、porcelain-v2 status、tracked diff、name-status、untracked 清单和 `git diff --check`。主要 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `preflight/01-show-toplevel.txt` | `74EDFBF418DDCCCA027C53907F1618EC271EE6131B9368CD81C3E503043448E9` |
| `preflight/02-head.txt` | `F0023205153080F2147D1A188CF04FA8416A9AC5C2C7D87B53DD77708186C8D9` |
| `preflight/03-git-status-full.txt` | `ED6BE4F1B229E8DE8FE3C7986F51FC0564AC924A728B21867EFFE6150DDB241F` |
| `preflight/04-git-status-porcelain-v2.txt` | `8E118D34F77764915CC16E7FCB27C96670B9D06FBC7CA72A25010310660A858C` |
| `preflight/05-tracked-diff-binary.patch` | `8ED9B1312FF0007983009E74046851DEB238E040ED7140673C14E156A684FD98` |
| `preflight/06-tracked-diff-name-status.txt` | `BF134E777EF425FA08F8AB0BA2EA3D949B9D60FF08C235859CEC4DADB76BD78D` |
| `preflight/07-untracked.txt` | `9F3CD426914D800AFDC6127D0FD1BB36FD0EF293CD6D161682676835E704CC84` |
| `preflight/08-git-diff-check.txt` | `C31A59129CD4F90D94DABC5E51A8CAA357EB1A13FA84608DB2B4B693525BCDEF` |
| `harness-audit.txt` | `18F16B3056E07244DD0C4F3C51A31943CD60F55FF2A0FA2D14BDA6BCEB26FA0D` |
| `harness-file-hashes.json` | `B340644DB9CF3DF690083C0B0C5D6FA826E6C815BCFD482F56F5849F9AF35C7E` |
| `closure-audit.txt` | `4282D7BB7A68745C732450A93D15477559066C5B4570008EAA621D87910385EF` |

## 2. 决定性失败

### 2.1 PROV-1：冻结源码 manifest 绑定失败

Post-audit 独立重建结果：

| 项目 | 值 |
|---|---|
| 文件数 | `2943` |
| missing / extra / changed | `0 / 0 / 0` |
| 独立 manifest SHA-256 | `94F4E8082830BE53F40A137C91531AE9ED8CA9D4AEBEDA11C33188E956631FCF` |
| R2 final-r5 参考 SHA-256 | `D3268F4AE8BB6CF514EE3B7717BC14C8A65E3082ED91C2B8C462A883801BF293` |
| 结论 | `FAIL` |

复现：在基线 HEAD 和当前工作树上按本轮独立 manifest 规则重新枚举 2943 个生产输入、生成逐文件 SHA-256 清单并哈希清单。结果文件为：

- `.acceptance-p2-5-f4/20260812-232411/provenance-postaudit/summary.json`，SHA-256 `6D6D8F495D61C79273C65FE2473EA84CB86674A5BF81FE22D1A738789D434822`。
- `.acceptance-p2-5-f4/20260812-232411/provenance-postaudit/source-manifest.txt`，SHA-256 `94F4E8082830BE53F40A137C91531AE9ED8CA9D4AEBEDA11C33188E956631FCF`。

R2 明确规定产物绑定不一致时 fail-fast，因此不能沿用实现侧 final-r5 的后续 PASS 汇总。

### 2.2 PROV-3：fresh raw App 与 R2 final-r5 参考不一致

诊断性 fresh GCC App 与 Boot 构建成功，但发生确定性 raw App 绑定不一致：

| 产物 | 大小 | SHA-256 |
|---|---:|---|
| R2 final-r5 raw App 参考 | `598852 B` | `8A5DEEBE5EB0D79AD2BD0CE0A9F0F93ACA6F99F5C3A3A87C0C10D9615783D741` |
| 本轮诊断 fresh raw App | `598852 B` | `B1021E296F8F63A843AFE3E43E1CA83D1F07907FC7D0BC596B4E1574297D69DF` |
| 本轮诊断 fresh Boot | `14724 B` | `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |

两份 App 有 14 个字节不同，位置约为 `0x46368` 到 `0x46AC2`，内容可归因于嵌入的 `__DATE__` / `__TIME__`。这可以解释差异来源，但不能取消 R2 的 exact binding 要求，因此 PROV-3 为 `FAIL`。

诊断封包链内部 candidate 与 v20801 逐字节一致：

| 产物 | 大小 | SHA-256 |
|---|---:|---|
| finalized v20800 | - | `C6D46D64415DE08AE3E73ED14412D4E842ECE664FAE25526B397A4D3AE028065` |
| finalized v20801 / candidate | - | `BFB0ECF8AB3B6C51072EE530116F810A951E61640B4399C3B31E05DEA17FBEFB` |
| 诊断 ETU | `281198 B` | `BDB01B4761EAD0AC811E323CE70576592B1B7F905B36E1BE90920DE2B81BEEAA` |

这些封包结果发生在最终 harness 审计完成前，只能作为诊断输入，不能补足 R2 的 post-timing 最终生产产物到 SD、candidate、map 和设备的完整绑定链。原始证据：

- `.acceptance-p2-5-f4/20260812-232411/gcc-build/logs/summary.json`，SHA-256 `6EE19EB2F0580C6B70B5B39264A4886E499973CC2D0504738F44509211B333C3`。
- `.acceptance-p2-5-f4/20260812-232411/package-current-rerun/summary.json`，SHA-256 `BBA03EDBFE76C308A1A8C857932177A317F12314C92EDA8F075499B5A7EB327B`。

### 2.3 CLEAN-1：发生未授权兄弟仓库写入

本轮边界审计发现以下项目外主动写入：

| 项目 | 值 |
|---|---|
| 路径 | `D:\github\my\E-Track\.acceptance-p2-5-f4\20260813-015454\recompute_manifest.ps1` |
| 大小 | `3074 B` |
| SHA-256 | `724A15111AA01BC27AF302E681F093F1A09919A2217D29A9B149A77856AF9AF5` |
| 结论 | `FAIL` |

该路径不属于本轮授权 worktree。文件未被删除、移动或修改，因为用户没有授权清理兄弟仓库内容。另有既存兄弟仓库文件 `D:\github\my\E-Track\.acceptance-p2-5-f4\20260810-200500\generate_audit_r26.ps1`，大小 `39257 B`，SHA-256 `A92BCFD64EEB681D79D44E1D9ACCB84E7CDF1A8C72E9FBE9091FCAD610F86BE4`；本轮只披露，不认定为本轮创建，也未触碰。

## 3. 可采信通过项

PRE-1、PRE-2、HAR-1、HAR-2、HAR-3 为 PASS。Harness 审计结论是：required outcome 未被常量 PASS/true 硬编码；未接受未经审计的动态实现侧加载；强制终止、超时和长时间 halt 的假 PASS 风险已检查。

模拟器生命周期中，SIM-2、SIM-3、SIM-4 为 PASS。该结果是审计记录中唯一允许采信的顺序例外，因为 exact r5 runner 在运行前已被审计，运行后又检查了原始 PNG：

| 项目 | 结果 |
|---|---|
| real-Startup 运行 | `4/4 PASS` |
| 连续 PASS | 是 |
| Responding / Hung | 全部 `Responding=True`、`Hung=False` |
| 关闭方式 | 全部 `WM_CLOSE` |
| Force fallback | 未使用 |
| 残留进程 | `0` |
| 结果文件 SHA-256 | `9C02C5C5179CC5C2E6244D4CE6EF0370BED8B09CBC86464CB822C00329EF1B72` |

结果路径：`.acceptance-p2-5-f4/20260812-232411/sim-r2-results-r5/lifecycle/logs/results.json`。

SIM-1 保持 `NOT_OBSERVED`，因为 production simulator Rebuild 发生在最终 harness 审计前，未按 R2 顺序 post-audit 重跑。

## 4. NOT_OBSERVED 项

### 4.1 F4 与 Begin/Apply 门禁

F4-1 至 F4-8、GATE-1、GATE-2 均为 `NOT_OBSERVED`。本轮 fixture 结果为：

| 字段 | 值 |
|---|---|
| `BrowserReady` | `false` |
| `Failure` | `BROWSER_NOT_READY` |
| `SemanticStatus` | `NOT_OBSERVED` |
| 结果 SHA-256 | `E1743C56568BD865EDDCB872BDE4ADA528FA7A5C46047397F708701BD0A661C4` |

证据路径：`.acceptance-p2-5-f4/20260812-232411/sim-r2-results-r5-truncscan/fixture-truncscan/logs/result.json`。没有使用 `CandidateAndStagePassed=true` 等代理字段推导视觉或语义通过。

### 4.2 独立计时链

TIME-1 至 TIME-8 全部为 `NOT_OBSERVED`。本轮没有完成从冻结生产源码派生隔离计时版本、保存插桩 patch/清单/哈希、测量首次和再次进入、证明生产源码零 mismatch、clean-first 重建 post-timing 最终生产固件的完整链。

实现侧历史值 `37,747 us`、`47,020 us`、`914,028 us` 未被继承，也不能用于本轮 320 ms / 917 ms 门槛判定。

### 4.3 审计前诊断结果

12 组宿主测试的诊断运行显示 `12/12` 通过；fresh GCC App/Boot 诊断构建为 0 errors、1252 warning lines；封包链内部 candidate 与 v20801 一致。但这些流程发生在 `2026-08-13T02:28` 最终 harness 审计完成前，未进行 post-audit 独立重跑，因此 HOST-1 至 HOST-12、BUILD-1 至 BUILD-4、PKG-1、PKG-2、SDIO-1 保持 `NOT_OBSERVED`。这不是把诊断结果改判为 FAIL，而是不将错误顺序的结果计入最终矩阵。

### 4.4 SD、J-Link、真机 OTA 与视觉

以下流程均未执行，因此相应矩阵项保持 `NOT_OBSERVED`：

- SDIO 普通复位和文件管理器扫描窗口复位压力测试。
- 写 E: 前完整根目录清单和条目数记录。
- 覆盖及回读 `E:\P2-5-FULL.etu`。
- fresh map RTT 地址解析及 `SEGGER RTT` 签名验证。
- 正式 P1-6 CLEAR_BCB 恢复 v20800 CONFIRMED。
- v20800 CONFIRMED 到 STAGED、APPLYING、TEST_BOOT、CONFIRMED 的 fresh OTA。
- 第二次复位后 BCB already CONFIRMED vcode=20801。
- 最终 SDReady、VTOR、CFSR、编码器和返回操作验证。

UI-1 至 UI-4 全部为 `NOT_OBSERVED`。用户已经准备拍照，但 OTA 未启动；不存在本轮 fresh 真机照片或录像原文件，也不存在对应 SHA-256：

| ID | 必需画面 | 状态 |
|---|---|---|
| UI-1 | CANDIDATE VERIFY | `NOT_OBSERVED` |
| UI-2 | BACKUP + STAGED | `NOT_OBSERVED` |
| UI-3 | 导入成功结果页 | `NOT_OBSERVED` |
| UI-4 | 升级后正常界面、编码器和返回操作 | `NOT_OBSERVED` |

历史用户口述、此前 OTA 监察、RAM/RTT 状态链和模拟器截图没有被错误地替代为本轮视觉 PASS。此前 OTA 过程没有问题与本轮不通过并不矛盾：前者描述一次历史功能观察，后者要求当前证据目录中的 exact fresh、同源、可哈希、顺序合规的独立证据链。

## 5. 当前设备、SD 与进程状态

本轮没有执行 J-Link 烧录、复位、读内存、RTT logger、CLEAR_BCB 或 OTA，因此没有改变设备软件和 BCB 状态。没有执行 E: 写入；`E:\P2-5-FULL.etu` 只读观测值为：

| 项目 | 值 |
|---|---|
| 大小 | `281276 B` |
| SHA-256 | `334C77489100FC8D21551A6B610115BEBC10073903E39CCD298E2AFEA62B443F` |
| LastWriteTime | `2026-08-12T23:18:08+08:00` |

收尾时没有继续启动 simulator、构建、Python、J-Link 或 RTT 任务。生产源码未为验收而修改；未执行 commit、push、merge、rebase、reset、checkout 或 stash。

## 6. 后续复验的最短有效路径

下一轮不能从本轮中间状态直接续判 PASS。应建立新的证据目录，并按 R2 顺序重新执行：先冻结并统一 manifest 规范及 reproducible build 时间输入，完成 harness/provenance 审计，再运行计时、post-timing clean-first 生产构建、封包和 candidate 绑定，最后才通知用户拍照并立即执行 fresh 真机 OTA。任何前置 FAIL 应即时报告并停止占用用户时间。

本轮不修改看板：P2-5 仍为“阻塞”，P2 仍为 `4/6`。
