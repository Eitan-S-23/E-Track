#ifndef P34_HOST_HAL_H
#define P34_HOST_HAL_H
#include <stdint.h>
#include <string>
extern std::string trace;
extern uintptr_t mock_ipsr, mock_mask, before_nmi, after_nmi;
struct MockVtor {
    uintptr_t value;
    operator uintptr_t() const { return value; }
    void operator=(uintptr_t next) {
        before_nmi = value;
        trace += 'V'; value = next;
        after_nmi = value;
    }
};
struct MockScb { MockVtor VTOR; };
extern MockScb* SCB;
inline uintptr_t __get_IPSR() { return mock_ipsr; }
inline uintptr_t __get_PRIMASK() { return mock_mask; }
inline void __disable_irq() { trace += 'I'; mock_mask = 1; }
inline void __DSB() { trace += 'D'; }
inline void __ISB() { trace += 'S'; }
inline void __set_PRIMASK(uintptr_t v) { trace += 'R'; mock_mask = v; }
/* Host pointer-width adaptation only; target validation uses the actual ARM ELF. */
#define uint32_t uintptr_t
#endif
