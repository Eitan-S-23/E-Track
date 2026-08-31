/* Minimal input sections used to exercise the production App linker script. */
.syntax unified
.thumb

.section .isr_vector, "a", %progbits
.word Reset_Handler

.section .fw_header, "a", %progbits
.space 96

.section .text.Reset_Handler, "ax", %progbits
.global Reset_Handler
.type Reset_Handler, %function
Reset_Handler:
    bx lr
.size Reset_Handler, .-Reset_Handler

.section .ota_vtor_noinit, "aw", %nobits
.space 8

.section .sram_ext, "aw", %nobits
.space 0

.section .ota_overlay, "aw", %nobits
.space 0xA000
