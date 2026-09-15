# P3-3-v7 外部输入证据：EXT-BOARD-STATE（目标板实机状态，30203 CONFIRMED 终态）

- 输入 ID: EXT-BOARD-STATE（category=hardware_state）
- 编制: 实现会话（P3-3-IMPL-20260907，DRAFT）；冻结核对: 待非实现会话
- 日期: 2026-09-15
- freeze_commit: `0fb167cf4c44a6e4741e5a42fcd4945cf29f7780`（v6/v7 共用——v7 为纯合同勘误轮，零设备操作）
- v7 轮验收=纯只读，设备保持当前终态不动（不连 J-Link、不烧录、不读写
  BCB/App 区）

## 1. 当前设备终态（r6 闭环后，本合同绑定的执行时点状态）

- 运行 App：3.2.3（versionCode 30203），镜像 SHA-256
  `3a2827683cbd2b557dd5d441927d1a490b3b28fe11f8d7a4b4b5c86a594144a3`
  （=v6 真包目标镜像，r6 闭环终点）
- BCB：CONFIRMED、cur_vcode=30203（与运行 App 一致态）
- 生产 Boot：全区原样（r2 恢复轮 S6 restored_sha256=`b6b33a82…` 与
  S1A 备份及 r1 轮同 SHA 闭合，其后各轮从未写 Boot 区）
- 证据来源：r6 服务日志设备自报
  （`.cache/p3-3-v2-service/service-v6-20260914.log` 00:06:05/00:06:08/
  00:07:22 三次 latest 自报 30203+3a282768 与服务端注册全等）+ 用户
  2026-09-15 实测确认（「实测OTA没有问题」，180s 复核窗口内确认目标）

## 2. 历史状态链（如实登记，全部留档）

| 时点 | 事件 | 结果态 |
| --- | --- | --- |
| 初始阻断 | BCB vcode 20801 与运行 3.2.0(30200) 不一致 | 恢复轮 20260913-r1 消除（REC0-REC7/S1A-S6 全 PASS） |
| 2026-09-14 O2 | 旧缺陷 fixture 传输完成未提交 BCB（PRODUCT_FAIL，板卡未被改动） | 1894f9d 修复 |
| 2026-09-14 烧录事故 | 误烧未 finalize 裸镜像触发 boot 设计内 ROLLBACK 黑屏 | 恢复轮 20260914-r2 全 PASS（S1A-S6） |
| r2 终态 | 生产 Boot 全区原样 + 3.2.0-fixed(30200) + BCB CONFIRMED/30200 | O 序列合法起点 |
| O2/O3（第十轮） | toy 闭环 | 30201 CONFIRMED（RTT "BCB already CONFIRMED vcode=30201"） |
| O4（第十轮） | 真包 3.2.2 闭环 | 30202 CONFIRMED |
| r6（v6 轮） | 真包 3.2.3 闭环 | 30203 CONFIRMED（当前态） |

各轮恢复/闭环证据：`.cache/p3-3-recovery-execute/20260913-r1/`、
`20260914-r2/`、`.cache/p3-3-o-verify/`、
`docs/ota-exec-notes/P3-3-o-sequence-execution-2026-09-14.md`、
`docs/ota-exec-notes/P3-3-r6-verification-execution-2026-09-14.md`。

## 3. v7 轮口径

- C-TOY-LOOP/C-REAL-LOOP 判定素材=既有落档证据的离线审查（toy 30201
  重跑需设备版本回退=烧录动作，未获授权不执行；real 30203 闭环已由 r6
  完成）。
- 本输入的解决证据=上表历史链 + 第 1 节当前终态自报记录；v7 验收会话
  不操作设备即可核对本输入（服务日志为设备身份的服务端镜像证据）。
