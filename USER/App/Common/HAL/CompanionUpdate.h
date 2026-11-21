#ifndef ETRACK_COMPANION_UPDATE_H
#define ETRACK_COMPANION_UPDATE_H

#include <stdint.h>
#include <string.h>

namespace HAL
{
enum CompanionUpdatePhase
{
    COMPANION_UPDATE_IDLE,
    COMPANION_UPDATE_TRANSFERRING,
    COMPANION_UPDATE_APPLYING,
    COMPANION_UPDATE_BACKING_UP,
    COMPANION_UPDATE_REBOOTING,
    COMPANION_UPDATE_FAILED
};

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
    // Local receiver projection, not phone-reported or wire-protocol fields.
    CompanionUpdatePhase phase;
    uint32_t totalBytes;
    uint32_t durableBytes;
    uint32_t transferVersion;
    uint32_t currentVersion; // Validated local running-image identity, zero if unknown.
};

inline bool CompanionUpdateActive(const CompanionUpdateInfo& info)
{
    return info.phase >= COMPANION_UPDATE_TRANSFERRING && info.phase <= COMPANION_UPDATE_REBOOTING;
}

inline int CompanionTransferPercent(const CompanionUpdateInfo& info)
{
    if (info.phase != COMPANION_UPDATE_TRANSFERRING || info.totalBytes == 0u ||
        info.durableBytes > info.totalBytes) return -1;
    return (int)((uint64_t)info.durableBytes * 100u / info.totalBytes);
}

inline bool CompanionSameOffer(const CompanionUpdateInfo& first, const CompanionUpdateInfo& second)
{
    return first.hasOffer && second.hasOffer && !first.checking && !second.checking &&
        first.offerRevision == second.offerRevision &&
        first.version == second.version && first.request == second.request &&
        strcmp(first.session, second.session) == 0 && strcmp(first.offer, second.offer) == 0 &&
        strcmp(first.packageSha256, second.packageSha256) == 0 && strcmp(first.targetSha256, second.targetSha256) == 0;
}

// Estimated milestones for pre-reboot preparation, not verified installation.
// Synchronous storage work advances at real boundaries, never by a timer.
inline int CompanionProcessingPercent(const CompanionUpdateInfo& info)
{
    switch (info.phase)
    {
    case COMPANION_UPDATE_APPLYING: return 20;
    case COMPANION_UPDATE_BACKING_UP: return 75;
    case COMPANION_UPDATE_REBOOTING: return 100;
    default: return -1;
    }
}

void BT_CompanionGetInfo(CompanionUpdateInfo* info);
// Main-loop phase boundaries only, outside storage operations and the UART ISR.
typedef void (*CompanionProgressRefresh)();
void BT_CompanionSetProgressRefresh(CompanionProgressRefresh refresh);
bool BT_CompanionCheck();
bool BT_CompanionChoose(bool updateNow, const CompanionUpdateInfo* displayed);
bool BT_CompanionCanInstall();
bool BT_CompanionInstallPending();
void BT_CompanionPresented(const CompanionUpdateInfo* displayed);
}

#endif
