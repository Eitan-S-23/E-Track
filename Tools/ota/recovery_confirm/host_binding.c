#include "confirm.h"

__declspec(dllexport) unsigned rc_host_size(unsigned which)
{
    if (which == 0) return (unsigned)sizeof(rc_plan);
    if (which == 1) return (unsigned)sizeof(rc_request);
    if (which == 2) return (unsigned)sizeof(rc_result);
    return (unsigned)sizeof(bcb_hal_t);
}

__declspec(dllexport) int rc_host_confirm(const rc_plan *plan,
    const rc_request *request, const bcb_hal_t *hal, rc_result *result)
{
    return (int)rc_confirm(plan, request, hal, result);
}
