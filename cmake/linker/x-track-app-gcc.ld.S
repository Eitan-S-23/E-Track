#include "ota_layout.h"

ENTRY(Reset_Handler)

_estack = ORIGIN(RAM) + LENGTH(RAM);
_sstack = ORIGIN(RAM);
_Min_Heap_Size = 0x200;
_Min_Stack_Size = 0x1000;

MEMORY
{
  FLASH (rx)     : ORIGIN = OTA_APP_ORIGIN, LENGTH = OTA_APP_LENGTH
  RAM (xrw)      : ORIGIN = OTA_RAM_ORIGIN, LENGTH = OTA_RAM_LENGTH
  RW_IRAM2 (xrw) : ORIGIN = OTA_OVERLAY_ORIGIN, LENGTH = OTA_OVERLAY_LENGTH
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
         "App vector table is not at the App origin")
  ASSERT(SIZEOF(.isr_vector) <= OTA_VECTOR_MAX,
         "App vector table exceeds the reserved prefix")

  .fw_header ORIGIN(FLASH) + OTA_FW_HEADER_OFFSET :
  {
    . = ALIGN(4);
    __fw_header_start__ = .;
    KEEP(*(.fw_header))
    KEEP(*(.fw_header.*))
    . = ALIGN(4);
    __fw_header_end__ = .;
  } > FLASH

  ASSERT(ADDR(.fw_header) == ORIGIN(FLASH) + OTA_FW_HEADER_OFFSET,
         "Firmware header is not at the contracted offset")
  ASSERT(SIZEOF(.fw_header) == OTA_FW_HEADER_SIZE,
         "Firmware header placeholder must be exactly 96 bytes")

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

  .bss :
  {
    . = ALIGN(4);
    _sbss = .;
    *(.bss*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
  } > RAM

  .ota_vtor_noinit (NOLOAD) :
  {
    . = ALIGN(4);
    __ota_vtor_noinit_start__ = .;
    KEEP(*(.ota_vtor_noinit))
    KEEP(*(.ota_vtor_noinit.*))
    . = ALIGN(4);
    __ota_vtor_noinit_end__ = .;
  } > RAM

  ASSERT(SIZEOF(.ota_vtor_noinit) >= OTA_VTOR_EVIDENCE_SIZE,
         "VTOR evidence section must hold both 32-bit markers")

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

  .sram_ext (NOLOAD) :
  {
    . = ALIGN(4);
    *(.sram_ext)
    *(.sram_ext.*)
    . = ALIGN(4);
  } > RW_IRAM2

  ASSERT(SIZEOF(.sram_ext) <= LENGTH(RW_IRAM2),
         "SRAM overlay exceeds the contracted region")
  ASSERT(ORIGIN(RAM) + LENGTH(RAM) == ORIGIN(RW_IRAM2),
         "Main RAM and overlay regions are not contiguous")

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
