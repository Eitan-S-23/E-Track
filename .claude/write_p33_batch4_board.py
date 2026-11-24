# -*- coding: utf-8 -*-
# PLAN-OTA-EXEC.md 回写：P3-3 状态行更新字段、第四批交付记录、§10 日志。
# 全字节级编辑：目标行与追加内容均为 LF 行尾（与既有行一致），不触碰 CRLF 行。
PATH = r'D:\github\my\E-Track\PLAN-OTA-EXEC.md'

with open(PATH, 'rb') as f:
    data = f.read()

# ---- 1. 状态行「更新:」字段替换（L622，LF 行） ----
old_status = ('状态: 进行中 ｜ 认领: Claude(P3-3 实现 agent, P3-3-IMPL-20260907) / 2026-09-07 ｜ '
              '更新: 2026-09-08(RC3 第三批独立集中复核：保留已修子项，RC3-01 至 RC3-12 仍部分修复，'
              '编译/API、测试可信度及取消/预算/恢复链路未闭合，详见 research §6.10；'
              'analyze/test 与 APK/EXE 未执行，正式验收 NOT_RUN，先批量整改与可信自测) '
              '｜ **APK/EXE 构建走 GitHub Actions(app 子项目禁本地构建)**').encode('utf-8')
new_status = ('状态: 进行中 ｜ 认领: Claude(P3-3 实现 agent, P3-3-IMPL-20260907) / 2026-09-07 ｜ '
              '更新: 2026-09-08(RC3 第四批整改交付：按 §6.10.2 完成 RC3-01 至 RC3-12 源码修复与'
              '测试补充并静态核对，详见 research §6.11；analyze/test/APK/EXE/真机 NOT_RUN，'
              '待授权提交后 Actions 验证，正式验收待非实现独立会话) '
              '｜ **APK/EXE 构建走 GitHub Actions(app 子项目禁本地构建)**').encode('utf-8')
assert data.count(old_status) == 1, '状态行定位失败'
data = data.replace(old_status, new_status)

# ---- 2. RC3 第三批复核行后插入第四批交付记录（LF） ----
anchor = ('- RC3 第三批整改集中复核(非正式轮次): Codex(非实现会话)/2026-09-08；按 §6.9 新交付沿原 '
          'RC3-01 至 RC3-12 集中复核').encode('utf-8')
assert data.count(anchor) == 1, '复核行锚点定位失败'
# 找到该行行尾（\n）后插入
idx = data.index(anchor)
line_end = data.index(b'\n', idx)
insertion = ('\n- RC3 第四批整改交付(实现会话): Claude(P3-3-IMPL-20260907)/2026-09-08；'
             '按 §6.10.2 逐项处置表完成 RC3-01 至 RC3-12 的源码修复与测试补充'
             '(96 次 Edit：lib 5 文件 45 次、test/ota 7 文件 51 次)，'
             '逐项记录见 docs/ota-exec-notes/P3-3-research-flutter-ota.md §6.11。'
             '编译矛盾、gate 死锁、fake 流式 SHA oracle、取消/预算/后台/重连链路、'
             'Windows 能力读取、HTTP 闭锁与清包恢复入口均已完成代码修改且静态核对未再发现所列矛盾；'
             '但 Flutter analyze/test、Actions APK/EXE、真机全部 NOT_RUN'
             '(无本机 SDK、未获推送授权)，已修不等于运行验证通过。'
             '未 commit/push/dispatch/真机；保持进行中，不填 PASS 矩阵，'
             '正式验收待非实现独立会话。').encode('utf-8')
data = data[:line_end] + insertion + data[line_end:]

# ---- 3. 文件末尾追加 §10 日志行（LF，文件以 \n 结尾） ----
assert data.endswith(b'\n'), '文件应以换行结尾'
log_line = ('- 2026-09-08 ｜ Claude(P3-3 实现 agent, P3-3-IMPL-20260907) ｜ '
            'P3-3(保持进行中，RC3 第四批整改交付) ｜ 按 §6.10.2 完成 RC3-01~12 源码修复与'
            '测试补充并静态核对(research §6.11，96 次 Edit)；analyze/test/APK/EXE/真机 NOT_RUN'
            '(无 SDK/未获授权)，未 commit/push/dispatch，不填 PASS 矩阵，正式验收待非实现会话。'
            '\n').encode('utf-8')
data = data + log_line

with open(PATH, 'wb') as f:
    f.write(data)
print('PLAN-OTA-EXEC.md rewritten OK')
