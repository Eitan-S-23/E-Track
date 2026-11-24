.syntax unified
.thumb
.section .vectors,"a",%progbits
.global re_vectors
re_vectors:
    .word __stack_top
    .word re_bootstrap_entry
.set slot, 2
.rept 129
    .if (slot==7)||(slot==8)||(slot==9)||(slot==10)||(slot==13)||(slot==86)||(slot==90)||(slot==91)||(slot==95)||(slot==96)||(slot==101)||(slot==102)||(slot==103)||(slot==104)||(slot==105)||(slot==106)||(slot==109)||(slot==111)||(slot==112)||(slot==113)||(slot==114)||(slot==115)||(slot==116)||(slot==117)
        .word 0
    .else
        .word re_terminal
    .endif
    .set slot, slot+1
.endr
.global re_vectors_end
re_vectors_end:

.section .text.re_entry,"ax",%progbits
.global re_bootstrap_entry
.type re_bootstrap_entry,%function
.thumb_func
re_bootstrap_entry:
    mrs r0, ipsr
    cmp r0, #0
    bne re_terminal
    mrs r0, control
    tst r0, #7
    bne re_terminal
    mrs r0, primask
    cmp r0, #1
    bne re_terminal
    mrs r0, msp
    tst r0, #7
    bne re_terminal
    /* Reserve two conservative 108-byte hardware exception frames. */
    ldr r1, =0x200570d8
    cmp r0, r1
    blo re_terminal
    ldr r1, =0x20058000
    cmp r0, r1
    bhi re_terminal
    ldr r1, =0xe000ef34
    ldr r0, [r1]
    tst r0, #1
    bne re_terminal
    ldr r0, =re_vectors
    ldr r1, =0xe000ed08
    dsb
    str r0, [r1]
    dsb
    isb
    ldr r0, =__stack_top
    msr msp, r0
    isb
    ldr r0, =__bss_start
    ldr r1, =__bss_end
    movs r2, #0
1:  cmp r0, r1
    bhs 2f
    str r2, [r0], #4
    b 1b
2:  ldr r0, =re_bootstrap_seen
    movs r1, #1
    str r1, [r0]
    /* Both variants are offline artifacts until physical entry is qualified. */
#if defined(RE_ENTRY_BCB_CAPTURE)
    b re_bcb_entry_dispatch
#elif defined(RE_ENTRY_DISPATCH)
    b re_entry_dispatch
#else
    b re_terminal
#endif
.size re_bootstrap_entry, .-re_bootstrap_entry
.global re_terminal
.type re_terminal,%function
.thumb_func
re_terminal:
    cpsid i
3:  b 3b
.size re_terminal, .-re_terminal
.ltorg
.section .bss.re_seen,"aw",%nobits
.balign 4
.global re_bootstrap_seen
re_bootstrap_seen: .space 4
.section .note.GNU-stack,"",%progbits
