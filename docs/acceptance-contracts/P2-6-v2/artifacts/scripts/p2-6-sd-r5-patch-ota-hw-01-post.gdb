set pagination off
set confirm off
set print elements 0
file "D:/github/my/E-Track/.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.elf"
target remote 127.0.0.1:24361
monitor halt
monitor WriteU32 0xE0042008 0x00001000
set $rtt_cb = (unsigned char*)0x20053e1c
if $rtt_cb[0] != 0x53 || $rtt_cb[1] != 0x45 || $rtt_cb[2] != 0x47 || $rtt_cb[3] != 0x47 || $rtt_cb[4] != 0x45 || $rtt_cb[5] != 0x52 || $rtt_cb[6] != 0x20 || $rtt_cb[7] != 0x52 || $rtt_cb[8] != 0x54 || $rtt_cb[9] != 0x54
  printf "P2_6_RTT_POST ERROR rtt_signature\n"
  quit 41
end
printf "P2_6_RTT_POST attached_stopped pc=0x%08x\n", (unsigned int)$pc
dump binary memory D:/github/my/E-Track/.cache/p2-6-sd-r5-20260830-01-implementation/logs/p2-6-sd-r5-patch-ota-hw-01-rtt-cb-post.bin $rtt_cb ($rtt_cb + 0xA8)
printf "P2_6_RTT_POST SNAPSHOT_WRITTEN cb_bytes=168\n"
detach
quit
