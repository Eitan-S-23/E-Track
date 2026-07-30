# P1-6 / P2-1 / P2-2 分支集成记录

- 日期: 2026-07-30
- 集成会话: Codex
- 集成分支: `integration/p1-p2`
- 共同基线: `bd9f4da0bee476d4ee2f4ba3f3e25b1e17b0d9ec`
- Checkout A / P1-6: `9a2f27f70bc4ebff26e5a335bce73ac681ab4890`
- Checkout B / P2: `2374519781460ce150b8ba44b4c246280939493a`

## 1. 集成边界

本次只整合两条已独立推进的提交历史并解决组合构建冲突，不重新实现 P1-6、
P2-1 或 P2-2，也不改变既有验收结论。最终 merge commit 保留 A、B 两侧完整
历史，不 amend、不 squash。

统一后的权威任务状态为：

```text
P1 = 5/6
P1-6 = 进行中
P2 = 2/6
P2-1 = 完成
P2-2 = 完成
```

P1-6 的 14 个 AUTO 点仍保持通过；PHYSICAL `03、05、07、15、16、17` 仍待
用户具备物理断电条件后执行。本次集成不实施、也不宣称通过这些物理点。

## 2. 冲突解决

三方合并只有以下三个文件产生内容冲突：

```text
MDK-ARM_F435/cmake-generated/CMakeLists.txt
cmake/linker/x-track-app-gcc.ld.S
cmake/linker/x-track-boot-gcc.ld.S
```

解决规则：

1. CMake 同时保留 `P1_6_TEST_ENABLE`、`P2_1_TEST_ENABLE`、
   `P2_2_TEST_ENABLE`，并新增两两互斥的 configure-time 硬失败。
2. 三种开关统一通过 `OTA_TEST_LINKER_DEFINES` 预处理 App/Boot linker；生产
   默认三项均为 `OFF`。
3. App linker 分别保留 P1-6 `0x200`、P2-1 `0x80`、P2-2 `0x800` RAM 尾部
   evidence control 区，并完整保留 P2 的 `.ota_overlay` 地址与大小断言。
4. Boot linker 保留 P1-6 `0x200` 和 P2-1 `0x80` control 区；P2-2 仅使用
   App harness，不给 Boot 增加控制区。

四种 linker 预处理结果：

| 模式 | App control | Boot control | App `.ota_overlay` |
|---|---|---|---|
| default | 无 | 无 | 有 |
| P1-6 | `P1_6_CTRL` | `P1_6_CTRL` | 有 |
| P2-1 | `P2_1_CTRL` | `P2_1_CTRL` | 有 |
| P2-2 | `P2_2_CTRL` | 无 | 有 |

## 3. 组合验证

宿主回归实际重跑：

| 测试 | 结果 |
|---|---|
| fw_header vectors | `16/16 PASS` |
| Boot Ymodem / ETSL | `19/19 PASS` |
| BCB | `27/27 PASS` |
| Boot state machine | `96/96 PASS` |
| P1-6 control protocol | `21/21 PASS` |
| OTA golden vectors | `9/9 PASS` |
| P2-1 staging | `48/48 PASS` |
| P2-2 package | `102/102 PASS` |

CMake 使用 GCC 13.3.1 分别配置 default、P1-6、P2-1、P2-2，四种模式均
成功；P1-6/P2-1、P1-6/P2-2、P2-1/P2-2 三种非法双开组合均按预期在
configure 阶段失败。

Ninja 在本机首个 job 前挂起，按仓库既有经验切换到 `Unix Makefiles` 完成
fresh Release 组合构建：

```text
X-Track-App-GCC.bin = 563252 bytes
sha256 = 719f959c6920ff3d3041e70af19f114349b0a67735a074dd9ecd9e41f5996368

X-Track-Boot.bin = 14236 bytes
sha256 = 5656466564891b54666325da4545f3f819ba38f50660ab4772809b5647135ab5
```

`validate_boot_artifact.py` 通过：

```text
P1_1_BOOT_ASSERTIONS=PASS bin=14236 vector=0x08000000/0x20c
```

Boot 小于 64 KiB，三个 LOAD 均无 RWX。App 保留仓库既有首个 LOAD `RWE`、
newlib/short-wchar 等 linker warning；错误为零，本次合并未掩盖这些 warning。

## 4. 硬件与发布

本次没有运行 J-Link、RTT 或任何板卡命令，没有执行 P1-6 物理断电点，也没有
push。后续从本集成提交继续 P2-3 时，P1-6 必须保持 `进行中`。
