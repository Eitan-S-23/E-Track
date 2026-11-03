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
target remote 127.0.0.1:25341
monitor exec DisableAutoUpdateFW
monitor exec SetRestartOnClose = 0
monitor flash breakpoints = 0
printf "P17_GDB_CPUID %08x\n", *(volatile unsigned int*)0xe000ed00
detach
quit
