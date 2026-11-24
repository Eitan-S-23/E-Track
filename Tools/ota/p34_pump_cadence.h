#ifndef E_TRACK_P34_PUMP_CADENCE_H
#define E_TRACK_P34_PUMP_CADENCE_H

#include <stdint.h>

#ifndef CONFIG_OTA_ACTIVE_PUMP
#define CONFIG_OTA_ACTIVE_PUMP 0
#endif

inline uint32_t ota_pump_period(bool ble_owned, uint32_t idle_period)
{
#if CONFIG_OTA_ACTIVE_PUMP
    return ble_owned ? 2u : idle_period;
#else
    (void)ble_owned;
    return idle_period;
#endif
}

#endif
