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
    .word _estack
    .word Reset_Handler
    .word NMI_Handler
    .word HardFault_Handler
    .word MemManage_Handler
    .word BusFault_Handler
    .word UsageFault_Handler
    .word 0
    .word 0
    .word 0
    .word 0
    .word SVC_Handler
    .word DebugMon_Handler
    .word 0
    .word PendSV_Handler
    .word SysTick_Handler
    .word WWDT_IRQHandler
    .word PVM_IRQHandler
    .word TAMP_STAMP_IRQHandler
    .word ERTC_WKUP_IRQHandler
    .word FLASH_IRQHandler
    .word CRM_IRQHandler
    .word EXINT0_IRQHandler
    .word EXINT1_IRQHandler
    .word EXINT2_IRQHandler
    .word EXINT3_IRQHandler
    .word EXINT4_IRQHandler
    .word EDMA_Stream1_IRQHandler
    .word EDMA_Stream2_IRQHandler
    .word EDMA_Stream3_IRQHandler
    .word EDMA_Stream4_IRQHandler
    .word EDMA_Stream5_IRQHandler
    .word EDMA_Stream6_IRQHandler
    .word EDMA_Stream7_IRQHandler
    .word ADC1_2_3_IRQHandler
    .word CAN1_TX_IRQHandler
    .word CAN1_RX0_IRQHandler
    .word CAN1_RX1_IRQHandler
    .word CAN1_SE_IRQHandler
    .word EXINT9_5_IRQHandler
    .word TMR1_BRK_TMR9_IRQHandler
    .word TMR1_OVF_TMR10_IRQHandler
    .word TMR1_TRG_HALL_TMR11_IRQHandler
    .word TMR1_CH_IRQHandler
    .word TMR2_GLOBAL_IRQHandler
    .word TMR3_GLOBAL_IRQHandler
    .word TMR4_GLOBAL_IRQHandler
    .word I2C1_EVT_IRQHandler
    .word I2C1_ERR_IRQHandler
    .word I2C2_EVT_IRQHandler
    .word I2C2_ERR_IRQHandler
    .word SPI1_IRQHandler
    .word SPI2_I2S2EXT_IRQHandler
    .word USART1_IRQHandler
    .word USART2_IRQHandler
    .word USART3_IRQHandler
    .word EXINT15_10_IRQHandler
    .word ERTCAlarm_IRQHandler
    .word OTGFS1_WKUP_IRQHandler
    .word TMR8_BRK_TMR12_IRQHandler
    .word TMR8_OVF_TMR13_IRQHandler
    .word TMR8_TRG_HALL_TMR14_IRQHandler
    .word TMR8_CH_IRQHandler
    .word EDMA_Stream8_IRQHandler
    .word XMC_IRQHandler
    .word SDIO1_IRQHandler
    .word TMR5_GLOBAL_IRQHandler
    .word SPI3_I2S3EXT_IRQHandler
    .word UART4_IRQHandler
    .word UART5_IRQHandler
    .word TMR6_DAC_GLOBAL_IRQHandler
    .word TMR7_GLOBAL_IRQHandler
    .word DMA1_Channel1_IRQHandler
    .word DMA1_Channel2_IRQHandler
    .word DMA1_Channel3_IRQHandler
    .word DMA1_Channel4_IRQHandler
    .word DMA1_Channel5_IRQHandler
    .word EMAC_IRQHandler
    .word EMAC_WKUP_IRQHandler
    .word CAN2_TX_IRQHandler
    .word CAN2_RX0_IRQHandler
    .word CAN2_RX1_IRQHandler
    .word CAN2_SE_IRQHandler
    .word OTGFS1_IRQHandler
    .word DMA1_Channel6_IRQHandler
    .word DMA1_Channel7_IRQHandler
    .word 0
    .word USART6_IRQHandler
    .word I2C3_EVT_IRQHandler
    .word I2C3_ERR_IRQHandler
    .word 0
    .word 0
    .word OTGFS2_WKUP_IRQHandler
    .word OTGFS2_IRQHandler
    .word DVP_IRQHandler
    .word 0
    .word 0
    .word FPU_IRQHandler
    .word UART7_IRQHandler
    .word UART8_IRQHandler
    .word SPI4_IRQHandler
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word QSPI2_IRQHandler
    .word QSPI1_IRQHandler
    .word 0
    .word DMAMUX_IRQHandler
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word SDIO2_IRQHandler
    .word ACC_IRQHandler
    .word TMR20_BRK_IRQHandler
    .word TMR20_OVF_IRQHandler
    .word TMR20_TRG_HALL_IRQHandler
    .word TMR20_CH_IRQHandler
    .word DMA2_Channel1_IRQHandler
    .word DMA2_Channel2_IRQHandler
    .word DMA2_Channel3_IRQHandler
    .word DMA2_Channel4_IRQHandler
    .word DMA2_Channel5_IRQHandler
    .word DMA2_Channel6_IRQHandler
    .word DMA2_Channel7_IRQHandler
__Vectors_End:
.equ __Vectors_Size, __Vectors_End - __Vectors

.section .text.Reset_Handler,"ax",%progbits
.type Reset_Handler, %function
Reset_Handler:
    ldr r0, =_estack
    mov sp, r0
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
