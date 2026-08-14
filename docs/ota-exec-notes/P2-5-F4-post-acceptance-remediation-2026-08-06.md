# P2-5 F4 独立验收失败后补救证据（2026-08-06）

## 0. 结论与边界

- 活动 worktree：`D:\github\my\E-Track-p2-5-20260801`
- 分支：`p2-5-20260801`
- HEAD：`0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e`
- 输入报告：`docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-06.md`
- 本轮只处理该报告指出的两个硬阻断，不修改 F4 生产逻辑，不执行 commit/push/merge。

两个硬阻断均已在实现 worktree 中关闭：原样执行 `git diff --check` 返回 `0`；
标准验收路径中的新 `.etu` 解包 candidate 与新的 v20801 最终 App 逐字节一致。
这只是实现侧补救，不是独立验收签字。P2-5 继续保持“阻塞”，P2 保持 `4/6`。

## 1. 硬阻断一：`git diff --check`

独立验收报告的失败项：

- `MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h` 三处行尾空格；
- `PLAN-OTA-EXEC.md` 九个新增行的 CR 被 Git 默认 whitespace 规则判为尾随空白。

处理：

- RTE 文件只删除三处行尾空格，未改变其他内容；处理后该文件相对 HEAD 无 diff。
- `PLAN-OTA-EXEC.md` 的 HEAD 历史内容使用 CRLF。为避免整文件换行噪声，只将
  `git diff --check` 报告的九个新增/修改行终止符改为 LF，未重写历史未改行。
- `PLAN-OTA-EXEC.md` 仍为 UTF-8 无 BOM。

复核命令及结果：

```powershell
git diff --check
# exit 0, no output

git status --short -- MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h
# no output
```

## 2. 硬阻断二：生成与最终 F4 App 对应的新 `.etu`

### 2.1 身份关系

最终 GCC raw App 没有改变：

| 角色 | 大小 | SHA-256 |
|---|---:|---|
| GCC raw App | `598760 B` | `57D33C3A1608132DC020334F9469E75318940C3A4EF4C966CA119283586847C1` |
| 已回刷基线 App，v20800 | `598760 B` | `0FAB063BAB058370F36C5FAD0E1AF84AA08FF47B4B78602A992ABAECB6482EED` |
| 新目标 App，v20801 | `598760 B` | `CEE82EE7BC15A07C021839FB7D7C2D9E43388555A5BF235288FBDCE4EBF3553E` |

v20800 和 v20801 使用同一个最终 raw App；差异仅来自 `0x400..0x45F` 的 96 字节
`fw_header`。逐字节检查确认新目标 App 在该 header 区间之外与 raw App 完全一致。
因此不能要求 v20801 candidate 等于基线 v20800 的 `0FAB...EED`；闭环应比较
`.etu` 解包结果与新的 v20801 最终 App `CEE82...553E`。

新目标 finalize 参数：

```text
version_name=2.8.1
vcode=20801
build_ts=1786031427
header_crc32=ca3a47cc
```

### 2.2 制包与解包命令

```powershell
python Tools\etu_pack.py finalize `
  --app MDK-ARM_F435\cmake-generated\build-gcc-release\app-gcc\X-Track-App-GCC.bin `
  --out .cache\p2-5-f4-post-acceptance\20260806-r1\X-Track-App-GCC-v2.8.1.finalized.bin `
  --ver-name 2.8.1 --build-ts 1786031427

python Tools\jlink\prepare-bootstrap-app.py verify `
  --input .cache\p2-5-f4-post-acceptance\20260806-r1\X-Track-App-GCC-v2.8.1.finalized.bin `
  --input-kind app

python Tools\etu_pack.py pack-full `
  --app .cache\p2-5-f4-post-acceptance\20260806-r1\X-Track-App-GCC-v2.8.1.finalized.bin `
  --out .cache\p2-5-f4-post-acceptance\20260806-r1\P2-5-FULL.etu `
  --ver-name 2.8.1

python Tools\etu_unpack.py `
  --out .cache\p2-5-f4-post-acceptance\20260806-r1\candidate.roundtrip.bin `
  --verify-fw-header `
  .cache\p2-5-f4-post-acceptance\20260806-r1\P2-5-FULL.etu
```

本机未设置 `OTA_AES_KEY`，工具按仓库既有开发流程使用 vendor development default
key；`key_id=1`。GCC 构建规则中未定义 `OTA_AES_KEY_1_WORD*` 覆盖，设备侧
`Libraries/OTA/ota_keys.c` 同样落到 key 1 的 development fallback。日志不记录 key 内容。

### 2.3 结果

```text
P1_5_APP_VERIFY=PASS kind=app len=598760 vcode=20801
pack-full: app_len=598760 etu_total=281108 target_vcode=20801 flags=0x000b
unpack(full): candidate_len=598760 target_vcode=20801
roundtrip_byte_equal=true
raw_equal_outside_fw_header=true
```

| 产物 | 大小 | 时间 | SHA-256 |
|---|---:|---|---|
| `X-Track-App-GCC-v2.8.1.finalized.bin` | `598760 B` | `2026-08-06T23:50:28.1003263+08:00` | `CEE82EE7BC15A07C021839FB7D7C2D9E43388555A5BF235288FBDCE4EBF3553E` |
| `P2-5-FULL.etu` | `281108 B` | `2026-08-06T23:50:29.2349417+08:00` | `866212C429C04D7177E48C5DF17A6FDBA3CFDA07A449133F877238CBA4CB4A41` |
| `candidate.roundtrip.bin` | `598760 B` | `2026-08-06T23:50:29.8458724+08:00` | `CEE82EE7BC15A07C021839FB7D7C2D9E43388555A5BF235288FBDCE4EBF3553E` |

标准验收路径已经更新为一致资产：

```text
.cache/p2-5-hw/app-v2.8.0-base.bin  = 0FAB063B...6482EED
.cache/p2-5-hw/app-v2.8.1-final.bin = CEE82EE7...F3553E
.cache/p2-5-hw/P2-5-FULL.etu        = 866212C4...B4A41
.cache/p2-5-hw/roundtrip.bin         = CEE82EE7...F3553E
```

`.claude/prompt-P2-5-verification.md` 中旧包的大小、candidate SHA 和包 SHA 已同步为
上述新资产；只更新实测元数据，未修改验收判据、步骤或 fail-fast 规则。

旧四个资产保存在：
`.cache/p2-5-hw/archive-pre-f4-final-app-20260806/`。

完整原始证据：`.cache/p2-5-f4-post-acceptance/20260806-r1/`。

| 证据 | SHA-256 |
|---|---|
| `finalize.log` | `0319DA86C05E41245E90189E1FB3CE3838F3A3C3D7F6595ED7911D2D4EF4FED6` |
| `verify-app.log` | `1ACFE0A301930A627E5A38ED13E12EEB160366DE3AC6D97931FE3C86DFB5DAE4` |
| `pack-full.log` | `470367C6C932B1768E755D66B604D3F3E8CCB686BA713F68850C4EE48D890F26` |
| `unpack.log` | `67B25FF4A28DF4B89D5E6620E266B9F2D1453D5DE735C5493A350FE1F9FC75D1` |
| `package-summary.json` | `72469172FFAD79E4E24C30B9E896E34CC79BCFB0F338ADD66D50650D57C79856` |

## 3. 尚未完成

- 新 `.etu` 只在 worktree 内生成，未擅自写入项目外的物理 SD 卡；重验前必须确认
  SD 根目录使用 SHA-256 为 `866212C4...B4A41` 的新包。
- 本实现会话不把制包自验当作 P2-5 真机闭环，也不改写独立验收“不通过”结论。
- 下一轮仍须由非实现会话重新执行宿主回归、fresh 构建、模拟器 fixture、烧录及
  `STAGED -> APPLYING -> TEST_BOOT -> CONFIRMED` 真机闭环。

本轮未 commit、push、merge、rebase 或 stash。
