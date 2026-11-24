#ifndef P34_EARLY_FAULT_POLICY_H
#define P34_EARLY_FAULT_POLICY_H
#include <stdint.h>

/* This is consulted only at the post-initialization promotion call site.
 * Primary Flash vectors, not this predicate or RAM, select the early handler. */
static int p34_promotion_allowed(uint32_t ipsr, uint32_t actual,
                                 uint32_t primary, int dependencies_ready)
{
    return ipsr == 0u && actual == primary && dependencies_ready == 1;
}
#endif
