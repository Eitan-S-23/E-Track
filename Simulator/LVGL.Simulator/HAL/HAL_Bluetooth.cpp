#include "HAL.h"
#include "Common/DataProc/DataProc.h"
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

void HAL::BT_CompanionGetInfo(CompanionUpdateInfo* info)
{
    if (info == nullptr) return;
    memset(info, 0, sizeof(*info));
    strcpy(info->status, "SIMULATOR_NO_PHONE");
}

bool HAL::BT_CompanionCheck() { return false; }
bool HAL::BT_CompanionChoose(bool, const CompanionUpdateInfo*) { return false; }
bool HAL::BT_CompanionCanInstall() { return false; }
void HAL::BT_CompanionPresented(const CompanionUpdateInfo*) {}



