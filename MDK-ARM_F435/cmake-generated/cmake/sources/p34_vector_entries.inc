    .word _estack
    .word Reset_Handler
#if defined(P34_PRIMARY_TABLE) && defined(P34_EARLY_FAULT_VECTORS)
    .word p34_early_exception
#else
    .word NMI_Handler
#endif
#if defined(P34_PRIMARY_TABLE) && defined(P34_EARLY_FAULT_VECTORS)
    .word p34_early_exception
#else
    .word HardFault_Handler
#endif
#if defined(P34_PRIMARY_TABLE) && defined(P34_EARLY_FAULT_VECTORS)
    .word p34_early_exception
#else
    .word MemManage_Handler
#endif
#if defined(P34_PRIMARY_TABLE) && defined(P34_EARLY_FAULT_VECTORS)
    .word p34_early_exception
#else
    .word BusFault_Handler
#endif
#if defined(P34_PRIMARY_TABLE) && defined(P34_EARLY_FAULT_VECTORS)
    .word p34_early_exception
#else
    .word UsageFault_Handler
#endif
    .word 0
    .word 0
    .word 0
    .word 0
#if defined(P34_PRIMARY_TABLE) && defined(P34_EARLY_FAULT_VECTORS)
    .word p34_early_exception
#else
    .word SVC_Handler
#endif
#if defined(P34_PRIMARY_TABLE) && defined(P34_EARLY_FAULT_VECTORS)
    .word p34_early_exception
#else
    .word DebugMon_Handler
#endif
    .word 0
#if defined(P34_PRIMARY_TABLE) && defined(P34_EARLY_FAULT_VECTORS)
    .word p34_early_exception
#else
    .word PendSV_Handler
#endif
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
