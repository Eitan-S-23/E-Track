#include <cassert>
#include <cstdio>
#include <string>
#include "p34_early_mock/HAL.h"
std::string trace;
uintptr_t mock_ipsr, mock_mask, before_nmi, after_nmi;
MockScb scb;
MockScb* SCB = &scb;
static int ready;
extern "C" const uintptr_t p34_runtime_vectors[] = {0, 0};
extern "C" int p34_runtime_diagnostics_ready(void) { return ready; }
extern "C" __attribute__((noreturn)) void p34_early_exception(void) { trace += 'E'; throw 1; }
#include "../../Tools/ota/p34_early_fault.cpp"

int main()
{
    unsigned checks = 0;
    for (unsigned mode = 0; mode < 2; ++mode)
    for (unsigned wrong = 0; wrong < 2; ++wrong)
    for (unsigned deps = 0; deps < 2; ++deps)
    for (unsigned mask = 0; mask < 2; ++mask)
    {
        trace.clear(); mock_ipsr = mode; ready = deps; mock_mask = mask;
        scb.VTOR.value = OTA_APP_ORIGIN + wrong * 1024;
        bool allowed = mode == 0 && wrong == 0 && deps == 1;
        bool halted = false;
        try { p34_enable_runtime_vectors(); } catch (int) { halted = true; }
        assert(halted != allowed);
        assert(mock_mask == mask);
        if (allowed)
        {
            assert(trace == "IDVDSR");
            assert(before_nmi == OTA_APP_ORIGIN);
            assert(after_nmi == (uintptr_t)p34_runtime_vectors);
            assert(scb.VTOR.value == after_nmi);
        }
        else
        {
            assert(trace == "E");
            assert(scb.VTOR.value == OTA_APP_ORIGIN + wrong * 1024);
        }
        ++checks;
    }
    std::printf("EARLY_PROMOTION_SEQUENCE_PASS checks=%u\n", checks);
}
