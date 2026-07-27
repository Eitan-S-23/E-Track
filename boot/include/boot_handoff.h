#ifndef E_TRACK_BOOT_HANDOFF_H
#define E_TRACK_BOOT_HANDOFF_H

#ifdef __cplusplus
extern "C" {
#endif

#if defined(__GNUC__)
#define BOOT_HANDOFF_NORETURN __attribute__((noreturn))
#else
#define BOOT_HANDOFF_NORETURN
#endif

BOOT_HANDOFF_NORETURN void boot_handoff_to_app(void);

#if defined(BOOT_HANDOFF_TEST_INJECT_PENDING)
void boot_handoff_test_inject_pending(void);
#endif

#ifdef __cplusplus
}
#endif

#endif
