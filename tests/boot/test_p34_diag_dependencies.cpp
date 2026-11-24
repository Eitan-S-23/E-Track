#include <cassert>
#include <cstdio>
#define P34_EARLY_FAULT_VECTORS 1
#define CONFIG_DEBUG_SERIAL_ENABLE 1
#define CONFIG_DEBUG_RTT_ENABLE 1
#define CONFIG_HARDFAULT_AUTO_REBOOT 0
#define CONFIG_HARDFAULT_DUMP_DISPLAY 0
#define SEGGER_RTT_MODE_NO_BLOCK_TRIM 1
static bool s_faultHandleReady;
static int backtrace_ready;
static int Serial5, other_serial;
static int* selected_serial;
#define CONFIG_DEBUG_SERIAL (*selected_serial)
struct MockUart { struct { int uen, ten; } ctrl1_bit; } uart;
static MockUart* UART5 = &uart;
struct MockRtt {
    int MaxNumUpBuffers;
    struct { void* pBuffer; unsigned SizeOfBuffer, Flags; } aUp[1];
} _SEGGER_RTT;
extern "C" int p34_backtrace_ready(void) { return backtrace_ready; }
#include "diag_impl.inc"

int main()
{
    for (unsigned mask = 0; mask < 512; ++mask)
    {
        s_faultHandleReady = (mask & 1) != 0;
        backtrace_ready = (mask & 2) != 0;
        selected_serial = mask & 4 ? &Serial5 : &other_serial;
        uart.ctrl1_bit.uen = (mask & 8) != 0;
        uart.ctrl1_bit.ten = (mask & 16) != 0;
        _SEGGER_RTT.MaxNumUpBuffers = (mask & 32) != 0;
        _SEGGER_RTT.aUp[0].pBuffer = mask & 64 ? &Serial5 : 0;
        _SEGGER_RTT.aUp[0].SizeOfBuffer = (mask & 128) != 0;
        _SEGGER_RTT.aUp[0].Flags = mask & 256 ? SEGGER_RTT_MODE_NO_BLOCK_TRIM : 0;
        assert(p34_runtime_diagnostics_ready() == (mask == 511));
    }
    std::puts("DIAGNOSTIC_DEPENDENCY_PASS checks=512");
}
