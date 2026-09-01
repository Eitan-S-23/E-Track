set pagination off
set confirm off
set print elements 0
file "D:/github/my/E-Track/.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.elf"
target remote 127.0.0.1:24361
monitor halt
monitor WriteU32 0xE0042008 0x00001000
# ================= S2-3: C7 链 (产品行为观测 1/1) =================
# 链路: Push FirmwareUpdate (LiveMap 释放) -> EnterPath("/") -> 选中 BAD ->
#   confirm(mode=1) -> StartImport(mode=2) -> [thbreak LzmaDec_Allocate] 采 owner==2 ->
#   [thbreak FinishImport] 采 owner==0 -> [thbreak HAL_Update] 采 mode=3 + RTT ring dump
# 全程 BCB 必须 CONFIRMED(4), vcode 保持 20801。
# ---- 确定性停点: HAL_Update ----
set $r9s3_magic = 0
thbreak *0x08040884
commands
  silent
  set $r9s3_magic = 0x503260C1
end
continue
if $r9s3_magic != 0x503260C1
  printf "P2_6_R9_S3 ERROR unexpected_stop magic=0x%08x pc=0x%08x\n", $r9s3_magic, (unsigned int)$pc
  quit 80
end
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR wrong_pc pc=0x%08x\n", (unsigned int)$pc
  quit 80
end
delete breakpoints
printf "P2_6_R9_S3 stop_verified pc=0x%08x\n", (unsigned int)$pc
# ---- 身份: v2.8.1 (必须, 本轮产品行为观测的前提) ----
source D:/github/my/E-Track/.cache/p2-6-sd-r9-20260901-01-implementation/tmp/v281-fw-header-gdb-block.txt
# ---- 前置: LiveMap 前台持 overlay (S2-2 留下的基线态), BCB=4 ----
set $sd3 = *(unsigned char*)0x20053214
set $vtor3 = *(unsigned int*)0xe000ed08
set $cfsr3 = *(unsigned int*)0xe000ed28
set $owner3 = *(unsigned char*)0x20053fa0
set $bcb3 = ((unsigned char (*)(void))0x08040ccd)()
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_bcb_pre pc=0x%08x\n", (unsigned int)$pc
  quit 81
end
printf "P2_6_R9_S3 pre vcode=%u bcb=%u owner=%u sd=%u\n", *(unsigned int*)0x08010408, $bcb3, $owner3, $sd3
if $bcb3 != 4
  printf "P2_6_R9_S3 ERROR pre bcb=%u expected=4\n", $bcb3
  quit 81
end
if $owner3 != 1
  printf "P2_6_R9_S3 ERROR pre owner=%u expected=1 (LiveMap 基线态缺失, 勿启动产品链)\n", $owner3
  quit 81
end
if $sd3 != 1 || $vtor3 != 0x08010000 || $cfsr3 != 0
  printf "P2_6_R9_S3 ERROR pre runtime sd=%u vtor=0x%08x cfsr=0x%08x\n", $sd3, $vtor3, $cfsr3
  quit 81
end
set $page_pre = *(void**)(0x200504f8 + 60)
if $page_pre == 0
  printf "P2_6_R9_S3 ERROR no_current_page\n"
  quit 81
end
if *(unsigned int*)$page_pre != 0x0805d818
  printf "P2_6_R9_S3 ERROR pre page vptr=0x%08x expected LiveMap 0x0805d818\n", *(unsigned int*)$page_pre
  quit 81
end
# ---- Push("Pages/FirmwareUpdate") (含 USB MSC gate 重试) ----
set $push3 = ((unsigned char (*)(void*, const char*, void*))0x0803db95)((void*)0x200504f8, "Pages/FirmwareUpdate", 0)
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_push pc=0x%08x\n", (unsigned int)$pc
  quit 82
end
printf "P2_6_R9_S3 push_try1=%u\n", $push3
if $push3 == 0
  call ((void (*)(void*))0x08018e77)((void*)0x2005368c)
  if (unsigned int)$pc != 0x08040884
    printf "P2_6_R9_S3 ERROR context_lost_usbdisc pc=0x%08x\n", (unsigned int)$pc
    quit 82
  end
  printf "P2_6_R9_S3 usbd_disconnect_done retrying_push\n"
  set $push3 = ((unsigned char (*)(void*, const char*, void*))0x0803db95)((void*)0x200504f8, "Pages/FirmwareUpdate", 0)
  if (unsigned int)$pc != 0x08040884
    printf "P2_6_R9_S3 ERROR context_lost_push2 pc=0x%08x\n", (unsigned int)$pc
    quit 82
  end
  printf "P2_6_R9_S3 push_try2=%u\n", $push3
end
if $push3 == 0
  printf "P2_6_R9_S3 ERROR push_failed\n"
  quit 82
end
# ---- 等切换动画完成: LiveMap onViewDidUnload 释放 overlay (owner 1->0) ----
set $r9s3_magic = 0
hbreak *0x08040884
commands
  silent
  set $r9s3_magic = 0x503260C2
end
set $turns3 = 0
set $owner_w3 = *(unsigned char*)0x20053fa0
while $owner_w3 != 0 && $turns3 < 5000
  continue
  set $turns3 = $turns3 + 1
  set $owner_w3 = *(unsigned char*)0x20053fa0
end
delete breakpoints
printf "P2_6_R9_S3 livemap_release_wait turns=%u owner=%u (应=0)\n", $turns3, $owner_w3
if $owner_w3 != 0
  printf "P2_6_R9_S3 ERROR livemap_not_released owner=%u\n", $owner_w3
  quit 83
end
# ---- FirmwareUpdate 页就绪检查 ----
set $page3 = *(void**)(0x200504f8 + 60)
if $page3 == 0
  printf "P2_6_R9_S3 ERROR no_current_page\n"
  quit 84
end
if *(unsigned int*)$page3 != 0x0809cb44
  printf "P2_6_R9_S3 ERROR wrong_page vptr=0x%08x expected=0x0809cb44\n", *(unsigned int*)$page3
  quit 84
end
set $page_state3 = *(unsigned char*)((char*)$page3 + 36)
if $page_state3 != 3 && $page_state3 != 4
  printf "P2_6_R9_S3 ERROR wrong_page_state state=%u\n", $page_state3
  quit 84
end
printf "P2_6_R9_S3 page_ready state=%u\n", $page_state3
# ---- BCB 中检 1 ----
set $bcb3a = ((unsigned char (*)(void))0x08040ccd)()
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_bcb_1 pc=0x%08x\n", (unsigned int)$pc
  quit 84
end
printf "P2_6_R9_S3 bcb_mid1=%u (应=4)\n", $bcb3a
if $bcb3a != 4
  printf "P2_6_R9_S3 ABORT bcb=%u 出现非 CONFIRMED, 停止\n", $bcb3a
  quit 84
end
# ---- EnterPath("/") ----
call ((void (*)(void*, const char*))0x08045619)($page3, "/")
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_enter pc=0x%08x\n", (unsigned int)$pc
  quit 85
end
printf "P2_6_R9_S3 enter_path_done\n"
# ---- 行扫描: 找 BAD 包 (24 行 = ROW_MAX) ----
set $row_index3 = -1
set $i3 = 0
while $i3 < 24
  set $row_path3 = (char*)$page3 + 0x146c + $i3 * 312 + 4
  set $cmp3 = ((int (*)(const char*, const char*))0x08052db7)($row_path3, "/P2-6A-FULL-v2.8.2-BAD-R9-20260901-02.etu")
  if $cmp3 == 0
    set $row_index3 = $i3
    loop_break
  end
  set $i3 = $i3 + 1
end
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_scan pc=0x%08x\n", (unsigned int)$pc
  quit 86
end
printf "P2_6_R9_S3 row_index=%d\n", $row_index3
if $row_index3 < 0
  printf "P2_6_R9_S3 ERROR package_row_not_found (harness 侧未及产品观测, 可修)\n"
  quit 86
end
# ---- 选中 BAD 包: SelectRow -> Inspect 首遍 (产品行为从这里开始计入 1/1) ----
call ((void (*)(void*, unsigned char))0x08045711)($page3, $row_index3)
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_select pc=0x%08x\n", (unsigned int)$pc
  quit 87
end
set $mode3a = *(unsigned char*)((char*)$page3 + 0x34e4)
printf "P2_6_R9_S3 confirm mode=%u (1=CONFIRM: 发起被接受; 0=被拒, 不得冒充中途失败)\n", $mode3a
if $mode3a != 1
  printf "P2_6_R9_S3 PRODUCT_REJECT mode=%u (Inspect 阶段被拒, 产品行为已观测, 停止)\n", $mode3a
  quit 87
end
set $owner_sel = *(unsigned char*)0x20053fa0
printf "P2_6_R9_S3 owner_at_confirm=%u (应=0)\n", $owner_sel
# ---- BCB 中检 2 ----
set $bcb3b = ((unsigned char (*)(void))0x08040ccd)()
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_bcb_2 pc=0x%08x\n", (unsigned int)$pc
  quit 87
end
printf "P2_6_R9_S3 bcb_mid2=%u (应=4)\n", $bcb3b
if $bcb3b != 4
  printf "P2_6_R9_S3 ABORT bcb=%u 出现非 CONFIRMED, 停止\n", $bcb3b
  quit 87
end
# ---- StartImport: mode->2 ----
call ((void (*)(void*))0x080457a9)($page3)
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_start pc=0x%08x\n", (unsigned int)$pc
  quit 88
end
set $mode3b = *(unsigned char*)((char*)$page3 + 0x34e4)
printf "P2_6_R9_S3 import_started mode=%u\n", $mode3b
if $mode3b != 2
  printf "P2_6_R9_S3 ERROR import_not_started mode=%u\n", $mode3b
  quit 88
end
set $r9s3_fail = 0
# ---- 停点 1: LzmaDec_Allocate 入口 (workspace_acquire 之后, 解码之前) ----
set $r9s3_magic = 0
thbreak *0x0804b568
commands
  silent
  set $r9s3_magic = 0x503260C3
end
continue
if $r9s3_magic != 0x503260C3
  printf "P2_6_R9_S3 ERROR unexpected_stop_lzma magic=0x%08x pc=0x%08x\n", $r9s3_magic, (unsigned int)$pc
  quit 89
end
if (unsigned int)$pc != 0x0804b568
  printf "P2_6_R9_S3 ERROR wrong_pc_lzma pc=0x%08x expected=0x0804b568\n", (unsigned int)$pc
  quit 89
end
delete breakpoints
monitor WriteU32 0xE0042008 0x00001000
printf "P2_6_R9_S3 lzma_alloc_entry pc=0x%08x\n", (unsigned int)$pc
# 决定性一格: owner 必须 == 2 (PACKAGE) — 先落盘再做任何有风险调用
set $owner_lzma = *(unsigned char*)0x20053fa0
printf "P2_6_R9_S3 DECISIVE owner_at_apply=%u (2=PACKAGE: Apply 窗口内 overlay 归包)\n", $owner_lzma
set $vcode_lzma = *(unsigned int*)0x08010408
set $mode_lzma = *(unsigned char*)((char*)$page3 + 0x34e4)
printf "P2_6_R9_S3 lzma_ctx vcode=%u mode=%u\n", $vcode_lzma, $mode_lzma
if $owner_lzma != 2
  printf "P2_6_R9_S3 FAIL owner_at_apply=%u expected=2 (如实登记, 继续观测)\n", $owner_lzma
  set $r9s3_fail = $r9s3_fail | 1
end
if $vcode_lzma != 20801
  printf "P2_6_R9_S3 FAIL vcode_changed=%u\n", $vcode_lzma
  set $r9s3_fail = $r9s3_fail | 2
end
# ---- BCB 中检 3 (Apply 窗口内) ----
set $bcb3c = ((unsigned char (*)(void))0x08040ccd)()
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_bcb_3 pc=0x%08x\n", (unsigned int)$pc
  quit 89
end
printf "P2_6_R9_S3 bcb_in_apply=%u (应=4)\n", $bcb3c
if $bcb3c != 4
  printf "P2_6_R9_S3 ABORT_STAGED_OR_APPLYING bcb=%u 立即停止原样上报\n", $bcb3c
  quit 89
end
# ---- 停点 2: FinishImport 入口 (Apply 已失败返回, cleanup 已跑) ----
set $r9s3_magic = 0
thbreak *0x08045074
commands
  silent
  set $r9s3_magic = 0x503260C4
end
continue
if $r9s3_magic != 0x503260C4
  printf "P2_6_R9_S3 ERROR unexpected_stop_finish magic=0x%08x pc=0x%08x\n", $r9s3_magic, (unsigned int)$pc
  quit 90
end
if (unsigned int)$pc != 0x08045074
  printf "P2_6_R9_S3 ERROR wrong_pc_finish pc=0x%08x expected=0x08045074\n", (unsigned int)$pc
  quit 90
end
delete breakpoints
monitor WriteU32 0xE0042008 0x00001000
printf "P2_6_R9_S3 finish_import_entry pc=0x%08x\n", (unsigned int)$pc
# 失败后: owner 必须回 0 (cleanup 已释放)
set $owner_fail = *(unsigned char*)0x20053fa0
printf "P2_6_R9_S3 owner_after_fail=%u (应=0: cleanup 释放)\n", $owner_fail
set $vcode_fail = *(unsigned int*)0x08010408
set $mode_fail = *(unsigned char*)((char*)$page3 + 0x34e4)
printf "P2_6_R9_S3 fail_ctx vcode=%u mode=%u(2=WORKING, FinishImport 内才置 3)\n", $vcode_fail, $mode_fail
if $owner_fail != 0
  printf "P2_6_R9_S3 FAIL owner_after_fail=%u expected=0 (如实登记, 继续观测)\n", $owner_fail
  set $r9s3_fail = $r9s3_fail | 4
end
if $vcode_fail != 20801
  printf "P2_6_R9_S3 FAIL vcode_changed=%u\n", $vcode_fail
  set $r9s3_fail = $r9s3_fail | 8
end
# ---- BCB 中检 4 (失败后) ----
set $bcb3d = ((unsigned char (*)(void))0x08040ccd)()
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_bcb_4 pc=0x%08x\n", (unsigned int)$pc
  quit 90
end
printf "P2_6_R9_S3 bcb_after_fail=%u (应=4: Apply 失败不得动 BCB)\n", $bcb3d
if $bcb3d != 4
  printf "P2_6_R9_S3 ABORT bcb=%u 非 CONFIRMED, 停止原样上报\n", $bcb3d
  quit 90
end
# ---- 停点 3: HAL_Update (FinishImport 完成, 页面进入 MODE_RESULT) ----
set $r9s3_magic = 0
thbreak *0x08040884
commands
  silent
  set $r9s3_magic = 0x503260C5
end
continue
if $r9s3_magic != 0x503260C5
  printf "P2_6_R9_S3 ERROR unexpected_stop_result magic=0x%08x pc=0x%08x\n", $r9s3_magic, (unsigned int)$pc
  quit 91
end
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR wrong_pc_result pc=0x%08x\n", (unsigned int)$pc
  quit 91
end
delete breakpoints
monitor WriteU32 0xE0042008 0x00001000
printf "P2_6_R9_S3 result_stopped pc=0x%08x\n", (unsigned int)$pc
set $mode3c = *(unsigned char*)((char*)$page3 + 0x34e4)
printf "P2_6_R9_S3 result mode=%u (3=MODE_RESULT: 失败结果页)\n", $mode3c
if $mode3c != 3
  printf "P2_6_R9_S3 FAIL result_mode=%u expected=3 (如实登记)\n", $mode3c
  set $r9s3_fail = $r9s3_fail | 16
end
set $owner_result = *(unsigned char*)0x20053fa0
printf "P2_6_R9_S3 owner_at_result=%u (应=0)\n", $owner_result
if $owner_result != 0
  printf "P2_6_R9_S3 FAIL owner_at_result=%u\n", $owner_result
  set $r9s3_fail = $r9s3_fail | 32
end
set $vcode_result = *(unsigned int*)0x08010408
printf "P2_6_R9_S3 vcode_at_result=%u (应=20801)\n", $vcode_result
if $vcode_result != 20801
  printf "P2_6_R9_S3 FAIL vcode_changed=%u\n", $vcode_result
  set $r9s3_fail = $r9s3_fail | 64
end
# ---- BCB 中检 5 (终态) ----
set $bcb3e = ((unsigned char (*)(void))0x08040ccd)()
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_S3 ERROR context_lost_bcb_5 pc=0x%08x\n", (unsigned int)$pc
  quit 91
end
printf "P2_6_R9_S3 bcb_final=%u (应=4)\n", $bcb3e
if $bcb3e != 4
  printf "P2_6_R9_S3 ABORT bcb=%u 非 CONFIRMED, 停止原样上报\n", $bcb3e
  quit 91
end
# ---- RTT ring dump (测量行 P2_6 kind=full result=<非-15 非-8 的失败码> 应在其中) ----
set $rtt3 = (unsigned char*)0x20053e1c
if $rtt3[0] != 0x53 || $rtt3[1] != 0x45 || $rtt3[2] != 0x47 || $rtt3[3] != 0x47
  printf "P2_6_R9_S3 ERROR rtt_signature\n"
  quit 92
end
set $up0_pbuf3 = *(unsigned int*)($rtt3 + 0x1C)
set $up0_size3 = *(unsigned int*)($rtt3 + 0x20)
set $up0_wroff3 = *(unsigned int*)($rtt3 + 0x24)
set $up0_rdoff3 = *(unsigned int*)($rtt3 + 0x28)
printf "P2_6_R9_S3 RTT_CB pBuffer=0x%08x size=%u wroff=%u rdoff=%u\n", $up0_pbuf3, $up0_size3, $up0_wroff3, $up0_rdoff3
if $up0_size3 != 1024
  printf "P2_6_R9_S3 ERROR up0_size=%u\n", $up0_size3
  quit 92
end
dump binary memory D:/github/my/E-Track/.cache/p2-6-sd-r9-20260901-01-implementation/logs/r9-s3-c7-rtt-cb.bin $rtt3 ($rtt3 + 0xA8)
dump binary memory D:/github/my/E-Track/.cache/p2-6-sd-r9-20260901-01-implementation/logs/r9-s3-c7-rtt-up0.bin $up0_pbuf3 ($up0_pbuf3 + $up0_size3)
printf "P2_6_R9_S3 SNAPSHOT_WRITTEN cb_bytes=168 ring_bytes=1024\n"
if $r9s3_fail != 0
  printf "P2_6_R9_S3 DONE_WITH_FAILURES fail_flags=0x%x (观测完成, 部分判据不符, 如实登记)\n", $r9s3_fail
else
  printf "P2_6_R9_S3 PASS c7_midfail_observed owner(2@apply)->owner(0@fail) mode=3 bcb=4 vcode=20801\n"
end
detach
quit
