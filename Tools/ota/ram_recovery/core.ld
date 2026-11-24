/* Callable transaction core only. No vectors, reset handler or device ports. */
ENTRY(rr_run)
MEMORY { RAM (rwx) : ORIGIN = 0x20058000, LENGTH = 0x28000 }
PHDRS { code PT_LOAD FLAGS(5); state PT_LOAD FLAGS(6); }
SECTIONS
{
    .text : { *(.text*) *(.rodata*) } > RAM :code
    .ARM.extab : { *(.ARM.extab*) } > RAM :code
    .ARM.exidx : { *(.ARM.exidx*) } > RAM :code
    .data : { *(.data*) } > RAM :state
    .bss (NOLOAD) : {
        . = ALIGN(8);
        __bss_start__ = .;
        KEEP(*(.bss.rr_workspace_storage))
        *(.bss*) *(COMMON)
        . = ALIGN(8);
        __bss_end__ = .;
    } > RAM :state
    .stack (NOLOAD) : {
        . = ALIGN(8);
        __stack_bottom__ = .;
        . += 8192;
        __stack_top__ = .;
    } > RAM :state
    /DISCARD/ : { *(.comment) *(.note*) }
    ASSERT(__stack_top__ <= ORIGIN(RAM) + LENGTH(RAM), "RAM core exceeds overlay")
}
