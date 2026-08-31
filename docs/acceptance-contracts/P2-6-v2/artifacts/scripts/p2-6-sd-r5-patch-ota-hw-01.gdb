set pagination off
set confirm off
set print elements 0
file "D:/github/my/E-Track/.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.elf"
target remote 127.0.0.1:24361
monitor halt
monitor WriteU32 0xE0042008 0x00001000
set $p2_6_attach_pc = (unsigned int)$pc
printf "P2_6_TRANSPORT attached_stopped pc=0x%08x\n", $p2_6_attach_pc
set $p2_6_stop_magic = 0
thbreak *0x08040884
commands
  silent
  set $p2_6_stop_magic = 0x50326001
  printf "P2_6_TRANSPORT breakpoint label=initial_hal_update pc=0x%08x\n", (unsigned int)$pc
end
continue
if $p2_6_stop_magic != 0x50326001
  printf "P2_6_TRANSPORT ERROR unexpected_stop label=initial_hal_update magic=0x%08x pc=0x%08x\n", $p2_6_stop_magic, (unsigned int)$pc
  quit 20
end
if (unsigned int)$pc != 0x08040884
  printf "P2_6_TRANSPORT ERROR wrong_pc label=initial_hal_update pc=0x%08x expected=0x08040884\n", (unsigned int)$pc
  quit 20
end
delete breakpoints
printf "P2_6_TRANSPORT stop_verified label=initial_hal_update pc=0x%08x\n", (unsigned int)$pc
if *(unsigned int*)0x08010400 != 0x57465445
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=0 actual=0x%08x expected=0x57465445\n", *(unsigned int*)0x08010400
  quit 21
end
if *(unsigned int*)0x08010404 != 0x00000001
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=4 actual=0x%08x expected=0x00000001\n", *(unsigned int*)0x08010404
  quit 21
end
if *(unsigned int*)0x08010408 != 0x00005140
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=8 actual=0x%08x expected=0x00005140\n", *(unsigned int*)0x08010408
  quit 21
end
if *(unsigned int*)0x0801040c != 0x2e382e32
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=12 actual=0x%08x expected=0x2e382e32\n", *(unsigned int*)0x0801040c
  quit 21
end
if *(unsigned int*)0x08010410 != 0x00000030
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=16 actual=0x%08x expected=0x00000030\n", *(unsigned int*)0x08010410
  quit 21
end
if *(unsigned int*)0x08010414 != 0x00000000
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=20 actual=0x%08x expected=0x00000000\n", *(unsigned int*)0x08010414
  quit 21
end
if *(unsigned int*)0x08010418 != 0x00000000
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=24 actual=0x%08x expected=0x00000000\n", *(unsigned int*)0x08010418
  quit 21
end
if *(unsigned int*)0x0801041c != 0x6a791480
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=28 actual=0x%08x expected=0x6a791480\n", *(unsigned int*)0x0801041c
  quit 21
end
if *(unsigned int*)0x08010420 != 0x00000001
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=32 actual=0x%08x expected=0x00000001\n", *(unsigned int*)0x08010420
  quit 21
end
if *(unsigned int*)0x08010424 != 0x00092aa8
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=36 actual=0x%08x expected=0x00092aa8\n", *(unsigned int*)0x08010424
  quit 21
end
if *(unsigned int*)0x08010428 != 0x995b2295
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=40 actual=0x%08x expected=0x995b2295\n", *(unsigned int*)0x08010428
  quit 21
end
if *(unsigned int*)0x0801042c != 0x32cec876
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=44 actual=0x%08x expected=0x32cec876\n", *(unsigned int*)0x0801042c
  quit 21
end
if *(unsigned int*)0x08010430 != 0xb238f5e5
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=48 actual=0x%08x expected=0xb238f5e5\n", *(unsigned int*)0x08010430
  quit 21
end
if *(unsigned int*)0x08010434 != 0x9eaa9e8e
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=52 actual=0x%08x expected=0x9eaa9e8e\n", *(unsigned int*)0x08010434
  quit 21
end
if *(unsigned int*)0x08010438 != 0xd351fb0c
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=56 actual=0x%08x expected=0xd351fb0c\n", *(unsigned int*)0x08010438
  quit 21
end
if *(unsigned int*)0x0801043c != 0xbf69c718
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=60 actual=0x%08x expected=0xbf69c718\n", *(unsigned int*)0x0801043c
  quit 21
end
if *(unsigned int*)0x08010440 != 0x286ce5cf
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=64 actual=0x%08x expected=0x286ce5cf\n", *(unsigned int*)0x08010440
  quit 21
end
if *(unsigned int*)0x08010444 != 0xfa7218e6
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=68 actual=0x%08x expected=0xfa7218e6\n", *(unsigned int*)0x08010444
  quit 21
end
if *(unsigned int*)0x08010448 != 0xffff0101
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=72 actual=0x%08x expected=0xffff0101\n", *(unsigned int*)0x08010448
  quit 21
end
if *(unsigned int*)0x0801044c != 0xffffffff
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=76 actual=0x%08x expected=0xffffffff\n", *(unsigned int*)0x0801044c
  quit 21
end
if *(unsigned int*)0x08010450 != 0xffffffff
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=80 actual=0x%08x expected=0xffffffff\n", *(unsigned int*)0x08010450
  quit 21
end
if *(unsigned int*)0x08010454 != 0xffffffff
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=84 actual=0x%08x expected=0xffffffff\n", *(unsigned int*)0x08010454
  quit 21
end
if *(unsigned int*)0x08010458 != 0xffffffff
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=88 actual=0x%08x expected=0xffffffff\n", *(unsigned int*)0x08010458
  quit 21
end
if *(unsigned int*)0x0801045c != 0xc9c387a0
  printf "P2_6_IDENTITY ERROR label=before_ota_fw offset=92 actual=0x%08x expected=0xc9c387a0\n", *(unsigned int*)0x0801045c
  quit 21
end
printf "P2_6_IDENTITY PASS label=before_ota_fw header_bytes=96\n"
set $rtt_before_ota = (unsigned char*)0x20053e1c
if $rtt_before_ota[0] != 0x53 || $rtt_before_ota[1] != 0x45 || $rtt_before_ota[2] != 0x47 || $rtt_before_ota[3] != 0x47 || $rtt_before_ota[4] != 0x45 || $rtt_before_ota[5] != 0x52 || $rtt_before_ota[6] != 0x20 || $rtt_before_ota[7] != 0x52 || $rtt_before_ota[8] != 0x54 || $rtt_before_ota[9] != 0x54
  printf "P2_6_STATE ERROR label=before_ota rtt_signature\n"
  quit 21
end
set $sd_before_ota = *(unsigned char*)0x20053214
set $vtor_before_ota = *(unsigned int*)0xe000ed08
set $cfsr_before_ota = *(unsigned int*)0xe000ed28
set $owner_before_ota = *(unsigned char*)0x20053fa0
if $sd_before_ota != 1 || $vtor_before_ota != 0x08010000 || $cfsr_before_ota != 0 || $owner_before_ota != 0
  printf "P2_6_STATE ERROR label=before_ota sd=%u vtor=0x%08x cfsr=0x%08x owner=%u\n", $sd_before_ota, $vtor_before_ota, $cfsr_before_ota, $owner_before_ota
  quit 21
end
set $bcb_before_ota = ((unsigned char (*)(void))0x08040ccd)()
set $p2_6_checked_pc = (unsigned int)$pc
if $p2_6_checked_pc != 0x08040884
  printf "P2_6_TRANSPORT ERROR context_lost label=before_ota_bcb_call pc=0x%08x expected=0x08040884\n", $p2_6_checked_pc
  quit 21
end
printf "P2_6_TRANSPORT context_verified label=before_ota_bcb_call pc=0x%08x\n", $p2_6_checked_pc
if $bcb_before_ota != 4
  printf "P2_6_STATE ERROR label=before_ota bcb=%u expected=4\n", $bcb_before_ota
  quit 21
end
printf "P2_6_STATE PASS label=before_ota sd=%u vtor=0x%08x cfsr=0x%08x bcb=%u owner=%u\n", $sd_before_ota, $vtor_before_ota, $cfsr_before_ota, $bcb_before_ota, $owner_before_ota
set $initial_page = *(void**)0x20050534
if $initial_page == 0
  printf "P2_6_RTT_DRIVER ERROR no_initial_page context_harness_fail\n"
  quit 22
end
set $push_ok = ((unsigned char (*)(void*, const char*, void*))0x0803db95)((void*)0x200504f8, "Pages/FirmwareUpdate", 0)
set $p2_6_checked_pc = (unsigned int)$pc
if $p2_6_checked_pc != 0x08040884
  printf "P2_6_TRANSPORT ERROR context_lost label=push_return pc=0x%08x expected=0x08040884\n", $p2_6_checked_pc
  quit 23
end
printf "P2_6_TRANSPORT context_verified label=push_return pc=0x%08x\n", $p2_6_checked_pc
printf "P2_6_RTT_DRIVER push_ok=%u\n", $push_ok
if $push_ok == 0
  printf "P2_6_RTT_DRIVER ERROR push_failed context_harness_fail\n"
  quit 24
end
set $page = *(void**)0x20050534
printf "P2_6_RTT_DRIVER page=0x%08x\n", $page
if $page == 0
  printf "P2_6_RTT_DRIVER ERROR no_current_page context_harness_fail\n"
  quit 25
end
set $expected_vptr = 0x0809cb44
if *(unsigned int*)$page != $expected_vptr
  printf "P2_6_RTT_DRIVER ERROR wrong_page vptr=0x%08x expected=0x%08x\n", *(unsigned int*)$page, $expected_vptr
  quit 26
end
set $page_state = *(unsigned char*)((char*)$page + 36)
if $page_state != 3 && $page_state != 4
  printf "P2_6_RTT_DRIVER ERROR wrong_page_state state=%u expected=3_or_4\n", $page_state
  quit 27
end
printf "P2_6_RTT_DRIVER page_ready state=%u\n", $page_state
call ((void (*)(void*, const char*))0x08045619)($page, "/")
set $p2_6_checked_pc = (unsigned int)$pc
if $p2_6_checked_pc != 0x08040884
  printf "P2_6_TRANSPORT ERROR context_lost label=enter_path_return pc=0x%08x expected=0x08040884\n", $p2_6_checked_pc
  quit 28
end
printf "P2_6_TRANSPORT context_verified label=enter_path_return pc=0x%08x\n", $p2_6_checked_pc
set $row_index = -1
set $i = 0
while $i < 24
  set $row_path = (char*)$page + 0x146c + $i * 312 + 4
  set $cmp = ((int (*)(const char*, const char*))0x08052db7)($row_path, "/P2-6A-PATCH-v2.8.0-to-v2.8.1-R5-20260830-01.etu")
  if $cmp == 0
    set $row_index = $i
    loop_break
  end
  set $i = $i + 1
end
set $p2_6_checked_pc = (unsigned int)$pc
if $p2_6_checked_pc != 0x08040884
  printf "P2_6_TRANSPORT ERROR context_lost label=row_scan_return pc=0x%08x expected=0x08040884\n", $p2_6_checked_pc
  quit 29
end
printf "P2_6_TRANSPORT context_verified label=row_scan_return pc=0x%08x\n", $p2_6_checked_pc
printf "P2_6_RTT_DRIVER row_index=%d\n", $row_index
if $row_index < 0
  printf "P2_6_RTT_DRIVER ERROR package_row_not_found\n"
  quit 30
end
call ((void (*)(void*, unsigned char))0x08045711)($page, $row_index)
set $p2_6_checked_pc = (unsigned int)$pc
if $p2_6_checked_pc != 0x08040884
  printf "P2_6_TRANSPORT ERROR context_lost label=select_row_return pc=0x%08x expected=0x08040884\n", $p2_6_checked_pc
  quit 31
end
printf "P2_6_TRANSPORT context_verified label=select_row_return pc=0x%08x\n", $p2_6_checked_pc
set $mode = *(unsigned char*)((char*)$page + 0x34e4)
printf "P2_6_RTT_DRIVER confirm mode=%u kind=PATCH\n", $mode
if $mode != 1
  printf "P2_6_RTT_DRIVER ERROR confirm_not_reached\n"
  quit 32
end
call ((void (*)(void*))0x080457a9)($page)
set $p2_6_checked_pc = (unsigned int)$pc
if $p2_6_checked_pc != 0x08040884
  printf "P2_6_TRANSPORT ERROR context_lost label=start_import_return pc=0x%08x expected=0x08040884\n", $p2_6_checked_pc
  quit 33
end
printf "P2_6_TRANSPORT context_verified label=start_import_return pc=0x%08x\n", $p2_6_checked_pc
set $mode = *(unsigned char*)((char*)$page + 0x34e4)
printf "P2_6_RTT_DRIVER import_started mode=%u\n", $mode
if $mode != 2
  printf "P2_6_RTT_DRIVER ERROR import_not_started\n"
  quit 34
end
set $p2_6_stop_magic = 0
thbreak *0x08045074
commands
  silent
  set $p2_6_stop_magic = 0x50326002
  printf "P2_6_TRANSPORT breakpoint label=finish_import_entry pc=0x%08x\n", (unsigned int)$pc
end
continue
if $p2_6_stop_magic != 0x50326002
  printf "P2_6_TRANSPORT ERROR unexpected_stop label=finish_import_entry magic=0x%08x pc=0x%08x\n", $p2_6_stop_magic, (unsigned int)$pc
  quit 35
end
if (unsigned int)$pc != 0x08045074
  printf "P2_6_TRANSPORT ERROR wrong_pc label=finish_import_entry pc=0x%08x expected=0x08045074\n", (unsigned int)$pc
  quit 35
end
delete breakpoints
printf "P2_6_TRANSPORT stop_verified label=finish_import_entry pc=0x%08x\n", (unsigned int)$pc
set $p2_6_stop_magic = 0
thbreak *0x08040884
commands
  silent
  set $p2_6_stop_magic = 0x50326003
  printf "P2_6_TRANSPORT breakpoint label=result_hal_update pc=0x%08x\n", (unsigned int)$pc
end
continue
if $p2_6_stop_magic != 0x50326003
  printf "P2_6_TRANSPORT ERROR unexpected_stop label=result_hal_update magic=0x%08x pc=0x%08x\n", $p2_6_stop_magic, (unsigned int)$pc
  quit 36
end
if (unsigned int)$pc != 0x08040884
  printf "P2_6_TRANSPORT ERROR wrong_pc label=result_hal_update pc=0x%08x expected=0x08040884\n", (unsigned int)$pc
  quit 36
end
delete breakpoints
printf "P2_6_TRANSPORT stop_verified label=result_hal_update pc=0x%08x\n", (unsigned int)$pc
set $mode = *(unsigned char*)((char*)$page + 0x34e4)
if *(unsigned int*)0x08010400 != 0x57465445
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=0 actual=0x%08x expected=0x57465445\n", *(unsigned int*)0x08010400
  quit 37
end
if *(unsigned int*)0x08010404 != 0x00000001
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=4 actual=0x%08x expected=0x00000001\n", *(unsigned int*)0x08010404
  quit 37
end
if *(unsigned int*)0x08010408 != 0x00005140
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=8 actual=0x%08x expected=0x00005140\n", *(unsigned int*)0x08010408
  quit 37
end
if *(unsigned int*)0x0801040c != 0x2e382e32
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=12 actual=0x%08x expected=0x2e382e32\n", *(unsigned int*)0x0801040c
  quit 37
end
if *(unsigned int*)0x08010410 != 0x00000030
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=16 actual=0x%08x expected=0x00000030\n", *(unsigned int*)0x08010410
  quit 37
end
if *(unsigned int*)0x08010414 != 0x00000000
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=20 actual=0x%08x expected=0x00000000\n", *(unsigned int*)0x08010414
  quit 37
end
if *(unsigned int*)0x08010418 != 0x00000000
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=24 actual=0x%08x expected=0x00000000\n", *(unsigned int*)0x08010418
  quit 37
end
if *(unsigned int*)0x0801041c != 0x6a791480
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=28 actual=0x%08x expected=0x6a791480\n", *(unsigned int*)0x0801041c
  quit 37
end
if *(unsigned int*)0x08010420 != 0x00000001
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=32 actual=0x%08x expected=0x00000001\n", *(unsigned int*)0x08010420
  quit 37
end
if *(unsigned int*)0x08010424 != 0x00092aa8
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=36 actual=0x%08x expected=0x00092aa8\n", *(unsigned int*)0x08010424
  quit 37
end
if *(unsigned int*)0x08010428 != 0x995b2295
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=40 actual=0x%08x expected=0x995b2295\n", *(unsigned int*)0x08010428
  quit 37
end
if *(unsigned int*)0x0801042c != 0x32cec876
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=44 actual=0x%08x expected=0x32cec876\n", *(unsigned int*)0x0801042c
  quit 37
end
if *(unsigned int*)0x08010430 != 0xb238f5e5
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=48 actual=0x%08x expected=0xb238f5e5\n", *(unsigned int*)0x08010430
  quit 37
end
if *(unsigned int*)0x08010434 != 0x9eaa9e8e
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=52 actual=0x%08x expected=0x9eaa9e8e\n", *(unsigned int*)0x08010434
  quit 37
end
if *(unsigned int*)0x08010438 != 0xd351fb0c
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=56 actual=0x%08x expected=0xd351fb0c\n", *(unsigned int*)0x08010438
  quit 37
end
if *(unsigned int*)0x0801043c != 0xbf69c718
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=60 actual=0x%08x expected=0xbf69c718\n", *(unsigned int*)0x0801043c
  quit 37
end
if *(unsigned int*)0x08010440 != 0x286ce5cf
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=64 actual=0x%08x expected=0x286ce5cf\n", *(unsigned int*)0x08010440
  quit 37
end
if *(unsigned int*)0x08010444 != 0xfa7218e6
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=68 actual=0x%08x expected=0xfa7218e6\n", *(unsigned int*)0x08010444
  quit 37
end
if *(unsigned int*)0x08010448 != 0xffff0101
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=72 actual=0x%08x expected=0xffff0101\n", *(unsigned int*)0x08010448
  quit 37
end
if *(unsigned int*)0x0801044c != 0xffffffff
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=76 actual=0x%08x expected=0xffffffff\n", *(unsigned int*)0x0801044c
  quit 37
end
if *(unsigned int*)0x08010450 != 0xffffffff
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=80 actual=0x%08x expected=0xffffffff\n", *(unsigned int*)0x08010450
  quit 37
end
if *(unsigned int*)0x08010454 != 0xffffffff
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=84 actual=0x%08x expected=0xffffffff\n", *(unsigned int*)0x08010454
  quit 37
end
if *(unsigned int*)0x08010458 != 0xffffffff
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=88 actual=0x%08x expected=0xffffffff\n", *(unsigned int*)0x08010458
  quit 37
end
if *(unsigned int*)0x0801045c != 0xc9c387a0
  printf "P2_6_IDENTITY ERROR label=after_ota_fw offset=92 actual=0x%08x expected=0xc9c387a0\n", *(unsigned int*)0x0801045c
  quit 37
end
printf "P2_6_IDENTITY PASS label=after_ota_fw header_bytes=96\n"
set $rtt_after_ota = (unsigned char*)0x20053e1c
if $rtt_after_ota[0] != 0x53 || $rtt_after_ota[1] != 0x45 || $rtt_after_ota[2] != 0x47 || $rtt_after_ota[3] != 0x47 || $rtt_after_ota[4] != 0x45 || $rtt_after_ota[5] != 0x52 || $rtt_after_ota[6] != 0x20 || $rtt_after_ota[7] != 0x52 || $rtt_after_ota[8] != 0x54 || $rtt_after_ota[9] != 0x54
  printf "P2_6_STATE ERROR label=after_ota rtt_signature\n"
  quit 37
end
set $sd_after_ota = *(unsigned char*)0x20053214
set $vtor_after_ota = *(unsigned int*)0xe000ed08
set $cfsr_after_ota = *(unsigned int*)0xe000ed28
set $owner_after_ota = *(unsigned char*)0x20053fa0
if $sd_after_ota != 1 || $vtor_after_ota != 0x08010000 || $cfsr_after_ota != 0 || $owner_after_ota != 0
  printf "P2_6_STATE ERROR label=after_ota sd=%u vtor=0x%08x cfsr=0x%08x owner=%u\n", $sd_after_ota, $vtor_after_ota, $cfsr_after_ota, $owner_after_ota
  quit 37
end
set $bcb_after_ota = ((unsigned char (*)(void))0x08040ccd)()
set $p2_6_checked_pc = (unsigned int)$pc
if $p2_6_checked_pc != 0x08040884
  printf "P2_6_TRANSPORT ERROR context_lost label=after_ota_bcb_call pc=0x%08x expected=0x08040884\n", $p2_6_checked_pc
  quit 37
end
printf "P2_6_TRANSPORT context_verified label=after_ota_bcb_call pc=0x%08x\n", $p2_6_checked_pc
if $bcb_after_ota != 1
  printf "P2_6_STATE ERROR label=after_ota bcb=%u expected=1\n", $bcb_after_ota
  quit 37
end
printf "P2_6_STATE PASS label=after_ota sd=%u vtor=0x%08x cfsr=0x%08x bcb=%u owner=%u\n", $sd_after_ota, $vtor_after_ota, $cfsr_after_ota, $bcb_after_ota, $owner_after_ota
printf "P2_6_RTT_DRIVER result mode=%u\n", $mode
if $mode != 3
  printf "P2_6_RTT_DRIVER ERROR result_mode_not_reached\n"
  quit 38
end
printf "P2_6_RTT_DRIVER PASS kind=PATCH page_state=%u mode=%u\n", $page_state, $mode

# Two-phase RTT capture, phase 1: snapshot the Up0 inventory while halted.
set $rtt_cb = (unsigned char*)0x20053e1c
if $rtt_cb[0] != 0x53 || $rtt_cb[1] != 0x45 || $rtt_cb[2] != 0x47 || $rtt_cb[3] != 0x47 || $rtt_cb[4] != 0x45 || $rtt_cb[5] != 0x52 || $rtt_cb[6] != 0x20 || $rtt_cb[7] != 0x52 || $rtt_cb[8] != 0x54 || $rtt_cb[9] != 0x54
  printf "P2_6_RTT_DRIVER ERROR rtt_signature_at_snapshot\n"
  quit 39
end
set $up0_pbuf = *(unsigned int*)($rtt_cb + 0x1C)
set $up0_size = *(unsigned int*)($rtt_cb + 0x20)
set $up0_wroff = *(unsigned int*)($rtt_cb + 0x24)
set $up0_rdoff = *(unsigned int*)($rtt_cb + 0x28)
printf "P2_6_RTT_CB pBuffer=0x%08x size=%u wroff=%u rdoff=%u\n", $up0_pbuf, $up0_size, $up0_wroff, $up0_rdoff
if $up0_size != 1024
  printf "P2_6_RTT_DRIVER ERROR up0_size=%u\n", $up0_size
  quit 40
end
dump binary memory D:/github/my/E-Track/.cache/p2-6-sd-r5-20260830-01-implementation/logs/p2-6-sd-r5-patch-ota-hw-01-rtt-cb-pre.bin $rtt_cb ($rtt_cb + 0xA8)
dump binary memory D:/github/my/E-Track/.cache/p2-6-sd-r5-20260830-01-implementation/logs/p2-6-sd-r5-patch-ota-hw-01-rtt-up0-pre.bin $up0_pbuf ($up0_pbuf + $up0_size)
printf "P2_6_RTT_DRIVER SNAPSHOT_WRITTEN cb_bytes=168 ring_bytes=%u\n", $up0_size
detach
quit
