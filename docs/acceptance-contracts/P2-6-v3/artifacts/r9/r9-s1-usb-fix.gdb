set pagination off
set confirm off
set print elements 0
file "D:/github/my/E-Track/.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.elf"
target remote 127.0.0.1:24361
monitor halt
monitor WriteU32 0xE0042008 0x00001000
set $r9f_magic = 0
thbreak *0x08040884
commands
  silent
  set $r9f_magic = 0x503260F3
end
continue
if $r9f_magic != 0x503260F3
  printf "P2_6_R9_USBF ERROR unexpected_stop magic=0x%08x pc=0x%08x\n", $r9f_magic, (unsigned int)$pc
  quit 69
end
delete breakpoints
printf "P2_6_R9_USBF stop_verified pc=0x%08x\n", (unsigned int)$pc
# ---- 现状: conn_state 陈旧为 CONFIGURED(3) ----
set $conn_before = *(unsigned char*)0x20053970
set $plugged_before = ((unsigned char (*)(void))0x0804238d)()
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_USBF ERROR context_lost_before pc=0x%08x\n", (unsigned int)$pc
  quit 69
end
printf "P2_6_R9_USBF before conn_state=%u plugged=%u (软断连已生效宿主已脱离, 但 suspend IRQ 未触发)\n", $conn_before, $plugged_before
if $conn_before != 3
  printf "P2_6_R9_USBF NOTE conn_state=%u 非预期 CONFIGURED, 按实测处理\n", $conn_before
end
# ---- 补齐 usbd_suspend_handler 应产生的状态: old=conn, conn=SUSPENDED(4) ----
# 物理事实: usbd_disconnect 已软断连, Windows 已失 E:, 总线无宿主流量。
# 该字节写入仅复刻产品 suspend 中断处理器对 USB 传输层状态字的动作,
# 不涉及 QSPI/BCB/overlay/任何产品 OTA 状态。
set *(unsigned char*)0x20053971 = $conn_before
set *(unsigned char*)0x20053970 = 4
printf "P2_6_R9_USBF conn_state_fix old=%u conn=4(SUSPENDED)\n", $conn_before
# ---- 验证: USB_IsPlugged 必须=0 ----
set $plugged_after = ((unsigned char (*)(void))0x0804238d)()
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_USBF ERROR context_lost_after pc=0x%08x\n", (unsigned int)$pc
  quit 69
end
printf "P2_6_R9_USBF plugged_after=%u (应=0: MSC gate 打开)\n", $plugged_after
if $plugged_after != 0
  printf "P2_6_R9_USBF ERROR still_plugged=%u\n", $plugged_after
  quit 69
end
# ---- 状态无损 ----
set $sd_f = *(unsigned char*)0x20053214
set $owner_f = *(unsigned char*)0x20053fa0
set $bcb_f = ((unsigned char (*)(void))0x08040ccd)()
if (unsigned int)$pc != 0x08040884
  printf "P2_6_R9_USBF ERROR context_lost_bcb pc=0x%08x\n", (unsigned int)$pc
  quit 69
end
printf "P2_6_R9_USBF state sd=%u owner=%u bcb=%u\n", $sd_f, $owner_f, $bcb_f
if $sd_f != 1 || $owner_f != 0 || $bcb_f != 4
  printf "P2_6_R9_USBF ERROR state sd=%u owner=%u bcb=%u\n", $sd_f, $owner_f, $bcb_f
  quit 69
end
printf "P2_6_R9_USBF PASS usb_gate_cleared plugged=0 sd=1 owner=0 bcb=4\n"
detach
quit
