#include "ota_layout.h"

ENTRY(Reset_Handler)

_estack = ORIGIN(RAM) + LENGTH(RAM);
_sstack = ORIGIN(RAM);
_Min_Heap_Size = 0x200;
_Min_Stack_Size = 0x1000;

MEMORY
{
  FLASH (rx)     : ORIGIN = OTA_APP_ORIGIN, LENGTH = OTA_APP_LENGTH
#if defined(P1_6_TEST_ENABLE)
  RAM (xrw)      : ORIGIN = OTA_RAM_ORIGIN, LENGTH = OTA_RAM_LENGTH - 0x200
  P1_6_CTRL (rw) : ORIGIN = OTA_RAM_ORIGIN + OTA_RAM_LENGTH - 0x200, LENGTH = 0x200
#elif defined(P2_2_TEST_ENABLE)
  RAM (xrw)      : ORIGIN = OTA_RAM_ORIGIN, LENGTH = OTA_RAM_LENGTH - 0x800
  P2_2_CTRL (rw) : ORIGIN = OTA_RAM_ORIGIN + OTA_RAM_LENGTH - 0x800, LENGTH = 0x800
#elif defined(P2_1_TEST_ENABLE)
  RAM (xrw)      : ORIGIN = OTA_RAM_ORIGIN, LENGTH = OTA_RAM_LENGTH - 0x80
  P2_1_CTRL (rw) : ORIGIN = OTA_RAM_ORIGIN + OTA_RAM_LENGTH - 0x80, LENGTH = 0x80
#else
  RAM (xrw)      : ORIGIN = OTA_RAM_ORIGIN, LENGTH = OTA_RAM_LENGTH
#endif
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

#if defined(P1_6_TEST_ENABLE)
  .p1_6_control (NOLOAD) :
  {
    . = ALIGN(4);
    __p1_6_control_start__ = .;
    . = . + 0x200;
    __p1_6_control_end__ = .;
  } > P1_6_CTRL

  ASSERT(ADDR(.p1_6_control) == OTA_RAM_ORIGIN + OTA_RAM_LENGTH - 0x200,
         "P1-6 control address drifted")
  ASSERT(SIZEOF(.p1_6_control) == 0x200,
         "P1-6 control size drifted")
#elif defined(P2_2_TEST_ENABLE)
  .p2_2_control (NOLOAD) :
  {
    . = ALIGN(4);
    __p2_2_control_start__ = .;
    . = . + 0x800;
    __p2_2_control_end__ = .;
  } > P2_2_CTRL

  ASSERT(ADDR(.p2_2_control) == OTA_RAM_ORIGIN + OTA_RAM_LENGTH - 0x800,
         "P2-2 control address drifted")
  ASSERT(SIZEOF(.p2_2_control) == 0x800,
         "P2-2 control size drifted")
#elif defined(P2_1_TEST_ENABLE)
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

  OVERLAY ORIGIN(RW_IRAM2) : NOCROSSREFS
  {
    .sram_ext
    {
      . = ALIGN(8);
      *(.sram_ext)
      *(.sram_ext.*)
      . = ALIGN(8);
    }

    .ota_overlay
    {
      . = ALIGN(8);
      __ota_overlay_start__ = .;
      KEEP(*(.ota_overlay))
      KEEP(*(.ota_overlay.*))
      . = ALIGN(8);
      __ota_overlay_end__ = .;
    }
  } > RW_IRAM2

  ASSERT(ADDR(.sram_ext) == OTA_OVERLAY_ORIGIN,
         "LiveMap overlay address drifted")
  ASSERT(SIZEOF(.sram_ext) <= LENGTH(RW_IRAM2),
         "SRAM overlay exceeds the contracted region")
  ASSERT(ADDR(.ota_overlay) == OTA_OVERLAY_ORIGIN,
         "OTA workspace address drifted")
  ASSERT(SIZEOF(.ota_overlay) == OTA_OVERLAY_WORKSPACE_LENGTH,
         "OTA workspace size drifted")
#if defined(P1_6_TEST_ENABLE)
  ASSERT(ORIGIN(RAM) + LENGTH(RAM) == ORIGIN(P1_6_CTRL),
         "Main RAM and P1-6 control region are not contiguous")
  ASSERT(ORIGIN(P1_6_CTRL) + LENGTH(P1_6_CTRL) == ORIGIN(RW_IRAM2),
         "P1-6 control and overlay regions are not contiguous")
#elif defined(P2_2_TEST_ENABLE)
  ASSERT(ORIGIN(RAM) + LENGTH(RAM) == ORIGIN(P2_2_CTRL),
         "Main RAM and P2-2 control region are not contiguous")
  ASSERT(ORIGIN(P2_2_CTRL) + LENGTH(P2_2_CTRL) == ORIGIN(RW_IRAM2),
         "P2-2 control and overlay regions are not contiguous")
#elif defined(P2_1_TEST_ENABLE)
  ASSERT(ORIGIN(RAM) + LENGTH(RAM) == ORIGIN(P2_1_CTRL),
         "Main RAM and P2-1 control region are not contiguous")
  ASSERT(ORIGIN(P2_1_CTRL) + LENGTH(P2_1_CTRL) == ORIGIN(RW_IRAM2),
         "P2-1 control and overlay regions are not contiguous")
#else
  ASSERT(ORIGIN(RAM) + LENGTH(RAM) == ORIGIN(RW_IRAM2),
         "Main RAM and overlay regions are not contiguous")
#endif

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
