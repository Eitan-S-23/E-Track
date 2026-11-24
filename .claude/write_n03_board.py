"""Byte-exact board update for the N03 candidate-preparation batch."""
import pathlib
import sys

BOARD = pathlib.Path(r"D:\github\my\E-Track\P3-4项目进度表.md")
text = BOARD.read_bytes().decode("utf-8")
require_newline = text.endswith("\n")


def replace(old, new):
    assert text.count(old) == 1, "anchor count %d: %r" % (text.count(old), old[:60])
    globals()["text"] = text.replace(old, new)


def insert_before(anchor, block):
    assert text.count(anchor) == 1, "anchor count %d: %r" % (text.count(anchor), anchor[:60])
    globals()["text"] = text.replace(anchor, block + anchor)


replace(
    "更新时间：2026-09-26（北京时间）。维护与当前接续执行：Codex root。",
    "更新时间：2026-09-26（北京时间）。维护与当前接续执行：Codex root。\n"
    "本轮接续实现（N03 候选准备）由续接实现会话执行；独立验收仍另行指派。",
)

replace(
    "当前服务与设备观察所有者均已关闭；不再让用户重复操作旧页面，S03/S04 保留未测。**",
    "当前服务与设备观察所有者均已关闭；不再让用户重复操作旧页面，S03/S04 保留未测。**\n"
    "**N03 本轮已从主机模型推进到可在真机接收端运行：候选 R 与成对探针包 T 均已构建并通过"
    "主机验证，但尚未安装、尚未测量真机收益（见下节）。**",
)

replace(
    "| N03 | 接收端整块校验，P34-QSPI-01 | 实现及主机自测完成；真机收益未验证 | "
    "让候选实际运行在接收端；固定链路条件比较小块回读次数、落盘等待及真实传输时间；"
    "保留逐字节校验和断电恢复语义 |",
    "| N03 | 接收端整块校验，P34-QSPI-01 | 候选 R 与成对探针包 T 已构建并主机验证；"
    "真机收益未验证 | 按下节四步在保留 30214 与候选 R 上发送同一个 T 的 32 KiB 零起点前缀，"
    "比较回读/校验次数、落盘等待与真实传输时间；保留逐字节校验和断电恢复语义 |",
)

insert_before("## N01 本批交付", """## N03 实测准备（本轮交付）

本轮把 P34-QSPI-01 从"主机模型"推进到"可在真机接收端运行"，仍未测量真机收益。

- 候选 R 源码树 `.cache/p34-next/n03/fw`：以保留 30214 谱系
  `.cache/p34q/timer-window-r2/fw` 为基版，仅叠加 6 个文件（3 个产品文件、2 个仪表文件
  及 1 个主机测试）；另有 6 个文件在 N03 影子树中较旧，已显式声明保留基版，并逐个核对
  等于当前主工作树副本，因此没有无关产品改动混入。差异表与来源记录见 [E41]。
- R 构建 [E42]：configure/build 退出码 0，0 error、638 warning；App `.bin` 613580 字节
  （保留版 613344，+236），ELF/MAP/SHA 均已留痕。App 槽 `OTA_APP_LENGTH=0xF0000`
  （983040 字节），候选可容纳，余量已记录。
- 整块校验确实进入镜像：`staging_verify` 在 0x0804419c（76 字节）、`p34_staging_verify`
  在 0x080412a0（84 字节）；`g_p34_ble_profile` 位于 0x20052568，大小 **336** 字节
  （288 + 2 x 24，新增 `P34_PAYLOAD_VERIFY`/`P34_JOURNAL_VERIFY`）。旧绑定的 288 字节
  断言对候选已失效，全部仪表符号、MAP/ELF、RTT 与 profile 地址必须按 R 重绑后才能测量。
- 成对资产 [E43]：安装包 `prefix-n03recv-full.etu`（30214 -> 30215，290996 字节，
  SHA-256 `a0c17864cb679da8b456b73db12e2e4687df29ecced508660accb19d81b7883e`，载荷为 R）；
  探针包 `prefix-n03probe-full.etu`（30214 -> 30216，290856 字节，SHA-256
  `82ffc33f9c53d0a9b631a56a1e9df772deb2e2e8a7e86a4de348882d7ee62d90`，载荷为已核验的
  30214 可执行体，仅改标准版本头）。两包均通过 Python 解包逐字节一致、现有原生固件/Boot
  解码（byte_identical/boot_ok/guards_ok/workspace_lifecycle_ok），并各自通过 4 项非法包
  在"进入 preparation 之前"被拒绝。未发送、未安装、未接触设备或网络。

有限实测步骤（每步只测一次；出现新失败即停止并保留原件）：

1. 保留 30214 上发送 T 的 32 KiB 零起点前缀并严格 ABORT，作为 A 臂。
2. 用 `prefix-n03recv-full.etu` 正常升级到 R，重启后核验真实 App/Boot 身份。该步由旧固件
   接收，不能计入 N03 收益。
3. 在 R 上发送字节完全相同的 T 前缀，波特率/窗口/发送端/MTU/写模式与 A 臂一致，作为
   B 臂；先按 R 重绑全部仪表与地址绑定。
4. 比较 A/B 的实际耗时、小块回读与整块校验次数、ACK 等待及落盘确认，再决定是否进入整包
   与 N04 计时。

预登记判据（主机模型推导，尚未实测，不得当作结果）：每个 4 KiB 落盘块的 XIP 恢复由
37 次降至 6 次。据此 S02 前缀的 payload_read 应由 256 次 / 2.4206 秒降至约 8 次 /
0.08 秒量级，整轮 9.2865 秒约减至 6.9 秒（约 25%）；整包 2273 次 / 21.5846 秒应降至
71 次 / 0.67 秒量级，103.80 秒约减至 83 秒（约 20%）。任一侧明显未达该量级，即视为
候选无效或环境不同，必须复核而不得解释掉。

停止条件：A 臂或 B 臂出现非零重传、身份不符、暂存/保留镜像不一致，或需要放宽版本/
恢复语义时停止；不重放已成功的传输，不用 App 单侧降级制造对照。

""")

replace(
    "当前保留固件仍没有 N03 的整块校验实现。安装包含优化的目标固件本身不证明提速，"
    "须在该固件作为接收端时测量。",
    "当前**保留**固件（30214）仍没有 N03 的整块校验实现；候选 R（30215）已构建但尚未安装。"
    "安装包含优化的目标固件本身不证明提速，须在该固件作为接收端时测量。",
)

replace(
    "[E40]: .cache/p34-session/runs/20260926T073722-11800/cells/s03/result.json\n",
    "[E40]: .cache/p34-session/runs/20260926T073722-11800/cells/s03/result.json\n"
    "[E41]: .cache/p34-next/n03/source-preparation.json\n"
    "[E42]: .cache/p34-next/n03/build-result.json\n"
    "[E43]: .cache/p34-next/n03/assets/result.json\n"
    "[E44]: .cache/p34-next/n03/delta.json\n"
    "[E45]: .cache/p34-next/n03_candidate.py\n"
    "[E46]: .cache/p34-next/n03_assets.py\n",
)

replace(
    "| 2026-09-26 | S02 正常完成，采集器无误判；同包同固件下窗口 8 为 9.29 秒/3.45 KiB/s、"
    "零重传 | 3.18 秒复用原回读完成复核，没有额外设备操作；同一服务中用固定入口准备 S03，"
    "不重跑测试/CI/打包 |\n",
    "| 2026-09-26 | S02 正常完成，采集器无误判；同包同固件下窗口 8 为 9.29 秒/3.45 KiB/s、"
    "零重传 | 3.18 秒复用原回读完成复核，没有额外设备操作；同一服务中用固定入口准备 S03，"
    "不重跑测试/CI/打包 |\n"
    "| 2026-09-26 | N03 候选 R 由保留 30214 谱系加 6 文件叠加构建完成（0 error、638 warning、"
    "613580 字节），成对资产 `prefix-n03recv-full.etu` 与 `prefix-n03probe-full.etu` 已冻结并"
    "通过原生解码与非法包拒绝 | 仅主机工作，无设备、网络、安装或提交；下一步按本节四步实测，"
    "需要设备窗口时再向用户提出，先完成 R 的仪表与地址重绑 |\n",
)

assert text.endswith("\n") == require_newline, "trailing newline changed"
BOARD.write_bytes(text.encode("utf-8"))
print("BOARD_UPDATED", len(text.encode("utf-8")))
