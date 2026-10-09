#ifndef E_TRACK_OTA_UI_CADENCE_H
#define E_TRACK_OTA_UI_CADENCE_H

#include <stdint.h>

#ifndef CONFIG_OTA_UI_CADENCE
#define CONFIG_OTA_UI_CADENCE 0
#endif

class OtaUiCadence
{
public:
    OtaUiCadence() : active_(false), previous_(0) {}

    bool due(uint32_t now, bool ota_owned)
    {
        if (!ota_owned)
        {
            active_ = false;
            return true;
        }
        if (!active_)
        {
            active_ = true;
            previous_ = now;
            return false;
        }
        if ((uint32_t)(now - previous_) < 200u)
        {
            return false;
        }
        previous_ = now;
        return true;
    }

private:
    bool active_;
    uint32_t previous_;
};

#endif
