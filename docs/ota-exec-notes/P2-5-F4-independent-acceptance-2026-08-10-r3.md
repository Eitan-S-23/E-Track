# P2-5 F4 final-r5 独立验收报告 R3

生成时间：2026-08-12

## 0. 最终结论

本轮独立验收不通过。

- P2-5 必须保持“阻塞”。
- P2 必须保持 `4/6`。
- `PLAN-OTA-EXEC.md` 不得更新，本轮未更新。
- 最终矩阵为 `PASS 31 / FAIL 3 / NOT_OBSERVED 32`。
- 确定性阻断项为 fresh 生产模拟器真实 Startup 生命周期：4 轮仅 2 轮 PASS，且没有连续两轮 PASS；Run 2 和 Run 4 在约 33 秒时进入 `Responding=False / IsHungAppWindow=True`。
- 按 R2 fail-fast 要求，发现该强制门禁失败后，没有继续执行 F4 fixture、AC5、P16、生产 marker 扫描、finalize/封包/解包、SD、CLEAR_BCB、J-Link 生产 OTA 或真机视觉采集。

失败矩阵项：

| ID | 结论 | 原因 |
|---|---|---|
| SIM-2 | FAIL | 4 轮仅 Run 1、Run 3 PASS，`PassCount=2`，`ConsecutivePass=false` |
| SIM-3 | FAIL | Run 2、Run 4 挂起后缺少最终 health 和 final screenshot |
| SIM-4 | FAIL | Run 2、Run 4 在正常 WM_CLOSE 生命周期前已挂起并退出，四轮生命周期门禁未完成 |

原始矩阵：

- `.acceptance-p2-5-f4/20260810-200500/evidence-matrix.md`
- `.acceptance-p2-5-f4/20260810-200500/evidence-matrix.json`

## 1. 身份、边界与前置读取

- 活动 worktree：`D:\github\my\E-Track-p2-5-20260801`
- 基线与最终 HEAD：`0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e`
- 新证据目录：`.acceptance-p2-5-f4/20260810-200500/`
- 唯一验收标准：`.claude/prompt-P2-5-verification-r2.md`
- 验收身份：新的非实现独立验收会话，不继承历史 PASS/FAIL。

开始前完整读取了 R2 第 2 节指定输入：

1. `AGENTS.md`
2. `PLAN-OTA-EXEC.md` 第 0 节、P2-5 卡和第 10 节
3. `.claude/prompt-P2-5-verification.md`
4. `.claude/prompt-F4-remediation.md`
5. `docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-09-r2.md`
6. `docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09-r3.md`
7. `.remediation-p2-5-f4/20260810-084053/final-production-cleanup-r5.json`
8. `.remediation-p2-5-f4/20260810-084053/final-snapshot-r5/07-snapshot-summary.json`
9. `.remediation-p2-5-f4/20260810-084053/source-freeze-r4/` 源码冻结证据
10. `.remediation-p2-5-f4/20260810-084053/timing-r4/` 插桩与计时证据

这些文件只作为待复核输入。R2 与旧资料冲突时使用 R2。

前置 Git 证据全部在 `preflight/`：

| 证据 | SHA-256 |
|---|---|
| `01-show-toplevel.txt` | `11CBCB1F144F95339889CBE836578B014716C7F9878343398968FF781F31CCBE` |
| `02-head.txt` | `8D0E37841297ADA7299CF25EE2CE8BD9FD0EF7A5A28BA17B4FCDEF0CE1C391A8` |
| `03-git-status-full.txt` | `E7802B7D80556105EACA391876B46BDF3EFF6BC9AB9B79CE331F6B51099C01B4` |
| `04-git-status-porcelain-v2.txt` | `96B20AEDA9DB7A42BB8CFB0BB58662F9BEF0FF8258588F4231F76EDDEF3628C6` |
| `05-tracked-diff-binary.patch` | `8A68EE10C5F4DBEFCDA1A72C6C3328CB4B94304066167A9986E918B3E7661390` |
| `06-tracked-diff-name-status.txt` | `BFCA5DD4282C938238FD6363DBBCB880E731CCCCD342D71EADC2BC01BA0AF30F` |
| `07-untracked.txt` | `4A38A2DB0061A396DF329F5CDFF3FD82466CE7480D2784CFAE2CA8C385202277` |
| `08-git-diff-check.txt` | `A6ADFFFCD5AB5D3BE4C06F3471B6B7087F617F92FDB8184AC95F988F29C7AB22` |

所有矩阵条件初始状态均为 `NOT_OBSERVED`。本轮没有 commit、push、merge、rebase、reset、checkout 或 stash，也没有修改生产实现源码。

## 2. Harness 与 provenance 审计

R14 是 simulator 生命周期执行前最后一次完整 harness/provenance/toolchain 审计。结论为 `APPROVED`：

| 项目 | 值 |
|---|---:|
| Harness delta | 4 |
| PowerShell parse error | 0 |
| Constant required outcome | 0 |
| Invalid contract | 0 |
| Provenance mismatch | 0 |
| Repository input mismatch | 0 |
| Toolchain mismatch | 0 |

R14 原始证据：

| 文件 | SHA-256 |
|---|---|
| `audit/harness-inventory-r14.json` | `012F46E403F5D13E3684ECBB1896BFE5A6CD60E71EBE9A01EEF40E507D08CD1F` |
| `audit/harness-static-scan-r14.json` | `5D9941CA1FD69172B1D40921AB95EE36D568DC0E0EF9514A0658D29B92973ACD` |
| `audit/provenance-independent-verification-r14.json` | `317C31D18B243D077AE063418E1439C984F3386558B51D7A5A83CD5CE6CB854B` |
| `audit/toolchain-inventory-r14.json` | `686E55B948FE681077218013C405B603EC6EAF1F693B5D46AE1E68DD17FF8F70` |
| `audit/python-ast-r14.json` | `65C998E506C5AA446B777BFF10003AA47ED9A6DE06705DD7AC71CBF89FAAA288` |
| `audit/r14-preexecution-audit.txt` | `3217A35A92B605B85B05AE012FF41EC8736A15A6BD8D9054D04C2AC36970F0EA` |

审计确认：没有 `CandidateAndStagePassed=true` 代理视觉结论，没有未审计 `Invoke-Expression`，Force 仅用于失败清理或 WM_CLOSE 超时后，J-Link halt 受限。HAR-1、HAR-2、HAR-3 均为 PASS。

## 3. 已独立通过的门禁

### 3.1 同源隔离计时

真机 Timing Attempt 04 使用冻结生产源码派生的隔离插桩镜像。原始 summary：

- 路径：`hardware/timing/attempt-04/summary.json`
- SHA-256：`652A51C39E276B015FE4ED8BCF8562B1C7769347EFAABCAF31E534BEE75E2008`

独立结果：

| 条件 | 观测值 | 门槛 | 结论 |
|---|---:|---:|---|
| 首次根目录 LoadFiles | `38054 us` | `<= 320000 us` | PASS |
| 返回后再次进入 LoadFiles | `38061 us`、`38003 us` | `<= 320000 us` | PASS |
| 两次 F4ACC 256 项扫描 | `46549 us`、`46435 us` | `<= 320000 us` | PASS |
| 首次输入到可操作列表上界 | `814387 + 100000 = 914387 us` | `<= 917000 us` | PASS |
| 再次进入输入上界 | `914199 us`、`914109 us` | `<= 917000 us` | PASS |
| 32 次读取服务上界 | `19008 us` | `< 10000000 us` | PASS，余量 `526.09x` |

计时插桩 patch SHA-256 为 `44421E16FE7AE11E68D7B0A059C6CFD482DC498485304948A2C61F24974CBFA2`，探针开销证据 SHA-256 为 `FA96544335C6EBB8EA2F9D5307F4D7E507278221D94354F5F0462245BEBCE120`。

Timing Attempt 04 地址来自该次 fresh map：

| 符号/寄存器 | 地址 |
|---|---|
| `_SEGGER_RTT` | `0x20053E14` |
| RTT up buffer | `0x20053A14` |
| EncoderDiff | `0x20053118` |
| SDReady | `0x2005320C` |
| OtaStateSnapshot | `0x20053EBC` |
| vcode | `0x08010408` |
| VTOR | `0xE000ED08` |
| CFSR | `0xE000ED28` |
| App origin | `0x08010000` |

地址证据为 `hardware/timing/attempt-04/addresses.json`，SHA-256 `8F004288EC7C8B1153773F088937CA53C6F6768050166CBA91F646F08AF37BD6`。

### 3.2 12 组宿主测试

Host Tests Attempt 02 全部通过：

- 汇总：`pipeline/hosttests-attempt-02/summary.json`
- 汇总 SHA-256：`81CA67D916FFEE06D20D81DA78C0A7C5520CFB7BE49D6051BED43CD98BE603D3`
- Test count：12
- Pass count：12
- Nonzero exit：0
- `tests/ota/test_sdio_command_timeouts.py` 原始日志 SHA-256：`B739E25985378C7B0627C7002AA441EFC37836BB61F01EA60CFBA913B235FCBC`
- SDIO 标记：`SDIO_COMMAND_TIMEOUTS=PASS functions=9`

HOST-1 到 HOST-12 均为 PASS。

### 3.3 Post-timing clean-first GCC App/Boot

R13 审计后，从活动生产源码执行了 target-limited clean-first App/Boot 构建。旧 raw App 参考哈希断言因 GCC `__DATE__/__TIME__` 变化而拒绝 fresh App；R14 `PostTimingBind` 随后独立证明差异只包含 10 个构建时间戳字节。

| 产物 | 大小 | SHA-256 |
|---|---:|---|
| fresh raw App | `598852 B` | `6436AF0BBBCDA78BF3E7FEA3C5660B2EBA326FD7BF08E928A002C79B83D7ACF5` |
| fresh Boot bin | `14724 B` | `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |
| fresh Boot hex | `41485 B` | `FF3BADEF69BE6D97FD66815B8DF90EFD962A708B559C8951D4B56380F8001F71` |

关键证据：

| 文件 | SHA-256 |
|---|---|
| `pipeline/posttimingbuild-attempt-02/03-production-build-clean-first.log` | `E7B92C4CE1CE9997744D3F4F9358911C08E2F5AF0ADEACFD3D67EC4D735D4B99` |
| `audit/posttiming-attempt-02-build-stamp-comparison.json` | `3DBD963E91C13168479AF861BF40B3A78E5E1C74FDE355107EFFCF058A91CC77` |
| `execution/posttimingbuild-attempt-02-protected-after.json` | `56EAD4FB7F233F47AEE5824E8FBD8AEF9A68AF6CBA92D7AE35EC49E9FF5E2CC4` |
| `pipeline/posttimingbind-attempt-01/summary.json` | `2DBDB1A2E3F708A5837C1BB52E37BFFFC13281A3BF58333D455FBDE63DBCB861` |
| `pipeline/posttimingbind-attempt-01/02-boot-readelf.log` | `0E8F4F1A36ACF6B96F04D7D6DB4586E8EEF07E02673483B234CC6D6979391A56` |

PostTimingBind 结果：source mismatch 0、active-source path bound、build error/FAILED 0、build-stamp 归一后 byte-identical、Boot LOAD=3、RWE LOAD=0。TIME-8、BUILD-1、BUILD-2 均为 PASS。

## 4. Fresh 生产模拟器

### 4.1 Rebuild 通过

执行命令：

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".acceptance-p2-5-f4\20260810-200500\run_pipeline.ps1" -Phase SimulatorBuild

结果：

| 项目 | 值 |
|---|---|
| Rebuild exit | `0` |
| Error matches | `0` |
| Warning matches | `102` |
| Active source path bound | `true` |
| Fresh EXE size | `5879296 B` |
| Fresh EXE SHA-256 | `B40EF24B898D5F7BA02CE62A7817A361520E6735D91E809D751BB8D00424DD3B` |
| 残留 simulator | `0` |

证据：

- `pipeline/simulatorbuild-attempt-02/summary.json`，SHA-256 `431C5407587C379D984FF8AB85DA178214922A6C593DA7671C429D5314FF675A`
- `pipeline/simulatorbuild-attempt-02/01-msbuild-rebuild.log`，SHA-256 `1AD949C3947F7A86E2D808457B4AD898A5B027889AC770213BE1B42A89718D68`
- `simb2/out/LVGL.Simulator.exe`，SHA-256 `B40EF24B898D5F7BA02CE62A7817A361520E6735D91E809D751BB8D00424DD3B`

SIM-1 为 PASS。

### 4.2 生命周期强制门禁失败

精确复现命令：

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".acceptance-p2-5-f4\20260810-200500\sim_runner.ps1" -Mode Lifecycle -RunCount 4

工作目录：

    D:\github\my\E-Track-p2-5-20260801

被测 EXE：

    .acceptance-p2-5-f4\20260810-200500\simb2\out\LVGL.Simulator.exe

被测 EXE SHA-256：

    B40EF24B898D5F7BA02CE62A7817A361520E6735D91E809D751BB8D00424DD3B

原始汇总：

- 路径：`simulator/lifecycle/logs/results.json`
- SHA-256：`CBA9757979A999F0352CB81DF2653B9466A937408E81BEF8A129EEBB01205EAC`
- `CompletedRuns=4`
- `PassCount=2`
- `ConsecutivePass=false`
- `Status=FAIL`

逐轮结果：

| Run | PID | HWND | Startup | Main | 最后健康观测 | Close | 结论 |
|---:|---:|---|---:|---:|---|---|---|
| 1 | `4504` | `0x1098E` | `5134 ms` | `8268 ms` | Responding=True, Hung=False | WM_CLOSE, residual 0 | PASS |
| 2 | `13980` | `0x209F8` | 未观测 | 未到达 | `32842 ms`: Responding=False, Hung=True, CPU=`84.672 s` | ALREADY_EXITED, Force=False | FAIL |
| 3 | `12668` | `0x309F8` | `2478 ms` | `4809 ms` | Responding=True, Hung=False | WM_CLOSE, residual 0 | PASS |
| 4 | `16376` | `0x409BC` | `2302 ms` | 未到达 | `33160 ms`: Responding=False, Hung=True, CPU=`81.516 s` | ALREADY_EXITED, Force=False | FAIL |

逐轮 CSV SHA-256：

| Run | 路径 | SHA-256 |
|---:|---|---|
| 1 | `simulator/lifecycle/logs/run01-samples.csv` | `73E5CE77251BD53A0D2982875217A6040455CB2DD6C083C9B41ADAE59AC1442E` |
| 2 | `simulator/lifecycle/logs/run02-samples.csv` | `F456D265DF27D569AEFC4CE9030068AC9A7E8C893A98410259F24B3E622EE0BA` |
| 3 | `simulator/lifecycle/logs/run03-samples.csv` | `2B7438E3C0B4F88DDD462E5729187F1324680CA9E658D9961A5B6EF5A2C9BF4E` |
| 4 | `simulator/lifecycle/logs/run04-samples.csv` | `C82C077D7066C94C46C0443B11BA3896656E577DACCE3E1D5746252CCC232022` |

失败轮截图：

| Run | 路径 | SHA-256 |
|---:|---|---|
| 2 | `simulator/lifecycle/screenshots/run02-startup.png` | `32C1F9020ED6A92FE9B35B71CE39DEBBEE439E96330341151EAB6D70C886C0E2` |
| 4 | `simulator/lifecycle/screenshots/run04-startup.png` | `705657ADE5E566BFDDEFCDBBEC1B1274A7E4BDB0F4449226398BC49B12EDA800` |

原图显示失败轮客户端没有完成稳定绘制，捕获区域暴露了后方桌面/控制台内容。该视觉现象与同轮 `Responding=False / Hung=True` 原始进程样本一致。Run 2、Run 4 没有 final screenshot 和最终 health 对象，因此 SIM-3 不能通过。

R2 要求至少 4 次连续独立启动、至少两次连续 PASS，并要求真实 Startup、健康数据、截图和正确 WM_CLOSE 生命周期。本轮四轮虽然全部启动了独立 PID，且没有使用 Force，但只有 Run 1、Run 3 PASS，失败条件被直接满足，因此 SIM-2、SIM-3、SIM-4 均为 FAIL。

本报告不进一步推断根因，也不修改生产代码尝试凑结果。该强制门禁失败已足够触发 fail-fast。

## 5. Fail-fast 后未执行项

以下矩阵项保持 `NOT_OBSERVED`，没有使用历史报告、实现汇总、模拟器代理字段或用户旧口述补齐：

- PROV-3：source、finalized App、ETU、candidate、map、device 全链绑定。
- F4-1 到 F4-8：扫描边界、截断提示、空/only-up/exact-bound、deviceReady 优先级、正常 ETU 二次确认、布局、返回和再次进入。
- GATE-1、GATE-2：Begin/Apply 在非 CONFIRMED 下拒绝且无副作用。
- BUILD-3：AC5 正式尝试。
- BUILD-4：最终生产 App/Boot/ETU/candidate 的 forbidden marker 扫描。
- PKG-1、PKG-2：fresh raw App finalize 为 v20800/v20801、封包、解包及 candidate 逐字节比较。
- SDIO-1 到 SDIO-3：生产静态 9 条等待绑定及两类各 3 次真机软件复位恢复。
- SD-1、SD-2：E: 完整根清单、唯一覆盖 `E:\P2-5-FULL.etu`、SD 回读。
- JLINK-1：post-timing 生产 map RTT 地址解析和 `SEGGER RTT` 签名。
- BASE-1：正式 P1-6 CLEAR_BCB 恢复 final-r5 v20800 CONFIRMED。
- OTA-1 到 OTA-6：v20800 到 STAGED/APPLYING/TEST_BOOT/CONFIRMED、二次复位及最终状态。
- UI-1 到 UI-4：本轮真机连续录像或照片及 SHA-256。

因此没有取得本轮 fresh 真机 `CANDIDATE VERIFY`、`BACKUP + STAGED`、导入成功结果页、升级后正常界面/编码器/返回操作的图像原文件。UI-1 到 UI-4 必须保持 `NOT_OBSERVED`。

## 6. 当前设备与产物状态

- 设备仍运行本轮隔离计时 v20801 固件，不是 post-timing clean production OTA 基线。
- 隔离计时 finalized App：`599708 B`，SHA-256 `59E465902FD82C06D8AF92C85E163C4476A5C95763CC0F80330DC3A8051C1EE3`。
- fresh post-timing raw App 已构建并绑定：`598852 B`，SHA-256 `6436AF0BBBCDA78BF3E7FEA3C5660B2EBA326FD7BF08E928A002C79B83D7ACF5`。
- fresh post-timing Boot 已构建并绑定：`14724 B`，SHA-256 `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594`。
- 因 simulator fail-fast，fresh raw App 没有在本轮 finalize、封包、写 SD 或烧录到设备。
- 没有执行 P1-6 CLEAR_BCB，也没有直接修改 EEPROM。
- 没有写入 E:，包括 `E:\P2-5-FULL.etu`。

## 7. 最终清理与写入边界

Cleanup Attempt 01 和 Attempt 02 均保留但排除：

- Attempt 01：PowerShell 函数参数名与自动变量 `$args` 冲突，实际调用 bare `git`。
- Attempt 02：错误地比较了分离 stdout/stderr 的 raw hash，而 preflight 文件合并了 stderr 警告与 stdout patch，并使用不同换行编码。

Cleanup Attempt 03 使用同一语义顺序拼接 stderr+stdout，并将 CRLF 归一为 LF。preflight 与最终 tracked diff 的归一 SHA-256 均为：

    8514CA662D7AAEA6501FC0275E12E4B47B650D81A62A6820BD0ECC63BF45EEDB

最终 cleanup 结果：

| 检查 | 结果 |
|---|---|
| HEAD | 精确等于 `0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e` |
| git status/diff/diff-check 命令 | exit 0 |
| tracked diff 对开场快照 | 归一后完全相等 |
| 5 个保护活动产物 | mismatch 0 |
| `2026-08-12T03:38:00` 后证据根之外近期写入 | 0 |
| LVGL.Simulator / MSBuild / cl / JLink 残留 | 0 / 0 / 0 / 0 |
| E: 写入 | false |
| PLAN 更新 | false |

证据：

| 文件 | SHA-256 |
|---|---|
| `final-audit-attempt-03/summary.json` | `D1E6385F72F5E9F2BC368A4A0C3D124AE6045EA0BD989002A953199EE4470D79` |
| `final-audit-attempt-03/01-tracked-diff-normalized-comparison.json` | `00ACE5BE634CA0129BB808B04247CA27BF4DC4E2C8A767AE604EB70F9DC5281F` |
| `final-audit-attempt-02/05-protected-files.json` | `DB5C028FDF74BAD899CD67DB68FC38DD8DEED6E73B7EEC090FEA5557733A61F2` |
| `final-audit-attempt-02/06-processes.json` | `A7CBDA1A694D1231FC4692B8301639CEAF5394D11CC9BB3E3228755CBA64962F` |
| `final-audit-attempt-02/07-recent-outside-evidence.json` | `7EB70257593DA06F682A3DDDA54A9D260D4FC514F645237F5CA74B08F8DA61A6` |

CLEAN-1 为 PASS。本报告是 R2 明确允许的独立验收报告写入，位于活动 worktree 内；除此之外没有新增证据根外输出。

## 8. 看板决定

R2 规定只有全部强制项 PASS 才能把 P2-5 改为完成并把 P2 改为 5/6。本轮存在 3 个 FAIL 和 32 个 NOT_OBSERVED，因此：

- P2-5：保持“阻塞”。
- P2：保持 `4/6`。
- 不在 `PLAN-OTA-EXEC.md` 第 10 节追加通过日志。
- 不修改任何生产实现代码继续凑结果。

下一轮必须先修复或独立解释并消除 fresh 生产模拟器真实 Startup 的交替挂起，再从新的证据目录重新执行 R2。不得复用本轮 SIM-2、SIM-3、SIM-4 结论为 PASS。
