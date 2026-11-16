#ifndef ETRACK_COMPANION_UPDATE_H
#define ETRACK_COMPANION_UPDATE_H

#include <stdint.h>
#include <string.h>

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
    uint32_t offerRevision;
    bool hasOffer;
    bool prompt;
    bool checking;
};

inline bool CompanionSameOffer(const CompanionUpdateInfo& first, const CompanionUpdateInfo& second)
{
    return first.hasOffer && second.hasOffer && !first.checking && !second.checking &&
        first.offerRevision == second.offerRevision &&
        first.version == second.version && first.request == second.request &&
        strcmp(first.session, second.session) == 0 && strcmp(first.offer, second.offer) == 0 &&
        strcmp(first.packageSha256, second.packageSha256) == 0 && strcmp(first.targetSha256, second.targetSha256) == 0;
}

void BT_CompanionGetInfo(CompanionUpdateInfo* info);
bool BT_CompanionCheck();
bool BT_CompanionChoose(bool updateNow, const CompanionUpdateInfo* displayed);
bool BT_CompanionCanInstall();
bool BT_CompanionInstallPending();
void BT_CompanionPresented(const CompanionUpdateInfo* displayed);
}

#endif
