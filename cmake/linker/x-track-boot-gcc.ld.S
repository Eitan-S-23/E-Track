#include "ota_layout.h"

ENTRY(Reset_Handler)

_estack = ORIGIN(RAM) + LENGTH(RAM);
_sstack = ORIGIN(RAM);
_Min_Heap_Size = 0x200;
_Min_Stack_Size = 0x1000;

MEMORY
{
  FLASH (rx) : ORIGIN = OTA_BOOT_ORIGIN, LENGTH = OTA_BOOT_LENGTH
#if defined(P2_1_TEST_ENABLE)
  RAM (xrw)  : ORIGIN = OTA_RAM_ORIGIN, LENGTH = OTA_RAM_LENGTH - 0x80
  P2_1_CTRL (rw) : ORIGIN = OTA_RAM_ORIGIN + OTA_RAM_LENGTH - 0x80, LENGTH = 0x80
#else
  RAM (xrw)  : ORIGIN = OTA_RAM_ORIGIN, LENGTH = OTA_RAM_LENGTH
#endif
}

SECTIONS
{
  .isr_vector ORIGIN(FLASH) :
  {
    . = ALIGN(4);
    KEEP(*(.isr_vector))
    . = ALIGN(4);
  } > FLASH

  ASSERT(ADDR(.isr_vector) == ORIGIN(FLASH),
         "Boot vector table is not at the Boot origin")
  ASSERT(SIZEOF(.isr_vector) <= OTA_VECTOR_MAX,
         "Boot vector table exceeds the reserved prefix")

  .text :
  {
    . = ALIGN(4);
    *(.text*)
    *(.rodata*)
    *(.glue_7)
    *(.glue_7t)
    *(.eh_frame)
    KEEP(*(.init))
    KEEP(*(.fini))
    . = ALIGN(4);
    _etext = .;
    _stext = ADDR(.text);
  } > FLASH

  .log_const_data :
  {
    PROVIDE(__start_log_const_data = .);
    KEEP(*(SORT(.log_const_data*)))
    PROVIDE(__stop_log_const_data = .);
  } > FLASH

  .log_backends :
  {
    PROVIDE(__start_log_backends = .);
    KEEP(*(SORT(.log_backends*)))
    PROVIDE(__stop_log_backends = .);
  } > FLASH

  .nrf_balloc :
  {
    PROVIDE(__start_nrf_balloc = .);
    KEEP(*(.nrf_balloc))
    PROVIDE(__stop_nrf_balloc = .);
  } > FLASH

  .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } > FLASH
  .ARM.exidx :
  {
    __exidx_start = .;
    *(.ARM.exidx*)
    __exidx_end = .;
  } > FLASH

  .preinit_array :
  {
    PROVIDE_HIDDEN(__preinit_array_start = .);
    KEEP(*(.preinit_array*))
    PROVIDE_HIDDEN(__preinit_array_end = .);
  } > FLASH

  .init_array :
  {
    PROVIDE_HIDDEN(__init_array_start = .);
    KEEP(*(SORT(.init_array.*)))
    KEEP(*(.init_array*))
    PROVIDE_HIDDEN(__init_array_end = .);
  } > FLASH

  .fini_array :
  {
    PROVIDE_HIDDEN(__fini_array_start = .);
    KEEP(*(SORT(.fini_array.*)))
    KEEP(*(.fini_array*))
    PROVIDE_HIDDEN(__fini_array_end = .);
  } > FLASH

  _sidata = LOADADDR(.data);
  .data :
  {
    . = ALIGN(4);
    _sdata = .;
    *(.data*)
    . = ALIGN(4);
    _edata = .;
  } > RAM AT > FLASH

  .log_dynamic_data :
  {
    PROVIDE(__start_log_dynamic_data = .);
    KEEP(*(SORT(.log_dynamic_data*)))
    PROVIDE(__stop_log_dynamic_data = .);
  } > RAM AT > FLASH

  .log_filter_data :
  {
    PROVIDE(__start_log_filter_data = .);
    KEEP(*(SORT(.log_filter_data*)))
    PROVIDE(__stop_log_filter_data = .);
  } > RAM AT > FLASH

#if defined(P2_1_TEST_ENABLE)
  .p2_1_control (NOLOAD) :
  {
    . = ALIGN(4);
    __p2_1_control_start__ = .;
    . = . + 0x80;
    __p2_1_control_end__ = .;
  } > P2_1_CTRL

  ASSERT(ADDR(.p2_1_control) == OTA_RAM_ORIGIN + OTA_RAM_LENGTH - 0x80,
         "P2-1 control address drifted")
  ASSERT(SIZEOF(.p2_1_control) == 0x80,
         "P2-1 control size drifted")
#endif

  .bss :
  {
    . = ALIGN(4);
    _sbss = .;
    *(.bss*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
  } > RAM

  .stack (NOLOAD) :
  {
    . = ALIGN(8);
    KEEP(*(.stack))
    . = ALIGN(8);
  } > RAM

  .heap (NOLOAD) :
  {
    . = ALIGN(8);
    KEEP(*(.heap))
    . = ALIGN(8);
  } > RAM

  ._user_heap_stack :
  {
    . = ALIGN(8);
    PROVIDE(end = .);
    . = . + _Min_Heap_Size;
    . = . + _Min_Stack_Size;
    . = ALIGN(8);
  } > RAM

  /DISCARD/ : { *(.note.GNU-stack) }
}
