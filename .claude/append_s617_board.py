# -*- coding: utf-8 -*-
"""看板 PLAN-OTA-EXEC.md 第七批回写（字节手术，LF 新增行）。

三处插入：
1. P3-3 卡动态记录：第六批记录行之后；
2. §9 变更登记表：裁定会话（OTA-DEC-013）行之后；
3. §10 会话日志：文件末尾（裁定会话日志行之后）。

不改任何既有字节，仅在锚点后插入新行；锚点用唯一子串定位并断言唯一命中。
"""

BOARD = 'PLAN-OTA-EXEC.md'

CARD_ANCHOR = '- RC3 第六批整改交付与开发自测闭环(实现会话): Claude(P3-3-IMPL-20260907)/2026-09-10；在独占验证分支 dev/flutter/apk/p3-3-batch6 按 §6.14 遗留清单完成 22 提交整改与 22 轮 CI 反馈迭代'

S9_ANCHOR = '| 2026-09-10 | P3-3/P3-5 / Codex 用户授权治理裁定'

CARD_LINE = (
    '- RC3 第七批整合整改交付与开发自测闭环(实现会话): Claude(P3-3-IMPL-20260907)/2026-09-10；'
    '按第六批复审草案(.cache/p3-3-review-20260910/review-draft.md，复核基线 HEAD 7e3ab72，非冻结合同)'
    '六项范围在 dev/flutter/apk/p3-3-batch6 交付两提交(f9dba08+3e10311，12 文件 +2766/−260，'
    '新增用例 56=产品 45+runner 回归 11)：'
    '①dev_checks 输入门禁语义化(porcelain rename/copy 解析+hash-object 内容指纹+未跟踪/重命名/删除=语义'
    '+工具链再生绑定实际生效字节+APK 起点门禁)；'
    '②命令等待者在 await 物理写前挂错误监听(取消/释放/通知报错不逃逸)；'
    '③半帧/迟到物理写边界(排队写启动复核通道+任意失败投毒+通道对象域+会话隔离+发窗间预算)；'
    '④owner 与资源生命周期(取消代次 epoch 屏障+迟到复核发布不覆盖取消终态+后台恢复三级 fail-closed'
    '+A 读取失败 B 作废+删包/终态发布次序+迟到旧订阅不关新 owner CCCD)；'
    '⑤fake 真值校准(BEGIN 门禁 6+MCU oracle 8，产品逻辑沿五六批)；'
    '⑥HTTP 分类关闭清理(首违规 206 中止旧响应+零事件停滞兜底+无在途/在途退出/超时不删三分清理'
    '+isRetryableLater 状态契约)。'
    '首跑 run 34449930671 被本批新增在途恢复正例抓获真实产品缺陷：service 后台复核的在途 GET_INFO '
    '从会话 seq 计数器取号，恢复后 DATA 整体跳号被 MCU ERR_SEQ 拒收→内部 ABORT+BEGIN 重对齐'
    '+durable 整段重发(真机=每次后台往返烧一个发送窗口+一次恢复预算，两次即升级失败)；'
    '已修为独立 _querySeq 空间(合同 §5.1 seq=会话内帧序号，GET_INFO session=0 不参与会话状态)，'
    '正例强化 beginCalls=1/8 段不重复+新增 transport 级 4096B/32 段在途复核回归。'
    '终态 run 34452184680(3e10311) completed success：ubuntu 13 命令全 PASS(含 apk_build 524s'
    '+apksigner verify)+windows 5 命令 PASS(+277)，debug APK 复产(131,454,050 B，'
    'sha256 e38c6887ddacb0f92ae9b21225033f766c6d461ca363e043d97f77b48029030a，release_signing=false，'
    'formal_acceptance=NOT_RUN)；失败轮证据留痕 .cache-ci/batch7-artifacts/。'
    '真机/EXE/release/正式验收 NOT_RUN，开发自测≠正式验收，P3-3 保持进行中；'
    '按 §7.3.2 预授权提交推送(7e3ab72..3e10311)，未合并/发布/部署/真机。'
    '逐项处置、缺陷叙事与 run 链见 research §6.17。'
)

S9_LINE = (
    '| 2026-09-10 | P3-3 / Claude 实现 agent（第七批整合整改） | '
    '第六批复审草案指出的 runner 门禁非 fail-closed(未跟踪/实质修改/真 EOL 不分)、命令等待者错误窗口、'
    '半帧/迟到写投毒绕过、owner 与资源生命周期、HTTP 关闭清理；首跑 CI 暴露在途 GET_INFO 消耗会话 seq '
    '的产品缺陷(合同 §5.1 seq=会话内帧序号) | '
    'dev_checks 语义身份+工具链再生绑定(11 runner 回归)；传输等待者错误监听/排队写启动复核/任意失败投毒'
    '/通道对象域/发窗间预算；service 取消代次 epoch 屏障+后台恢复三级 fail-closed 复核+A→B 作废；'
    'GET_INFO 独立 _querySeq(3e10311) | '
    '属 §7.3.2 预授权范围内的开发自测整改，不改冻结合同/矩阵/判据；终态 run 34452184680 双宿主全绿'
    '+debug APK 复产，失败轮 34449930671 证据留痕 .cache-ci/；开发自测≠正式验收 | 已执行/开发自测全绿 |'
)

S10_LINE = (
    '- 2026-09-10 ｜ Claude(P3-3 实现 agent，第七批整合整改与开发自测闭环) ｜ '
    'P3-3(保持进行中，开发自测全绿，正式验收 NOT_RUN) ｜ '
    '按第六批复审草案六项范围完成整合整改(f9dba08，12 文件 +2710/−259)，首跑 run 34449930671 被新增'
    '在途恢复正例抓获并修复真实产品缺陷——在途 GET_INFO 消耗会话 seq 致恢复后 DATA 跳号/内部重对齐'
    '/整段重发(3e10311 独立 _querySeq)；终态 run 34452184680 双宿主全绿(ubuntu 13 命令+windows 5 命令)'
    '+debug APK 复产(sha256 e38c6887…，release_signing=false)，失败轮证据留痕 .cache-ci/batch7-artifacts/。'
    '真机/EXE/release/正式验收 NOT_RUN，未填 EXECUTED PASS；按 §7.3.2 预授权提交推送(7e3ab72..3e10311)，'
    '未合并/发布/部署/真机。逐项处置见 research §6.17；看板/研究回写留在工作树未提交'
    '(避免卷入裁定会话未提交治理文档)，治理文档提交待主会话串行协调。'
)


def insert_after_line(data: bytes, anchor: str, new_line: str, label: str) -> bytes:
    """在包含 anchor 的行（整行）之后插入 new_line（LF 结尾）。"""
    a = anchor.encode('utf-8')
    hits = data.count(a)
    assert hits == 1, f'{label}: anchor 命中 {hits} 次（要求唯一）'
    pos = data.index(a)
    nl = data.index(b'\n', pos)
    line_end = nl + 1
    # 锚点行本身必须以 LF 结尾（不含 CR），新增行保持同风格
    assert not data[pos:nl].endswith(b'\r'), f'{label}: 锚点行为 CRLF，需人工确认插入风格'
    ins = new_line.encode('utf-8') + b'\n'
    return data[:line_end] + ins + data[line_end:]


def main() -> None:
    with open(BOARD, 'rb') as f:
        data = f.read()
    orig_len = len(data)
    crlf_before = data.count(b'\r\n')

    data = insert_after_line(data, CARD_ANCHOR, CARD_LINE, 'card')
    data = insert_after_line(data, S9_ANCHOR, S9_LINE, 's9')
    assert data.endswith(b'\n'), 'board must end with newline'
    data = data + S10_LINE.encode('utf-8') + b'\n'

    with open(BOARD, 'wb') as f:
        f.write(data)

    crlf_after = data.count(b'\r\n')
    print(f'board {orig_len} -> {len(data)} bytes (+{len(data) - orig_len})')
    print(f'CRLF {crlf_before} -> {crlf_after} (must be equal: {crlf_before == crlf_after})')
    print('added lines: 3 (card/§9/§10), all LF')


if __name__ == '__main__':
    main()
