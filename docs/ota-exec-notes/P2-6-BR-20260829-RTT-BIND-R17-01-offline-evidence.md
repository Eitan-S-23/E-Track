# P2-6-BR-20260829-RTT-BIND-R17-01 离线实现与自证证据

- 日期：2026-08-29（初版）；同日 B-1 整改（见 §7）
- 证据根：`D:\github\my\E-Track\.cache\p2-6-rtt-binding-20260829-15`（执行前确认不存在，本会话创建）
- 分支：`p2-6-implementation-20260819`，HEAD=`99173123cae8c487b86efa8a4eecbbe73b1bb512`（与 origin/main 一致）
- 硬件状态：**hardware_started=false**（未启动任何 J-Link/GDB/RTT 会话）
- R16（`20260829-14`）、R15（`20260828-13`）、R14（`20260828-12`）根只读未动（R14/R15 manifest mtime 保持 2026-08-28，R16 根 0 个文件被改）

## 1. 交付脚本与 SHA-256（共 12 冻结 + 7 生成 = 19）

### 1.1 原样继承（4 个，SHA 与验收钉死值一致）

| 文件 | SHA-256 |
|---|---|
| binding.gdb.in | `6FC845B5343F48A0088926BFC5CB91BA70C2ED0CCE07977D0732598448294281` |
| generate_binding_gdb.py | `3322EF140F6B0F7D63265A356F883C7E85941B04822D7B03E628EC947D6F4062` |
| jlink-settings.ini | `849D80A1B2985411396B1884A8BE4717ECE4B4A77BA10E08E36FE408A80B1C13` |
| precall_audit.py | `CCA63DDB0760C46BD02DADF2578B50F394949DB2557B378EF06F367982E50A24` |

### 1.2 修改/新增（本会话产物；带 † 者为 B-1 整改后版本，SHA 以本表为准）

| 文件 | SHA-256 | 角色 |
|---|---|---|
| binding_host.py | `2AC18A4D1997C040DDBD5D3C4F0D0C41420E029FB1E16AE24C0FDCAD01FCB52F`（连续 64 位，无空格） | 按 F1/F2/F6 修改 |
| recovery_policy.py | `8F0B0F8191E88AC9FD9302D6EF8553BFFB4E74063C0ED4D519ED537F201B1973` | 策略模块 |
| run_recovery_binding.py † | `8D73A0E549359D4D11003F6FAA8F017731BC70945C98BE60289DA0429D752D8D` | 唯一启动入口（含 B-1 自举+断言） |
| run_readback.py † | `386746076DCF4CDFFF5DE10EABC7B3BF6174A675580143C1E0405D77D546241D` | 每遍运行器（含 B-1 自举） |
| generate_readback_gdb.py | `369C9D4B1CCA18F2B09160A22D66338FEC74A92560A18157C5B490E0019BD235` | 读回脚本生成器 |
| readback.gdb.in | `44CE98A96F97A1B1A1175AAA3076919EED412F28AA1BF730142E214A19E29755` | 只读分块读回模板 |
| run_binding.py † | `1F8756E46CC01ED8A0C3128F778F1E95AD9FA8D8A189D279104E8952F55DDD31` | binding 运行器（仅闸门后调用，含 B-1 自举） |
| test_recovery_policy.py † | `36658C54DEAA77540C859FAEB22A00EAAA8B6394B08BBB8E7421104B0325F956` | 离线 unittest（45 条） |
| binding.gdb（生成） | `E30EBE2795F5C5A2FBDA2DF1FB26C183152342AA42043BE58D737F7AAE28BB09` | 继承生成器物化 |
| readback-gate-pre-a/b/c.gdb（生成） | `2B414434653A0AF68B83F2B77D41C0AB607E444E706A70633FED9DA2C87B9CB7` / `2A103FFCEFA9BCA0C29410A166978F09A3E732CF1B8E7B45569ED58970FFBBE7` / `9EE1EEE7AEBF0FE3394C4DADF9E34AB8AD2849EE99A18307ABECEFBC25D55BC7` | 每遍独立脚本 |
| readback-gate-post-a/b/c.gdb（生成） | `585A4F0F53079E349AC2B03B271562CAD124F7E7F44207CD0623A505D3029B63` / `D7C76BE53E664807355C1BEE9073D0B157079CB9BDE152F752FED47958557C57` / `62F0F915E6014219C7754BB52FDE7E209661E4D1EA1FAEF673CDEC437628C5BC` | 每遍独立脚本（Flash 后相位） |

### 1.3 binding_host.py 变更点（F1/F2/F6）

- **F1**：`reconstruct_chunked_board()` 删除 2-of-3 多数表决、disagreement 容忍与 lenient pass；逐块要求 `sha(a[i])==sha(b[i])==sha(c[i])`，任一块不等立即抛 `BOARD_IMAGE_READ_INCONSISTENT`；三遍独立写出 `board-image-{a,b,c}.bin`；新增 `APP_ORIGIN/APP_IMAGE_BYTES/APP_IMAGE_END/AUTHORITATIVE_APP_SHA256/BOARD_CHUNK_COUNT` 常量。
- **F2**：删除旧 `identity()` 中"重建结果 vs 它自己刚写出的文件"的自证比较；新增 `validate_pass_authority()` 独立读回三份重建镜像，互相逐字节比较，并各自与权威 SHA `A2D3083B...D58E00` 比较（不符抛 `BOARD_IMAGE_AUTHORITY_SHA_MISMATCH`）。
- **F6**：`identity()` 中 `dump_size = max(candidate.st_size)` 删除，钉死为常量 600744，并在重建前断言覆盖区间恰为 `0x08010000..0x080A2AA8`。
- precheck/capture/postcheck 相位与 CLI 未改。

## 2. 六个阻断缺陷的修复落点

| 缺陷 | 修复 |
|---|---|
| F1 majority | `binding_host.reconstruct_chunked_board` 严格三遍逐块相等；`recovery_policy.classify_gate_consensus` 三镜像逐字节比较；全脚本文本扫描 majority/vote 出现次数=0（含测试断言） |
| F2 自证同义反复 | `validate_pass_authority` 三镜像互比 + 各比对权威 SHA；旧自证块删除 |
| F3 三遍同进程 | 每遍独立 `readback-<phase>-<label>.gdb` + 独立 JLinkGDBServerCL（-singlerun，端口 24361-24364）；每遍结束 `monitor go` 恢复运行 + JLink.exe `IsHalted` 探针证明 running + 端口/进程自然清零后才进下一遍；生成器内断言每遍 dump 行=147（原 458 已重新推导） |
| F4 无 core 状态证明 | 每块 dump 前后各读一次 DHCSR(0xE000EDF0) 并 printf `P2_6_RB DHCSR ... s_halt=N`；运行器解析 294 个标记/遍，任一 s_halt=0 即失败 |
| F5 读写未分离 | readback 脚本全程 `may-write-memory/registers/call-functions/breakpoints/tracepoints off`，零 target write（生成器+静态审计双重断言）；闸门通过（含 Flash 后三遍全等权威 SHA）→ 一次最终 reset/prove-running → 才由独立子进程进入 binding |
| F6 读回长度不钉死 | dump_size 钉死 600744 常量；区间断言 `0x08010000..0x080A2AA8`（600744 = 0x92AA8，末块 2728B） |

## 3. 离线自证命令与结果

### 3.1 py_compile（全绿，字节码在项目内）

```
cd D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-15/scripts
C:/Users/SU/AppData/Local/Programs/Python/Python313/python.exe -c "…py_compile.compile(src, cfile=D:/github/my/E-Track/.cache/p2-6-r17-offline-tests/pycache/<name>.pyc, doraise=True)…"
→ PY_COMPILE_OK × 9（binding_host/generate_binding_gdb/generate_readback_gdb/precall_audit/recovery_policy/run_binding/run_readback/run_recovery_binding/test_recovery_policy），TOTAL=9
```
TEMP/TMP/TMPDIR 与 PYTHONPYCACHEPREFIX 全部重定向至 `D:\github\my\E-Track\.cache\p2-6-r17-offline-tests\{tmp,pycache}`，未使用系统 TEMP；scripts/ 目录无 __pycache__ 残留。

### 3.2 test_recovery_policy.py（45/45 全绿，exit=0）

```
PYTHONDONTWRITEBYTECODE=1 P2_6_OFFLINE_TEST_ROOT="D:/github/my/E-Track/.cache/p2-6-r17-offline-tests/scratch" \
  python.exe test_recovery_policy.py
→ Ran 45 tests in 15.625s / OK
完整日志：.cache/p2-6-r17-offline-tests/test-run.log
```

验收点名三例均在其中：
- `test_chunk_level_a_equals_b_differs_from_c_fails_closed`：a==b!=c → `BOARD_IMAGE_READ_INCONSISTENT`
- `test_r14_clear_only_drift_allows_exactly_one_recovery`：三遍全等但 != 权威 SHA → header 精确校验 + clear-only 判定分支，`build_flash_plan` loadbin=1/verifybin=1/reset=0
- `test_reverse_bit_drift_fails_closed_without_flash_or_reset`：reverse-bit 差异 → `UNEXPECTED_BOARD_IMAGE`，loadbin=0/reset=0

其余覆盖：R15 三快照判 inconsistent（loadbin=0/reset=0）、权威三遍一致不 Flash、chunk missing/extra/size/stale/未钉死尺寸、DHCSR 中途 running、日志 Error 行（退出码 0 也失败）、异遍标记、server halt/go 回显唯一性、探针 running 证明、生成器 147/294/区间/无 gap-overlap-duplicate、readback 生成物无 reset/loadbin/erase、loadbin 命令仅存在于 flash 计划构建器、majority/vote/retry/taskkill/TerminateProcess 全脚本 0、manifest missing/extra/mismatch/duplicate/late-write/reparse 六检、自然清零不强制终止、handoff v4 双成功分支与非法 loadbin 拒绝。

### 3.3 离线静态审计（exit=0，无硬件）

```
python.exe run_recovery_binding.py --audit-id P2-6-BR-20260829-RTT-BIND-R17-01 \
  --evidence-root D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-15 --offline-audit
→ schema=p2-6-r17-offline-static-audit-v1, pass=true, hardware_started=false
完整输出：.cache/p2-6-r17-offline-tests/offline-audit.json
```
审计要点（实测值）：
- majority/vote 文本扫描 occurrences=**0**；retry/taskkill/TerminateProcess 字样 **0**；AST 生命周期强制调用 **0**
- 6 个 readback 脚本：dumps=**147**/脚本、DHCSR 标记=**294**/脚本（=2×147）、coverage=**0x08010000..0x080A2AA8**、gaps=0/overlaps=0/duplicates=0
- 14 项钉死输入哈希全部复核（ELF 35BB2AB7…、MAP 2446B401…、权威镜像 A2D3083B…（600744B，restore 与 frozen 双份一致）、JLink.exe 9A498039…、GDBServer 1EED5ED1…、GDB 9BF61D2F…、nm/objdump、driver/qualifier/preflight/uploader harness、identity tool 50D778DE…、Python313）
- binding.gdb 物化 + 路径审计 0 错误；受控调用符号/空基反汇编审计通过；git 三元组一致
- 未授权动作：全部 GDB/JLink 命令文件仅由 `build_flash_plan`（loadbin×1/verifybin×1）/`build_reset_plan`（r×1）产出并经 `audit_command_plan` 计数审计；readback/binding 脚本无 reset/loadbin/erase/SD/OTA/BCB/QSPI 命令

### 3.4 新根启动前状态

- 根内容 = `scripts/`（19 文件）+ 空的 `baseline/ logs/ snapshots/ tmp/`；**无 manifest.json**
- reparse/junction/symlink 计数 = **0**（根+全递归）
- 端口 24361-24364 LISTENING = **0**；JLink/JLinkGDBServerCL/JLinkGUIServer/JLinkRTTLogger/gdb 相关进程 = **NONE**
- 4 个继承脚本 SHA 与钉死值逐字节一致

## 4. 静态动作矩阵

| 输入判定 | 动作 | loadbin | reset | 重复 |
|---|---|---|---|---|
| 三遍逐块一致 且 重建镜像逐字节相等 且 == 权威 SHA | BOARD_IMAGE_AUTHORITATIVE：**不 Flash** → 一次最终 reset/prove-running → binding | 0 | 1 | 无 |
| 三遍一致、header 精确有效、仅稳定 clear-only 漂移 | STABLE_CLEAR_ONLY_FLASH_DRIFT：**至多一次**完整 App loadbin/verifybin → gate-post 三遍复读（必须全部 == 权威 SHA）→ 一次 reset → binding | 1 | 1 | 无 |
| 三遍一致但 header 无效或存在 reverse-bit | UNEXPECTED_BOARD_IMAGE：FAIL_NO_FLASH | 0 | 0 | 无自动重试 |
| 任一块三遍 sha 不等 / chunk missing/extra/size 错 | BOARD_IMAGE_READ_INCONSISTENT（或对应 chunk 失败码）：FAIL_NO_FLASH | 0 | 0 | 无自动重试 |
| 任一遍进程/日志（含 Error 行）/DHCSR/清零异常 | 对应失败码，fail-closed 终止 | 0（未到 Flash） | 0 | 无自动重试 |
| 永不 | majority 修复、补零、terminate/kill、Boot Flash、SD、OTA、BCB、QSPI、R4 重跑、历史配额 | — | — | — |

## 5. manifest 覆盖清单与写入顺序（硬件成功路径预期）

写入顺序（每步失败即 fail-closed 封存）：
1. `scripts/` 12 冻结脚本（实现期）→ 2. 静态审计物化 `binding.gdb` + 6 个 `readback-*.gdb` → 3. `baseline/pre-recovery.json`、`logs/recovery-static-audit.json` → 4. gate-pre：每遍 `logs/readback-gate-pre-<label>-{server.log,gdb.log,probe.jlink,probe.log,server-command.json}`（15 文件）+ `snapshots/gate-pre/` 441 chunks + 3 `board-image-*.bin` → `logs/gate-pre.json` → 5.（漂移分支）`logs/recovery-flash.{jlink,log}` + gate-post 全套（15 日志 + 444 文件 + `gate-post.json`）→ 6. `logs/recovery-reset.{jlink,log}` → `logs/recovery-result.json` → 7. binding 子进程：`baseline/pre-hardware.json`、`logs/{jlink-server.log,gdb.log,identity.json,precall.json,precheck.json,capture.json,postcheck.json,controlled-call-static-audit.json,rtt.raw.log}`、`snapshots/` 平铺 `board-header.bin` + 441 `board-chunk-*.bin` + 4 `spot-*.bin` + 12 个 sram/rtt-cb/up0/measurement dump + `board-image-{a,b,c}.bin` + `pending.bin` + `telnet-payload.bin` → `logs/result.json` → 8. **`manifest.json` 最后写入**（自排除、双清单比对 + late-write/reparse/duplicate 检测 + 写后自校验）。

## 6. 硬件启动命令（唯一，供独立验收会话执行）

```
C:/Users/SU/AppData/Local/Programs/Python/Python313/python.exe ^
  D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-15/scripts/run_recovery_binding.py ^
  --audit-id P2-6-BR-20260829-RTT-BIND-R17-01 ^
  --evidence-root D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-15
```

bash 形式：
```
cd /d/github/my/E-Track && "C:/Users/SU/AppData/Local/Programs/Python/Python313/python.exe" \
  .cache/p2-6-rtt-binding-20260829-15/scripts/run_recovery_binding.py \
  --audit-id P2-6-BR-20260829-RTT-BIND-R17-01 \
  --evidence-root "D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-15"
```

前置条件：端口 24361-24364 无监听、无 J-Link/GDB/RTT 残留进程（本会话已验证为 0）；根保持 baseline/logs/snapshots/tmp 全空。

## 7. B-1 整改记录（2026-08-29，响应独立验收 INDEPENDENT_ACCEPTANCE_FAIL）

**缺陷**（验收 B-1）：入口在模块级 import 四个同目录模块，默认环境下 CPython 于 import 时写 `scripts/__pycache__/*.pyc`（先于 main()），使 scripts 名字集合变为 20 项，`validate_pristine_root()` 必然 `SCRIPT_ROOT_INVALID`、退出码 2；`--offline-audit` 同样中招。冻结命令本身照抄跑不起来。

**修复方向**：采纳验收建议 a（入口自举）并叠加 c 的断言（不依赖命令行前缀，不变量由入口自己保证）。

**修复落点**（4 个脚本，SHA 已更新进 §1.2，标 †）：
- `run_recovery_binding.py` / `run_binding.py` / `run_readback.py` / `test_recovery_policy.py`：在**第一个本地模块 import 之前**置 `sys.dont_write_bytecode = True`（`run_binding.py` 另 `os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")` 使子进程继承）。
- `run_recovery_binding.py` `validate_static_inputs()` 开头新增断言：`sys.dont_write_bytecode` 为假即抛 `BYTECODE_BOOTSTRAP_DISABLED`——若未来有人把自举挪走，静态审计自己会挡住。
- 新增 2 条离线测试：`test_static_audit_requires_bytecode_bootstrap`（负例：mock 关掉自举标志 → 必须抛 `BYTECODE_BOOTSTRAP_DISABLED`）、`test_entry_points_bootstrap_bytecode_flag_before_local_imports`（四个入口的标志位必须出现在任何本地 import 之前）。测试总数 43→45。（更正记录：原文写"新增 3 条""原有 45 条总数不变"，实际新增即上列 2 条、整改前为 43 条——由 R18 验收以整改前 .pyc 取证指出，R19 会话更正；本段上文与 §3.2 的 45 计数为整改后口径，不受影响。）

**默认环境复现验证**（验收的精确复现路径，`env -u PYTHONDONTWRITEBYTECODE -u PYTHONPYCACHEPREFIX -u TMP -u TEMP -u TMPDIR`，无 `-B`）：

```
env -u PYTHONDONTWRITEBYTECODE -u PYTHONPYCACHEPREFIX -u TMP -u TEMP -u TMPDIR \
  python.exe .cache/p2-6-rtt-binding-20260829-15/scripts/run_recovery_binding.py \
  --audit-id P2-6-BR-20260829-RTT-BIND-R17-01 \
  --evidence-root D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-15 --offline-audit
→ OFFLINE_AUDIT_EXIT=0；__pycache__/*.pyc 计数=0；scripts/ 仍为 19 文件且
  19 个 SHA 与运行前逐字节一致（SCRIPTS_IDENTICAL）；pass=true, hardware_started=false
完整输出：.cache/p2-6-r17-offline-tests/offline-audit-default-env.json
```

整改前该路径为 exit 2 + 4 个 .pyc（验收方隔离复现）；整改后 exit 0、零污染。§6 冻结命令**未改动**（自举使命令无需任何环境前缀）， hardware 配额未被消耗，历史根未触碰。

**整改后全量复跑**：py_compile 9/9 OK；test_recovery_policy.py 45/45 OK（15.625s）；离线静态审计 pass=true。
