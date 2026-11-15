#ifndef ETRACK_COMPANION_UPDATE_H
#define ETRACK_COMPANION_UPDATE_H

#include <stdint.h>

namespace HAL
{
struct CompanionUpdateInfo
{
    char status[32];
    char session[33];
    char offer[33];
    char packageSha256[65];
    char targetSha256[65];
    uint32_t request;
    uint32_t version;
    bool hasOffer;
    bool prompt;
    bool checking;
};

void BT_CompanionGetInfo(CompanionUpdateInfo* info);
bool BT_CompanionCheck();
bool BT_CompanionChoose(bool updateNow, const CompanionUpdateInfo* displayed);
bool BT_CompanionCanInstall();
void BT_CompanionPresented(const CompanionUpdateInfo* displayed);
}

#endif
