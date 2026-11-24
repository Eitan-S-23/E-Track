ENTRY(re_bootstrap_entry)
PHDRS { vectors PT_LOAD FLAGS(4); code PT_LOAD FLAGS(5); state PT_LOAD FLAGS(6); }
SECTIONS
{
    .vectors 0x20060000 : { KEEP(*(.vectors)) } :vectors
    .text 0x20060400 : { KEEP(*(.text.re_entry)) *(.text*) *(.rodata*) } :code
    .ARM.extab : { *(.ARM.extab*) } :code
    .ARM.exidx : { *(.ARM.exidx*) } :code
    __code_end = .;
    .bss 0x20062000 (NOLOAD) : {
        __bss_start = .; KEEP(*(.bss.re_seen)) *(.bss*) *(COMMON)
        . = ALIGN(4); __bss_end = .;
    } :state
    .data : { *(.data*) } :state
    __stack_bottom = 0x20064000;
    __stack_top = 0x20066000;
    /DISCARD/ : { *(.comment) *(.note*) }
    ASSERT(SIZEOF(.vectors) == 524, "exact vector count required")
    ASSERT(__code_end <= 0x20062000, "bootstrap code overflow")
    ASSERT(__bss_end <= 0x20062800, "BSS overlaps sealed-input reservation")
    ASSERT(SIZEOF(.data) == 0, "no implicit initialized-data copy")
}
