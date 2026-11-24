/* Link-only fixture with an invalid firmware header. Never flash this image. */
#include <stdint.h>
#include "ota_layout.h"

extern char _estack;
void Reset_Handler(void);

__attribute__((section(".isr_vector"), used))
const uintptr_t vectors[] = {(uintptr_t)&_estack, (uintptr_t)Reset_Handler};
__attribute__((section(".fw_header"), used))
const unsigned char header[OTA_FW_HEADER_SIZE] = {0};
__attribute__((section(".ota_vtor_noinit"), used))
uint32_t markers[2];
__attribute__((section(".ota_overlay"), used))
unsigned char overlay[OTA_OVERLAY_WORKSPACE_LENGTH];
static volatile unsigned char ram[TEST_RAM_BYTES];

void Reset_Handler(void)
{
    for (;;) {
        ++ram[0];
    }
}
