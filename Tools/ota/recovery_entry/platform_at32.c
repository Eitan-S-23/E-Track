#include "supervisor.h"
#include "at32f435_437.h"

void re_platform_report_barrier(void) { __DSB(); }

int re_platform_snapshot(re_hw_snapshot *h)
{
    static dma_channel_type *const channels[]={DMA1_CHANNEL1,DMA1_CHANNEL2,DMA1_CHANNEL3,
        DMA1_CHANNEL4,DMA1_CHANNEL5,DMA1_CHANNEL6,DMA1_CHANNEL7,DMA2_CHANNEL1,DMA2_CHANNEL2,
        DMA2_CHANNEL3,DMA2_CHANNEL4,DMA2_CHANNEL5,DMA2_CHANNEL6,DMA2_CHANNEL7};
    static edma_stream_type *const streams[]={EDMA_STREAM1,EDMA_STREAM2,EDMA_STREAM3,
        EDMA_STREAM4,EDMA_STREAM5,EDMA_STREAM6,EDMA_STREAM7,EDMA_STREAM8};
    unsigned i;
    if (!h) return -1;
    h->clock[0]=CRM->ctrl; h->clock[1]=CRM->pllcfg; h->clock[2]=CRM->cfg;
    h->clock[3]=CRM->misc1; h->clock[4]=CRM->misc2;
    h->ticks=DWT->CYCCNT;
    h->trace_enabled=CoreDebug->DEMCR & CoreDebug_DEMCR_TRCENA_Msk;
    h->counter_enabled=DWT->CTRL & DWT_CTRL_CYCCNTENA_Msk;
    h->ipsr=__get_IPSR(); h->control=__get_CONTROL(); h->primask=__get_PRIMASK();
    h->msp=__get_MSP(); h->vtor=SCB->VTOR; h->fpccr=FPU->FPCCR;
    h->dma_active=0;
    for (i=0;i<sizeof(channels)/sizeof(channels[0]);++i) h->dma_active|=channels[i]->ctrl & 1u;
    for (i=0;i<sizeof(streams)/sizeof(streams[0]);++i) h->dma_active|=streams[i]->ctrl & 1u;
    h->qspi_dma=QSPI1->ctrl2 & 1u;
    __DSB();
    /* Detect clock reconfiguration during this non-atomic snapshot. It cannot
       detect change-and-restore or prove a previously active DMA drained. */
    if (h->clock[0]!=CRM->ctrl || h->clock[1]!=CRM->pllcfg || h->clock[2]!=CRM->cfg ||
        h->clock[3]!=CRM->misc1 || h->clock[4]!=CRM->misc2) return -1;
    return 0;
}
int re_platform_read32(uint32_t off, uint32_t *v)
{
    if (!v) return -1;
    switch (off) {
    case 0x10: *v=QSPI1->ctrl; return 0;
    case 0x18: *v=QSPI1->fifosts; return 0;
    case 0x24: *v=QSPI1->cmdsts; return 0;
    default: return -1;
    }
}
int re_platform_write32(uint32_t off, uint32_t value)
{
    switch (off) {
    case 0x00: if (value) return -1; QSPI1->cmd_w0=0; break;
    case 0x04: if (value!=0x01000000u) return -1; QSPI1->cmd_w1=0x01000000u; break;
    case 0x08: if (value!=1u) return -1; QSPI1->cmd_w2=1; break;
    case 0x0c: if (value!=0x05000000u) return -1; QSPI1->cmd_w3=0x05000000u; break;
    default: return -1;
    }
    __DSB();
    return 0;
}
int re_platform_read8(uint32_t off, uint8_t *v)
{
    if (!v || off!=0x100u) return -1;
    *v=QSPI1->dt_u8;
    return 0;
}
