#ifndef E_TRACK_STAGING_HAL_TEST_PLATFORM_H
#define E_TRACK_STAGING_HAL_TEST_PLATFORM_H

#include <stdint.h>

typedef struct qspi_cmd_type
{
    uint32_t unused;
} qspi_cmd_type;

enum { FALSE = 0, TRUE = 1 };

#define QSPI1 ((void *)1)
#define QSPI1_MEM_BASE staging_test_mapped_base()

uintptr_t staging_test_mapped_base(void);
void qspi_xip_enable(void *qspi, int enabled);

namespace HAL
{
bool Qspi_IsOtaDisabled();
uint32_t Qspi_GetJedecId();
}

#endif
