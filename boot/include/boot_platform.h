#ifndef E_TRACK_BOOT_PLATFORM_H
#define E_TRACK_BOOT_PLATFORM_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int boot_platform_init(void);
uint32_t boot_platform_millis(void);
void boot_platform_delay_ms(uint32_t delay_ms);
int boot_platform_recovery_key_held(void);

void boot_platform_uart_putc(uint8_t byte);
int boot_platform_uart_getc(uint8_t *byte, uint32_t timeout_ms);
void boot_platform_log(const char *text);

int boot_platform_eeprom_read(uint8_t address, uint8_t *dst, uint16_t len);
int boot_platform_eeprom_write(uint8_t address, const uint8_t *src, uint16_t len);

int boot_platform_qspi_init(void);
int boot_platform_qspi_read(uint32_t address, uint8_t *dst, size_t len);

int boot_platform_flash_erase_4k(uint32_t address);
int boot_platform_flash_program(uint32_t address, const uint8_t *src, size_t len);
int boot_platform_flash_read(uint32_t address, uint8_t *dst, size_t len);
int boot_platform_watchdog_start(void);

void boot_platform_hold(void);

#ifdef __cplusplus
}
#endif

#endif
