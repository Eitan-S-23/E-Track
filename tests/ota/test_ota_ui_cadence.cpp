#include "HAL/ota_ui_cadence.h"
#include <assert.h>
#include <stdio.h>

int main()
{
    OtaUiCadence cadence;
    assert(cadence.due(0u, false));
    assert(cadence.due(1u, false));
    assert(!cadence.due(100u, true));
    assert(!cadence.due(299u, true));
    assert(cadence.due(300u, true));
    assert(!cadence.due(301u, true));
    assert(cadence.due(950u, true));
    assert(!cadence.due(951u, true));
    assert(cadence.due(952u, false));
    assert(!cadence.due(953u, true));
    assert(!cadence.due(1152u, true));
    assert(cadence.due(1153u, true));
    assert(cadence.due(UINT32_MAX - 100u, false));
    assert(!cadence.due(UINT32_MAX - 99u, true));
    assert(!cadence.due(99u, true));
    assert(cadence.due(100u, true));
    assert(cadence.due(101u, false));
    puts("OTA_UI_CADENCE_PASS checks=17");
    return 0;
}
