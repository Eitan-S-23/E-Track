#include "HAL.h"
#include "App/Version.h"
#include "cm_backtrace/cm_backtrace.h"

static volatile bool s_faultHandleReady = false;

#if CONFIG_HARDFAULT_AUTO_REBOOT
static void Delay(uint32_t ms)
{
    volatile uint32_t i = F_CPU / 1000 * ms / 5;
    while(i--);
}

static void Reboot()
{
    while(digitalRead(CONFIG_ENCODER_PUSH_PIN) == HIGH)
    {
        Delay(1000);
    }
    NVIC_SystemReset();
}
#endif

void HAL::FaultHandle_Init()
{
    cm_backtrace_init(
        VERSION_FIRMWARE_NAME,
        VERSION_HARDWARE,
        VERSION_SOFTWARE " " __DATE__
    );
    s_faultHandleReady = true;
}

static void FaultWrite(const char* str)
{
#if CONFIG_DEBUG_RTT_ENABLE
    SEGGER_RTT_WriteString(0, str);
#endif

#if CONFIG_DEBUG_SERIAL_ENABLE
    if(s_faultHandleReady)
    {
        CONFIG_DEBUG_SERIAL.print(str);
    }
#endif
}

static void FaultPrintf(const char *__restrict format, ...)
{
    char printf_buff[256];

    va_list args;
    va_start(args, format);
    int ret_status = vsnprintf(printf_buff, sizeof(printf_buff), format, args);
    va_end(args);

    (void)ret_status;
    FaultWrite(printf_buff);
}

void cmb_printf(const char *__restrict __format, ...)
{
    char printf_buff[256];

    va_list args;
    va_start(args, __format);
    int ret_status = vsnprintf(printf_buff, sizeof(printf_buff), __format, args);
    va_end(args);

    (void)ret_status;
    FaultWrite(printf_buff);
}

extern "C"
{
    /*
    void vApplicationStackOverflowHook(TaskHandle_t xTask, char* pcTaskName)
    {
        char strBuf[configMAX_TASK_NAME_LEN + 1];
        snprintf(strBuf, sizeof(strBuf), "stack overflow\n < %s >", pcTaskName);
        DisplayError_SetReports(strBuf);
        Reboot();
    }
    
    void vApplicationMallocFailedHook()
    {
        DisplayError_SetReports("malloc failed");
        Reboot();
    }
    */

    typedef struct
    {
        uint32_t r0;
        uint32_t r1;
        uint32_t r2;
        uint32_t r3;
        uint32_t r12;
        uint32_t lr;
        uint32_t pc;
        uint32_t xpsr;
    } HardFaultStackFrame_t;

    static bool IsValidRamFrame(uint32_t sp)
    {
        const uint32_t ramStart = 0x20000000;
        const uint32_t ramEnd = 0x20060000;
        const uint32_t stackingErrorMask = (1UL << 4) | (1UL << 12);

        return ((SCB->CFSR & stackingErrorMask) == 0)
            && ((sp & 0x3) == 0)
            && (sp >= ramStart)
            && (sp <= (ramEnd - sizeof(HardFaultStackFrame_t)));
    }

    static void FaultPrintFlag(uint32_t value, uint32_t mask, const char* name, bool* hasFlag)
    {
        if((value & mask) != 0)
        {
            FaultPrintf(" %s", name);
            *hasFlag = true;
        }
    }

    static void FaultPrintCfsr(uint32_t cfsr)
    {
        bool hasFlag = false;

        FaultPrintf("CFSR flags:");
        FaultPrintFlag(cfsr, (1UL << 0), "IACCVIOL", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 1), "DACCVIOL", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 3), "MUNSTKERR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 4), "MSTKERR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 5), "MLSPERR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 7), "MMARVALID", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 8), "IBUSERR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 9), "PRECISERR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 10), "IMPRECISERR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 11), "UNSTKERR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 12), "STKERR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 13), "LSPERR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 15), "BFARVALID", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 16), "UNDEFINSTR", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 17), "INVSTATE", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 18), "INVPC", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 19), "NOCP", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 24), "UNALIGNED", &hasFlag);
        FaultPrintFlag(cfsr, (1UL << 25), "DIVBYZERO", &hasFlag);

        if(!hasFlag)
        {
            FaultPrintf(" none");
        }
        FaultPrintf("\r\n");
    }

    static bool FaultPrintResetFlag(const char* name, uint32_t flag)
    {
        if(crm_flag_get(flag) != RESET)
        {
            FaultPrintf(" %s", name);
            return true;
        }

        return false;
    }

    static void FaultPrintResetReason()
    {
        bool hasFlag = false;

        FaultPrintf("Reset flags:");
        hasFlag |= FaultPrintResetFlag("NRST", CRM_NRST_RESET_FLAG);
        hasFlag |= FaultPrintResetFlag("POR", CRM_POR_RESET_FLAG);
        hasFlag |= FaultPrintResetFlag("SW", CRM_SW_RESET_FLAG);
        hasFlag |= FaultPrintResetFlag("WDT", CRM_WDT_RESET_FLAG);
        hasFlag |= FaultPrintResetFlag("WWDT", CRM_WWDT_RESET_FLAG);
        hasFlag |= FaultPrintResetFlag("LOWPWR", CRM_LOWPOWER_RESET_FLAG);

        if(!hasFlag)
        {
            FaultPrintf(" none");
        }
        FaultPrintf("\r\n");
    }

    void vApplicationHardFaultDump(uint32_t excReturn, uint32_t faultSp)
    {
        SEGGER_RTT_Init();
        SEGGER_RTT_SetFlagsUpBuffer(0, SEGGER_RTT_MODE_NO_BLOCK_TRIM);

        FaultPrintf("\r\n*** HardFault ***\r\n");
        FaultPrintf("Build: %s %s\r\n", __DATE__, __TIME__);
#if CONFIG_DEBUG_RTT_ENABLE
        FaultPrintf("RTT_CB=0x%08x\r\n", (uint32_t)&_SEGGER_RTT);
#endif
        FaultPrintResetReason();
        FaultPrintf(
            "EXC_RETURN=0x%08x SP=0x%08x STACK=%s\r\n",
            excReturn,
            faultSp,
            (excReturn & (1UL << 2)) ? "PSP" : "MSP"
        );

        if(IsValidRamFrame(faultSp))
        {
            const HardFaultStackFrame_t* frame = (const HardFaultStackFrame_t*)faultSp;

            FaultPrintf(
                "R0=0x%08x R1=0x%08x R2=0x%08x R3=0x%08x\r\n",
                frame->r0,
                frame->r1,
                frame->r2,
                frame->r3
            );
            FaultPrintf(
                "R12=0x%08x LR=0x%08x PC=0x%08x xPSR=0x%08x\r\n",
                frame->r12,
                frame->lr,
                frame->pc,
                frame->xpsr
            );
        }
        else
        {
            FaultPrintf("Invalid fault stack frame\r\n");
        }

        FaultPrintf(
            "CFSR=0x%08x HFSR=0x%08x DFSR=0x%08x AFSR=0x%08x\r\n",
            SCB->CFSR,
            SCB->HFSR,
            SCB->DFSR,
            SCB->AFSR
        );
        FaultPrintf(
            "MMFAR=0x%08x BFAR=0x%08x\r\n",
            SCB->MMFAR,
            SCB->BFAR
        );
        FaultPrintf(
            "ICSR=0x%08x SHCSR=0x%08x CCR=0x%08x VTOR=0x%08x\r\n",
            SCB->ICSR,
            SCB->SHCSR,
            SCB->CCR,
            SCB->VTOR
        );
        FaultPrintCfsr(SCB->CFSR);
    }

    void vApplicationHardFaultTrace(uint32_t excReturn, uint32_t faultSp)
    {
        if(s_faultHandleReady)
        {
            cm_backtrace_fault(excReturn, faultSp);
        }
        else
        {
            FaultPrintf("cm_backtrace is not initialized; skip call stack\r\n");
        }
    }
    
    void vApplicationHardFaultHook(uint32_t excReturn, uint32_t faultSp)
    {
        char crashInfo[96];

        if(IsValidRamFrame(faultSp))
        {
            const HardFaultStackFrame_t* frame = (const HardFaultStackFrame_t*)faultSp;
            snprintf(
                crashInfo,
                sizeof(crashInfo),
                "HardFault\nPC=0x%08x\nLR=0x%08x",
                frame->pc,
                frame->lr
            );
        }
        else
        {
            snprintf(
                crashInfo,
                sizeof(crashInfo),
                "HardFault\nEXC=0x%08x\nSP=0x%08x",
                excReturn,
                faultSp
            );
        }

#if CONFIG_HARDFAULT_DUMP_DISPLAY
        HAL::Display_DumpCrashInfo(crashInfo);
#else
        FaultPrintf("CrashInfo: %s\r\n", crashInfo);
#endif

#if CONFIG_HARDFAULT_AUTO_REBOOT
        FaultPrintf("HardFault auto reboot enabled\r\n");
        Reboot();
#else
        FaultPrintf("HardFault halted; reset manually after collecting RTT log\r\n");
        __disable_irq();
        for(;;)
        {
#if CONFIG_WATCH_DOG_ENABLE
            WDG_ReloadCounter();
#endif
        }
#endif
    }
    
    __asm void HardFault_Handler()
    {
        extern vApplicationHardFaultHook
        extern vApplicationHardFaultDump
        extern vApplicationHardFaultTrace
            
        mov r4, lr
        tst r4, #4
        beq use_msp
        mrs r5, psp
        b got_fault_sp
use_msp
        mrs r5, msp
got_fault_sp
        mov r0, r4
        mov r1, r5
        bl vApplicationHardFaultDump
        mov r0, r4
        mov r1, r5
        bl vApplicationHardFaultTrace
        mov r0, r4
        mov r1, r5
        bl vApplicationHardFaultHook
fault_loop
        b fault_loop
    }
}
