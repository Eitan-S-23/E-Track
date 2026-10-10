/* Auto-generated GNU startup file converted from a Keil ARMASM startup file. */
.syntax unified
.cpu cortex-m4
.thumb

.global __Vectors
.global g_pfnVectors
.global __Vectors_End
.global __Vectors_Size
.global Reset_Handler
.extern SystemInit
.extern __libc_init_array
.extern main
.extern extend_sram_512k

.section .isr_vector,"a",%progbits
.type __Vectors, %object
__Vectors:
g_pfnVectors:
#define P34_PRIMARY_TABLE 1
#include "p34_vector_entries.inc"
#undef P34_PRIMARY_TABLE
__Vectors_End:
.equ __Vectors_Size, __Vectors_End - __Vectors

.section .text.Reset_Handler,"ax",%progbits
.type Reset_Handler, %function
Reset_Handler:
    ldr r0, =_estack
    mov sp, r0
    ldr r1, =__StackLimit
    ldr r2, =__StackTop
    ldr r3, =0xA5A5A5A5
.Lfill_ota_stack:
    cmp r1, r2
    bcs .Lfill_ota_guard
    str r3, [r1]
    adds r1, r1, #4
    b .Lfill_ota_stack
.Lfill_ota_guard:
    ldr r1, =__StackGuardStart
    ldr r2, =__StackGuardEnd
    ldr r3, =0x5A5A5A5A
.Lfill_ota_guard_loop:
    cmp r1, r2
    bcs .Lafter_ota_guards
    str r3, [r1]
    adds r1, r1, #4
    b .Lfill_ota_guard_loop
.Lafter_ota_guards:
    bl extend_sram_512k
    bl SystemInit
    ldr r0, =_sidata
    ldr r1, =_sdata
    ldr r2, =_edata
.Lcopy_data:
    cmp r1, r2
    bcs .Lzero_bss
    ldr r3, [r0]
    str r3, [r1]
    adds r0, r0, #4
    adds r1, r1, #4
    b .Lcopy_data
.Lzero_bss:
    ldr r1, =_sbss
    ldr r2, =_ebss
    movs r3, #0
.Lfill_bss:
    cmp r1, r2
    bcs .Linit_runtime
    str r3, [r1]
    adds r1, r1, #4
    b .Lfill_bss
.Linit_runtime:
    bl __libc_init_array
    bl main
.Lhang:
    b .Lhang
.size Reset_Handler, .-Reset_Handler

.section .text.Default_Handler,"ax",%progbits
.type Default_Handler, %function
Default_Handler:
    b .
.size Default_Handler, .-Default_Handler

    .weak NMI_Handler
    .thumb_set NMI_Handler, Default_Handler
    .weak HardFault_Handler
    .thumb_set HardFault_Handler, Default_Handler
    .weak MemManage_Handler
    .thumb_set MemManage_Handler, Default_Handler
    .weak BusFault_Handler
    .thumb_set BusFault_Handler, Default_Handler
    .weak UsageFault_Handler
    .thumb_set UsageFault_Handler, Default_Handler
    .weak SVC_Handler
    .thumb_set SVC_Handler, Default_Handler
    .weak DebugMon_Handler
    .thumb_set DebugMon_Handler, Default_Handler
    .weak PendSV_Handler
    .thumb_set PendSV_Handler, Default_Handler
    .weak SysTick_Handler
    .thumb_set SysTick_Handler, Default_Handler
    .weak WWDT_IRQHandler
    .thumb_set WWDT_IRQHandler, Default_Handler
    .weak PVM_IRQHandler
    .thumb_set PVM_IRQHandler, Default_Handler
    .weak TAMP_STAMP_IRQHandler
    .thumb_set TAMP_STAMP_IRQHandler, Default_Handler
    .weak ERTC_WKUP_IRQHandler
    .thumb_set ERTC_WKUP_IRQHandler, Default_Handler
    .weak FLASH_IRQHandler
    .thumb_set FLASH_IRQHandler, Default_Handler
    .weak CRM_IRQHandler
    .thumb_set CRM_IRQHandler, Default_Handler
    .weak EXINT0_IRQHandler
    .thumb_set EXINT0_IRQHandler, Default_Handler
    .weak EXINT1_IRQHandler
    .thumb_set EXINT1_IRQHandler, Default_Handler
    .weak EXINT2_IRQHandler
    .thumb_set EXINT2_IRQHandler, Default_Handler
    .weak EXINT3_IRQHandler
    .thumb_set EXINT3_IRQHandler, Default_Handler
    .weak EXINT4_IRQHandler
    .thumb_set EXINT4_IRQHandler, Default_Handler
    .weak EDMA_Stream1_IRQHandler
    .thumb_set EDMA_Stream1_IRQHandler, Default_Handler
    .weak EDMA_Stream2_IRQHandler
    .thumb_set EDMA_Stream2_IRQHandler, Default_Handler
    .weak EDMA_Stream3_IRQHandler
    .thumb_set EDMA_Stream3_IRQHandler, Default_Handler
    .weak EDMA_Stream4_IRQHandler
    .thumb_set EDMA_Stream4_IRQHandler, Default_Handler
    .weak EDMA_Stream5_IRQHandler
    .thumb_set EDMA_Stream5_IRQHandler, Default_Handler
    .weak EDMA_Stream6_IRQHandler
    .thumb_set EDMA_Stream6_IRQHandler, Default_Handler
    .weak EDMA_Stream7_IRQHandler
    .thumb_set EDMA_Stream7_IRQHandler, Default_Handler
    .weak ADC1_2_3_IRQHandler
    .thumb_set ADC1_2_3_IRQHandler, Default_Handler
    .weak CAN1_TX_IRQHandler
    .thumb_set CAN1_TX_IRQHandler, Default_Handler
    .weak CAN1_RX0_IRQHandler
    .thumb_set CAN1_RX0_IRQHandler, Default_Handler
    .weak CAN1_RX1_IRQHandler
    .thumb_set CAN1_RX1_IRQHandler, Default_Handler
    .weak CAN1_SE_IRQHandler
    .thumb_set CAN1_SE_IRQHandler, Default_Handler
    .weak EXINT9_5_IRQHandler
    .thumb_set EXINT9_5_IRQHandler, Default_Handler
    .weak TMR1_BRK_TMR9_IRQHandler
    .thumb_set TMR1_BRK_TMR9_IRQHandler, Default_Handler
    .weak TMR1_OVF_TMR10_IRQHandler
    .thumb_set TMR1_OVF_TMR10_IRQHandler, Default_Handler
    .weak TMR1_TRG_HALL_TMR11_IRQHandler
    .thumb_set TMR1_TRG_HALL_TMR11_IRQHandler, Default_Handler
    .weak TMR1_CH_IRQHandler
    .thumb_set TMR1_CH_IRQHandler, Default_Handler
    .weak TMR2_GLOBAL_IRQHandler
    .thumb_set TMR2_GLOBAL_IRQHandler, Default_Handler
    .weak TMR3_GLOBAL_IRQHandler
    .thumb_set TMR3_GLOBAL_IRQHandler, Default_Handler
    .weak TMR4_GLOBAL_IRQHandler
    .thumb_set TMR4_GLOBAL_IRQHandler, Default_Handler
    .weak I2C1_EVT_IRQHandler
    .thumb_set I2C1_EVT_IRQHandler, Default_Handler
    .weak I2C1_ERR_IRQHandler
    .thumb_set I2C1_ERR_IRQHandler, Default_Handler
    .weak I2C2_EVT_IRQHandler
    .thumb_set I2C2_EVT_IRQHandler, Default_Handler
    .weak I2C2_ERR_IRQHandler
    .thumb_set I2C2_ERR_IRQHandler, Default_Handler
    .weak SPI1_IRQHandler
    .thumb_set SPI1_IRQHandler, Default_Handler
    .weak SPI2_I2S2EXT_IRQHandler
    .thumb_set SPI2_I2S2EXT_IRQHandler, Default_Handler
    .weak USART1_IRQHandler
    .thumb_set USART1_IRQHandler, Default_Handler
    .weak USART2_IRQHandler
    .thumb_set USART2_IRQHandler, Default_Handler
    .weak USART3_IRQHandler
    .thumb_set USART3_IRQHandler, Default_Handler
    .weak EXINT15_10_IRQHandler
    .thumb_set EXINT15_10_IRQHandler, Default_Handler
    .weak ERTCAlarm_IRQHandler
    .thumb_set ERTCAlarm_IRQHandler, Default_Handler
    .weak OTGFS1_WKUP_IRQHandler
    .thumb_set OTGFS1_WKUP_IRQHandler, Default_Handler
    .weak TMR8_BRK_TMR12_IRQHandler
    .thumb_set TMR8_BRK_TMR12_IRQHandler, Default_Handler
    .weak TMR8_OVF_TMR13_IRQHandler
    .thumb_set TMR8_OVF_TMR13_IRQHandler, Default_Handler
    .weak TMR8_TRG_HALL_TMR14_IRQHandler
    .thumb_set TMR8_TRG_HALL_TMR14_IRQHandler, Default_Handler
    .weak TMR8_CH_IRQHandler
    .thumb_set TMR8_CH_IRQHandler, Default_Handler
    .weak EDMA_Stream8_IRQHandler
    .thumb_set EDMA_Stream8_IRQHandler, Default_Handler
    .weak XMC_IRQHandler
    .thumb_set XMC_IRQHandler, Default_Handler
    .weak SDIO1_IRQHandler
    .thumb_set SDIO1_IRQHandler, Default_Handler
    .weak TMR5_GLOBAL_IRQHandler
    .thumb_set TMR5_GLOBAL_IRQHandler, Default_Handler
    .weak SPI3_I2S3EXT_IRQHandler
    .thumb_set SPI3_I2S3EXT_IRQHandler, Default_Handler
    .weak UART4_IRQHandler
    .thumb_set UART4_IRQHandler, Default_Handler
    .weak UART5_IRQHandler
    .thumb_set UART5_IRQHandler, Default_Handler
    .weak TMR6_DAC_GLOBAL_IRQHandler
    .thumb_set TMR6_DAC_GLOBAL_IRQHandler, Default_Handler
    .weak TMR7_GLOBAL_IRQHandler
    .thumb_set TMR7_GLOBAL_IRQHandler, Default_Handler
    .weak DMA1_Channel1_IRQHandler
    .thumb_set DMA1_Channel1_IRQHandler, Default_Handler
    .weak DMA1_Channel2_IRQHandler
    .thumb_set DMA1_Channel2_IRQHandler, Default_Handler
    .weak DMA1_Channel3_IRQHandler
    .thumb_set DMA1_Channel3_IRQHandler, Default_Handler
    .weak DMA1_Channel4_IRQHandler
    .thumb_set DMA1_Channel4_IRQHandler, Default_Handler
    .weak DMA1_Channel5_IRQHandler
    .thumb_set DMA1_Channel5_IRQHandler, Default_Handler
    .weak EMAC_IRQHandler
    .thumb_set EMAC_IRQHandler, Default_Handler
    .weak EMAC_WKUP_IRQHandler
    .thumb_set EMAC_WKUP_IRQHandler, Default_Handler
    .weak CAN2_TX_IRQHandler
    .thumb_set CAN2_TX_IRQHandler, Default_Handler
    .weak CAN2_RX0_IRQHandler
    .thumb_set CAN2_RX0_IRQHandler, Default_Handler
    .weak CAN2_RX1_IRQHandler
    .thumb_set CAN2_RX1_IRQHandler, Default_Handler
    .weak CAN2_SE_IRQHandler
    .thumb_set CAN2_SE_IRQHandler, Default_Handler
    .weak OTGFS1_IRQHandler
    .thumb_set OTGFS1_IRQHandler, Default_Handler
    .weak DMA1_Channel6_IRQHandler
    .thumb_set DMA1_Channel6_IRQHandler, Default_Handler
    .weak DMA1_Channel7_IRQHandler
    .thumb_set DMA1_Channel7_IRQHandler, Default_Handler
    .weak USART6_IRQHandler
    .thumb_set USART6_IRQHandler, Default_Handler
    .weak I2C3_EVT_IRQHandler
    .thumb_set I2C3_EVT_IRQHandler, Default_Handler
    .weak I2C3_ERR_IRQHandler
    .thumb_set I2C3_ERR_IRQHandler, Default_Handler
    .weak OTGFS2_WKUP_IRQHandler
    .thumb_set OTGFS2_WKUP_IRQHandler, Default_Handler
    .weak OTGFS2_IRQHandler
    .thumb_set OTGFS2_IRQHandler, Default_Handler
    .weak DVP_IRQHandler
    .thumb_set DVP_IRQHandler, Default_Handler
    .weak FPU_IRQHandler
    .thumb_set FPU_IRQHandler, Default_Handler
    .weak UART7_IRQHandler
    .thumb_set UART7_IRQHandler, Default_Handler
    .weak UART8_IRQHandler
    .thumb_set UART8_IRQHandler, Default_Handler
    .weak SPI4_IRQHandler
    .thumb_set SPI4_IRQHandler, Default_Handler
    .weak QSPI2_IRQHandler
    .thumb_set QSPI2_IRQHandler, Default_Handler
    .weak QSPI1_IRQHandler
    .thumb_set QSPI1_IRQHandler, Default_Handler
    .weak DMAMUX_IRQHandler
    .thumb_set DMAMUX_IRQHandler, Default_Handler
    .weak SDIO2_IRQHandler
    .thumb_set SDIO2_IRQHandler, Default_Handler
    .weak ACC_IRQHandler
    .thumb_set ACC_IRQHandler, Default_Handler
    .weak TMR20_BRK_IRQHandler
    .thumb_set TMR20_BRK_IRQHandler, Default_Handler
    .weak TMR20_OVF_IRQHandler
    .thumb_set TMR20_OVF_IRQHandler, Default_Handler
    .weak TMR20_TRG_HALL_IRQHandler
    .thumb_set TMR20_TRG_HALL_IRQHandler, Default_Handler
    .weak TMR20_CH_IRQHandler
    .thumb_set TMR20_CH_IRQHandler, Default_Handler
    .weak DMA2_Channel1_IRQHandler
    .thumb_set DMA2_Channel1_IRQHandler, Default_Handler
    .weak DMA2_Channel2_IRQHandler
    .thumb_set DMA2_Channel2_IRQHandler, Default_Handler
    .weak DMA2_Channel3_IRQHandler
    .thumb_set DMA2_Channel3_IRQHandler, Default_Handler
    .weak DMA2_Channel4_IRQHandler
    .thumb_set DMA2_Channel4_IRQHandler, Default_Handler
    .weak DMA2_Channel5_IRQHandler
    .thumb_set DMA2_Channel5_IRQHandler, Default_Handler
    .weak DMA2_Channel6_IRQHandler
    .thumb_set DMA2_Channel6_IRQHandler, Default_Handler
    .weak DMA2_Channel7_IRQHandler
    .thumb_set DMA2_Channel7_IRQHandler, Default_Handler

#if defined(P34_EARLY_FAULT_VECTORS)
.section .p34_runtime_vectors,"a",%progbits
.balign 1024
.global p34_runtime_vectors
.type p34_runtime_vectors, %object
p34_runtime_vectors:
#include "p34_vector_entries.inc"
.size p34_runtime_vectors, .-p34_runtime_vectors
.section .text.p34_early_exception,"ax",%progbits
.global p34_early_exception
.type p34_early_exception, %function
.thumb_func
p34_early_exception:
    cpsid i
1:  b 1b
.size p34_early_exception, .-p34_early_exception
#endif
