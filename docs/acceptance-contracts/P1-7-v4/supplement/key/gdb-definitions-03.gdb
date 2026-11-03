set pagination off
set confirm off
set auto-load off
set debuginfod enabled off
set trust-readonly-sections off
set mem inaccessible-by-default off
set breakpoint auto-hw on
set remote hardware-breakpoint-limit 6
set remotetimeout 5
file "D:/github/my/E-Track/.cache/p35-integration-20261028/source/.cache/p17-acceptance-20261103-01/prepare-01/boot.elf"
mem 0x08000000 0x08100000 ro
define p17-key-test
target remote 127.0.0.1:25341
monitor exec DisableAutoUpdateFW
monitor exec SetRestartOnClose = 0
monitor flash breakpoints = 0
set $p17_freeze = *(volatile unsigned int*)0xe0042008
set *(volatile unsigned int*)0xe0042008 = $p17_freeze | 0x1000
monitor halt
hbreak *0x080410c8
continue
if !($pc == 0x080410c8)
  echo P17_ERROR not_idle\n
  monitor halt
  disconnect
  quit 3
end
delete breakpoints
if !(*(volatile unsigned int*)0x08010400 == 0x57465445)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010404 == 0x00000001)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010408 == 0x00007669)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x0801040c == 0x2e332e33)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010410 == 0x00003331)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010414 == 0x00000000)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010418 == 0x00000000)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x0801041c == 0x6adf9926)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010420 == 0x00000001)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010424 == 0x00095ecc)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010428 == 0x8d873440)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x0801042c == 0xea654923)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010430 == 0x8ffe78ba)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010434 == 0xd706c17e)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010438 == 0xc8fd6b77)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x0801043c == 0x341e3f8d)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010440 == 0xc9533edc)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010444 == 0x93ac5ee7)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010448 == 0xffff0101)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x0801044c == 0xffffffff)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010450 == 0xffffffff)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010454 == 0xffffffff)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x08010458 == 0xffffffff)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x0801045c == 0x38436b1a)
  echo P17_ERROR header_changed\n
  monitor halt
  disconnect
  quit 3
end
if !(*(unsigned char*)0x200528a0 == 1)
  echo P17_ERROR app_state\n
  monitor halt
  disconnect
  quit 3
end
if !(*(unsigned char*)0x20053590 == 0)
  echo P17_ERROR app_state\n
  monitor halt
  disconnect
  quit 3
end
if !(*(unsigned char*)0x2005355e == 1)
  echo P17_ERROR app_state\n
  monitor halt
  disconnect
  quit 3
end
if !(*(unsigned char*)0x2005355c == 4)
  echo P17_ERROR app_state\n
  monitor halt
  disconnect
  quit 3
end
if !((*(volatile unsigned int*)0x4002c434 & 0x3800) == 0)
  echo P17_ERROR sdio_active\n
  monitor halt
  disconnect
  quit 3
end
set logging file D:/github/my/E-Track/.cache/p35-integration-20261028/source/.cache/p17-key-method-20261104-01/gdb-key-01/stage-hold.log
set logging overwrite on
set logging redirect on
set logging enabled on
echo P17_STAGE hold\n
set logging enabled off
set logging redirect off
set $p17_wait = 0
while !((*(volatile unsigned int*)0x40020010 & 0x8000) == 0) && $p17_wait < 1200
  monitor sleep 50
  set $p17_wait = $p17_wait + 1
end
if !((*(volatile unsigned int*)0x40020010 & 0x8000) == 0)
  echo P17_ERROR key_wait_timeout\n
  monitor halt
  disconnect
  quit 3
end
monitor reset
set *(volatile unsigned int*)0xe0042008 = $p17_freeze | 0x1000
hbreak *0x080019aa
continue
if !($pc == 0x080019aa && $r0 == 0)
  echo P17_ERROR boot_checkpoint\n
  monitor halt
  disconnect
  quit 3
end
delete breakpoints
if !(*(volatile unsigned int*)0xe000ed08 == 0x08000000)
  echo P17_ERROR boot_vectors\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x20000000 == 288000000 && *(volatile unsigned int*)0xe000e014 == 287999)
  echo P17_ERROR boot_clock\n
  monitor halt
  disconnect
  quit 3
end
if !((*(volatile unsigned int*)0x40020c14 & 4) != 0)
  echo P17_ERROR power_hold\n
  monitor halt
  disconnect
  quit 3
end
if !($sp > 0x20057000 && $sp <= 0x20058000 && ($sp & 7) == 0)
  echo P17_ERROR boot_stack\n
  monitor halt
  disconnect
  quit 3
end
if !($primask == 0 && $basepri == 0 && $faultmask == 0 && $control == 0)
  echo P17_ERROR interrupt_context\n
  monitor halt
  disconnect
  quit 3
end
if !(($xpsr & 0x1ff) == 0 && ($xpsr & 0x01000000) != 0)
  echo P17_ERROR thread_thumb_context\n
  monitor halt
  disconnect
  quit 3
end
if !((*(volatile unsigned int*)0xe000e010 & 7) == 7)
  echo P17_ERROR systick_enabled\n
  monitor halt
  disconnect
  quit 3
end
if !((*(volatile unsigned int*)0x40020000 >> 30) == 0 && (*(volatile unsigned int*)0x4002000c >> 30) == 1)
  echo P17_ERROR key_gpio_input_pullup\n
  monitor halt
  disconnect
  quit 3
end
if !(*(volatile unsigned int*)0x0800003c == 0x08001e45)
  echo P17_ERROR bound_systick_vector\n
  monitor halt
  disconnect
  quit 3
end
set $p17_saved_msp = $msp
set $p17_saved_psp = $psp
set $p17_saved_primask = $primask
set $p17_saved_basepri = $basepri
set $p17_saved_faultmask = $faultmask
set $p17_saved_control = $control
set $p17_saved_r0 = $r0
set $p17_saved_r1 = $r1
set $p17_saved_r2 = $r2
set $p17_saved_r3 = $r3
set $p17_saved_r4 = $r4
set $p17_saved_r5 = $r5
set $p17_saved_r6 = $r6
set $p17_saved_r7 = $r7
set $p17_saved_r8 = $r8
set $p17_saved_r9 = $r9
set $p17_saved_r10 = $r10
set $p17_saved_r11 = $r11
set $p17_saved_r12 = $r12
set $p17_saved_sp = $sp
set $p17_saved_lr = $lr
set $p17_saved_pc = $pc
set $p17_saved_xpsr = $xpsr
set $p17_scratch = $sp - 512
dump binary memory "D:/github/my/E-Track/.cache/p35-integration-20261028/source/.cache/p17-key-method-20261104-01/gdb-key-01/stack-before.bin" $p17_scratch $sp
if !((*(volatile unsigned int*)0x40020010 & 0x8000) == 0)
  echo P17_ERROR key_not_pressed\n
  monitor halt
  disconnect
  quit 3
end
set $p17_start_long = *(volatile unsigned int*)0x20001030
set $p17_result_long = ((int (*)(void))0x08001e6d)()
set $p17_ticks_long = (unsigned int)(*(volatile unsigned int*)0x20001030 - $p17_start_long)
printf "P17_RESULT long result=%d ticks=%u gpio=%08x\n", $p17_result_long, $p17_ticks_long, *(volatile unsigned int*)0x40020010
if !($r0 == $p17_saved_r0)
  echo P17_ERROR call_context_r0\n
  monitor halt
  disconnect
  quit 3
end
if !($r1 == $p17_saved_r1)
  echo P17_ERROR call_context_r1\n
  monitor halt
  disconnect
  quit 3
end
if !($r2 == $p17_saved_r2)
  echo P17_ERROR call_context_r2\n
  monitor halt
  disconnect
  quit 3
end
if !($r3 == $p17_saved_r3)
  echo P17_ERROR call_context_r3\n
  monitor halt
  disconnect
  quit 3
end
if !($r4 == $p17_saved_r4)
  echo P17_ERROR call_context_r4\n
  monitor halt
  disconnect
  quit 3
end
if !($r5 == $p17_saved_r5)
  echo P17_ERROR call_context_r5\n
  monitor halt
  disconnect
  quit 3
end
if !($r6 == $p17_saved_r6)
  echo P17_ERROR call_context_r6\n
  monitor halt
  disconnect
  quit 3
end
if !($r7 == $p17_saved_r7)
  echo P17_ERROR call_context_r7\n
  monitor halt
  disconnect
  quit 3
end
if !($r8 == $p17_saved_r8)
  echo P17_ERROR call_context_r8\n
  monitor halt
  disconnect
  quit 3
end
if !($r9 == $p17_saved_r9)
  echo P17_ERROR call_context_r9\n
  monitor halt
  disconnect
  quit 3
end
if !($r10 == $p17_saved_r10)
  echo P17_ERROR call_context_r10\n
  monitor halt
  disconnect
  quit 3
end
if !($r11 == $p17_saved_r11)
  echo P17_ERROR call_context_r11\n
  monitor halt
  disconnect
  quit 3
end
if !($r12 == $p17_saved_r12)
  echo P17_ERROR call_context_r12\n
  monitor halt
  disconnect
  quit 3
end
if !($sp == $p17_saved_sp)
  echo P17_ERROR call_context_sp\n
  monitor halt
  disconnect
  quit 3
end
if !($lr == $p17_saved_lr)
  echo P17_ERROR call_context_lr\n
  monitor halt
  disconnect
  quit 3
end
if !($pc == $p17_saved_pc)
  echo P17_ERROR call_context_pc\n
  monitor halt
  disconnect
  quit 3
end
if !($xpsr == $p17_saved_xpsr)
  echo P17_ERROR call_context_xpsr\n
  monitor halt
  disconnect
  quit 3
end
if !($msp == $p17_saved_msp)
  echo P17_ERROR call_special_msp\n
  monitor halt
  disconnect
  quit 3
end
if !($psp == $p17_saved_psp)
  echo P17_ERROR call_special_psp\n
  monitor halt
  disconnect
  quit 3
end
if !($primask == $p17_saved_primask)
  echo P17_ERROR call_special_primask\n
  monitor halt
  disconnect
  quit 3
end
if !($basepri == $p17_saved_basepri)
  echo P17_ERROR call_special_basepri\n
  monitor halt
  disconnect
  quit 3
end
if !($faultmask == $p17_saved_faultmask)
  echo P17_ERROR call_special_faultmask\n
  monitor halt
  disconnect
  quit 3
end
if !($control == $p17_saved_control)
  echo P17_ERROR call_special_control\n
  monitor halt
  disconnect
  quit 3
end
if !($p17_result_long == 1 && $p17_ticks_long >= 3000)
  echo P17_ERROR long_predicate\n
  monitor halt
  disconnect
  quit 3
end
set logging file D:/github/my/E-Track/.cache/p35-integration-20261028/source/.cache/p17-key-method-20261104-01/gdb-key-01/stage-release.log
set logging overwrite on
set logging redirect on
set logging enabled on
echo P17_STAGE release\n
set logging enabled off
set logging redirect off
set $p17_wait = 0
while !((*(volatile unsigned int*)0x40020010 & 0x8000) != 0) && $p17_wait < 1200
  monitor sleep 50
  set $p17_wait = $p17_wait + 1
end
if !((*(volatile unsigned int*)0x40020010 & 0x8000) != 0)
  echo P17_ERROR key_wait_timeout\n
  monitor halt
  disconnect
  quit 3
end
set logging file D:/github/my/E-Track/.cache/p35-integration-20261028/source/.cache/p17-key-method-20261104-01/gdb-key-01/stage-short.log
set logging overwrite on
set logging redirect on
set logging enabled on
echo P17_STAGE short\n
set logging enabled off
set logging redirect off
set $p17_wait = 0
while !((*(volatile unsigned int*)0x40020010 & 0x8000) == 0) && $p17_wait < 1200
  monitor sleep 50
  set $p17_wait = $p17_wait + 1
end
if !((*(volatile unsigned int*)0x40020010 & 0x8000) == 0)
  echo P17_ERROR key_wait_timeout\n
  monitor halt
  disconnect
  quit 3
end
if !((*(volatile unsigned int*)0x40020010 & 0x8000) == 0)
  echo P17_ERROR key_not_pressed\n
  monitor halt
  disconnect
  quit 3
end
set $p17_start_short = *(volatile unsigned int*)0x20001030
set $p17_result_short = ((int (*)(void))0x08001e6d)()
set $p17_ticks_short = (unsigned int)(*(volatile unsigned int*)0x20001030 - $p17_start_short)
printf "P17_RESULT short result=%d ticks=%u gpio=%08x\n", $p17_result_short, $p17_ticks_short, *(volatile unsigned int*)0x40020010
if !($r0 == $p17_saved_r0)
  echo P17_ERROR call_context_r0\n
  monitor halt
  disconnect
  quit 3
end
if !($r1 == $p17_saved_r1)
  echo P17_ERROR call_context_r1\n
  monitor halt
  disconnect
  quit 3
end
if !($r2 == $p17_saved_r2)
  echo P17_ERROR call_context_r2\n
  monitor halt
  disconnect
  quit 3
end
if !($r3 == $p17_saved_r3)
  echo P17_ERROR call_context_r3\n
  monitor halt
  disconnect
  quit 3
end
if !($r4 == $p17_saved_r4)
  echo P17_ERROR call_context_r4\n
  monitor halt
  disconnect
  quit 3
end
if !($r5 == $p17_saved_r5)
  echo P17_ERROR call_context_r5\n
  monitor halt
  disconnect
  quit 3
end
if !($r6 == $p17_saved_r6)
  echo P17_ERROR call_context_r6\n
  monitor halt
  disconnect
  quit 3
end
if !($r7 == $p17_saved_r7)
  echo P17_ERROR call_context_r7\n
  monitor halt
  disconnect
  quit 3
end
if !($r8 == $p17_saved_r8)
  echo P17_ERROR call_context_r8\n
  monitor halt
  disconnect
  quit 3
end
if !($r9 == $p17_saved_r9)
  echo P17_ERROR call_context_r9\n
  monitor halt
  disconnect
  quit 3
end
if !($r10 == $p17_saved_r10)
  echo P17_ERROR call_context_r10\n
  monitor halt
  disconnect
  quit 3
end
if !($r11 == $p17_saved_r11)
  echo P17_ERROR call_context_r11\n
  monitor halt
  disconnect
  quit 3
end
if !($r12 == $p17_saved_r12)
  echo P17_ERROR call_context_r12\n
  monitor halt
  disconnect
  quit 3
end
if !($sp == $p17_saved_sp)
  echo P17_ERROR call_context_sp\n
  monitor halt
  disconnect
  quit 3
end
if !($lr == $p17_saved_lr)
  echo P17_ERROR call_context_lr\n
  monitor halt
  disconnect
  quit 3
end
if !($pc == $p17_saved_pc)
  echo P17_ERROR call_context_pc\n
  monitor halt
  disconnect
  quit 3
end
if !($xpsr == $p17_saved_xpsr)
  echo P17_ERROR call_context_xpsr\n
  monitor halt
  disconnect
  quit 3
end
if !($msp == $p17_saved_msp)
  echo P17_ERROR call_special_msp\n
  monitor halt
  disconnect
  quit 3
end
if !($psp == $p17_saved_psp)
  echo P17_ERROR call_special_psp\n
  monitor halt
  disconnect
  quit 3
end
if !($primask == $p17_saved_primask)
  echo P17_ERROR call_special_primask\n
  monitor halt
  disconnect
  quit 3
end
if !($basepri == $p17_saved_basepri)
  echo P17_ERROR call_special_basepri\n
  monitor halt
  disconnect
  quit 3
end
if !($faultmask == $p17_saved_faultmask)
  echo P17_ERROR call_special_faultmask\n
  monitor halt
  disconnect
  quit 3
end
if !($control == $p17_saved_control)
  echo P17_ERROR call_special_control\n
  monitor halt
  disconnect
  quit 3
end
if !($p17_result_short == 0 && $p17_ticks_short > 0 && $p17_ticks_short < 3000)
  echo P17_ERROR short_predicate\n
  monitor halt
  disconnect
  quit 3
end
dump binary memory "D:/github/my/E-Track/.cache/p35-integration-20261028/source/.cache/p17-key-method-20261104-01/gdb-key-01/stack-after.bin" $p17_scratch $sp
restore "D:/github/my/E-Track/.cache/p35-integration-20261028/source/.cache/p17-key-method-20261104-01/gdb-key-01/stack-before.bin" binary $p17_scratch
if !($pc == 0x080019aa)
  echo P17_ERROR resume_checkpoint\n
  monitor halt
  disconnect
  quit 3
end
set *(volatile unsigned int*)0xe0042008 = $p17_freeze
detach
set logging file D:/github/my/E-Track/.cache/p35-integration-20261028/source/.cache/p17-key-method-20261104-01/gdb-key-01/stage-finished.log
set logging overwrite on
set logging redirect on
set logging enabled on
echo P17_STAGE finished\n
set logging enabled off
set logging redirect off
end
