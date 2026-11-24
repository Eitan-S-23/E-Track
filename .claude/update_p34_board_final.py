# -*- coding: utf-8 -*-
# P3-4 看板最终回写：行 652/658 更新为最终绿提交 1256e2f / run 35034258547，
# §10 追加收口条目。字节级替换，保持 CRLF/LF 原样。

import io

PATH = 'PLAN-OTA-EXEC.md'

with io.open(PATH, 'rb') as f:
    data = f.read()

old652 = ('状态: 进行中 ｜ 认领: Claude(P3-4 实现 agent) / 2026-09-16 ｜ 更新: '
          '2026-09-16(测量接线完成并双宿主开发自测全绿：OtaLinkStats 接线+测试入 '
          'dev/flutter/p3-4-link-stats 03b509d，CI 35032091035 Ubuntu/Windows 各 '
          '+347 通过；设备实测 NOT_RUN 待授权)').encode('utf-8') + b'\r'
new652 = ('状态: 进行中 ｜ 认领: Claude(P3-4 实现 agent) / 2026-09-16 ｜ 更新: '
          '2026-09-16(测量接线与 service 层接线断言完成，五轮 CI 后双宿主开发自测'
          '全绿：dev/flutter/p3-4-link-stats 1256e2f，CI 35034258547 Ubuntu '
          '+348/Windows +355 通过；设备实测 NOT_RUN 待授权)').encode('utf-8') + b'\r'
assert data.count(old652) == 1, 'old 652 not unique'
data = data.replace(old652, new652)

old658 = ('- 证据: research 已落盘 docs/ota-exec-notes/'
          'P3-4-research-link-timing-2026-09-16.md(调用链/分阶段测量方案/ACK 样本'
          '冻结语义映射/接线设计/共享依赖/fixture 盘点/操作单草案)；测量接线已完成'
          '并自测：dev/flutter/p3-4-link-stats(03b509d) flutter-dev-checks run '
          '35032091035 双宿主(Ubuntu/Windows) analyze 零问题、各 +347 测试通过，'
          '三轮红->绿修复链完整留痕；APK/EXE 构建 NOT_REQUESTED，产品实测与正式'
          '验收 NOT_RUN。').encode('utf-8') + b'\r'
new658 = ('- 证据: research 已落盘 docs/ota-exec-notes/'
          'P3-4-research-link-timing-2026-09-16.md(调用链/分阶段测量方案/ACK 样本'
          '冻结语义映射/接线设计/共享依赖/fixture 盘点/操作单草案)；测量接线与 '
          'service 层断言已完成并自测：dev/flutter/p3-4-link-stats(1256e2f) '
          'flutter-dev-checks run 35034258547 双宿主(Ubuntu/Windows) analyze '
          '零问题、Ubuntu +348 / Windows +355 测试通过(含 upgrade/probe 摘要与 '
          'GATT 写计时接线断言)，五轮提交链 b23ce5d/1ba6460/03b509d/edf8f92/'
          '1256e2f 完整留痕；APK/EXE 构建 NOT_REQUESTED，产品实测与正式验收 '
          'NOT_RUN。').encode('utf-8') + b'\r'
assert data.count(old658) == 1, 'old 658 not unique'
data = data.replace(old658, new658)

entry = ('- 2026-09-16 ｜ Claude(P3-4 实现 agent) ｜ P3-4(开发自测收口：五轮 CI '
         '双宿主全绿) ｜ 补 service 层接线断言(edf8f92)暴露 upgrade fake 覆写带计时'
         '外壳时旁路 recordMtu/recordSubscribe/recordGattWrite，私有实现无法从测试'
         '覆写，改在 fake 内对齐外壳上报语义修复(1256e2f)；run 35034258547 双宿主 '
         'analyze 零问题、Ubuntu +348(7 skip)/Windows +355 全过，OTA_LINK_ 观测行 '
         '828/849 条；设备实验操作单待授权，产品实测与正式验收 NOT_RUN。'
         ).encode('utf-8')
assert data.endswith(b'\n'), 'file must end with newline'
data = data + entry + b'\n'

with io.open(PATH, 'wb') as f:
    f.write(data)

print('board updated: 652/658 replaced, one session log appended')
