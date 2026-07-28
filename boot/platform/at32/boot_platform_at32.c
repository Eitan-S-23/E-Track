#include "boot_platform.h"

#include "OTA/ota_layout.h"

#include "at32f435_437.h"

#include <string.h>

enum
{
    BOOT_UART_BAUD = 115200,
    BOOT_RECOVERY_HOLD_MS = 3000,
    BOOT_EEPROM_ADDRESS = 0x50,
    BOOT_EEPROM_PAGE_SIZE = 8,
    BOOT_EEPROM_CAPACITY = 256,
    BOOT_EEPROM_RESERVED_ADDR = 0xFF,
    BOOT_I2C_ACK_TIMEOUT_MS = 10,
    BOOT_QSPI_TIMEOUT_MS = 100,
    BOOT_QSPI_BUSY_TIMEOUT_MS = 2000,
    BOOT_QSPI_PAGE_SIZE = 256,
    BOOT_FLASH_ERASE_UNIT_SIZE = 2048,
    BOOT_FLASH_COPY_BLOCK_SIZE = 4096,
    BOOT_QSPI_READ_CHUNK = 32,
    BOOT_TEST_WATCHDOG_RELOAD = 1561
};

static volatile uint32_t g_boot_millis;

void SysTick_Handler(void)
{
    ++g_boot_millis;
}

uint32_t boot_platform_millis(void)
{
    return g_boot_millis;
}

void boot_platform_delay_ms(uint32_t delay_ms)
{
    uint32_t start = boot_platform_millis();
    while ((uint32_t)(boot_platform_millis() - start) < delay_ms)
    {
        __WFI();
    }
}

static void configure_power_hold(void)
{
    gpio_init_type gpio;

    crm_periph_clock_enable(CRM_GPIOD_PERIPH_CLOCK, TRUE);
    gpio_default_para_init(&gpio);
    gpio.gpio_pins = GPIO_PINS_2;
    gpio.gpio_mode = GPIO_MODE_OUTPUT;
    gpio.gpio_out_type = GPIO_OUTPUT_PUSH_PULL;
    gpio.gpio_pull = GPIO_PULL_NONE;
    gpio.gpio_drive_strength = GPIO_DRIVE_STRENGTH_STRONGER;
    gpio_init(GPIOD, &gpio);
    gpio_bits_reset(GPIOD, GPIO_PINS_2);
    boot_platform_delay_ms(1000u);
    gpio_bits_set(GPIOD, GPIO_PINS_2);
}

static void configure_recovery_key(void)
{
    gpio_init_type gpio;

    crm_periph_clock_enable(CRM_GPIOA_PERIPH_CLOCK, TRUE);
    gpio_default_para_init(&gpio);
    gpio.gpio_pins = GPIO_PINS_15;
    gpio.gpio_mode = GPIO_MODE_INPUT;
    gpio.gpio_pull = GPIO_PULL_UP;
    gpio_init(GPIOA, &gpio);
}

static void configure_uart(void)
{
    gpio_init_type gpio;

    crm_periph_clock_enable(CRM_GPIOB_PERIPH_CLOCK, TRUE);
    crm_periph_clock_enable(CRM_UART5_PERIPH_CLOCK, TRUE);
    gpio_default_para_init(&gpio);
    gpio.gpio_pins = GPIO_PINS_8 | GPIO_PINS_9;
    gpio.gpio_mode = GPIO_MODE_MUX;
    gpio.gpio_pull = GPIO_PULL_NONE;
    gpio.gpio_out_type = GPIO_OUTPUT_PUSH_PULL;
    gpio.gpio_drive_strength = GPIO_DRIVE_STRENGTH_STRONGER;
    gpio_init(GPIOB, &gpio);
    gpio_pin_mux_config(GPIOB, GPIO_PINS_SOURCE8, GPIO_MUX_8);
    gpio_pin_mux_config(GPIOB, GPIO_PINS_SOURCE9, GPIO_MUX_8);

    usart_init(UART5, BOOT_UART_BAUD, USART_DATA_8BITS, USART_STOP_1_BIT);
    usart_parity_selection_config(UART5, USART_PARITY_NONE);
    usart_transmitter_enable(UART5, TRUE);
    usart_receiver_enable(UART5, TRUE);
    usart_enable(UART5, TRUE);
}

static void configure_eeprom_gpio(void)
{
    gpio_init_type gpio;

    crm_periph_clock_enable(CRM_GPIOB_PERIPH_CLOCK, TRUE);
    gpio_default_para_init(&gpio);
    gpio.gpio_pins = GPIO_PINS_6 | GPIO_PINS_7;
    gpio.gpio_mode = GPIO_MODE_OUTPUT;
    gpio.gpio_pull = GPIO_PULL_UP;
    gpio.gpio_out_type = GPIO_OUTPUT_OPEN_DRAIN;
    gpio.gpio_drive_strength = GPIO_DRIVE_STRENGTH_MODERATE;
    gpio_init(GPIOB, &gpio);
    gpio_bits_set(GPIOB, GPIO_PINS_6 | GPIO_PINS_7);
}

int boot_platform_init(void)
{
    system_core_clock_update();
    g_boot_millis = 0u;
    if (SysTick_Config(system_core_clock / 1000u) != 0u)
    {
        return -1;
    }

    configure_power_hold();
    configure_recovery_key();
    configure_uart();
    configure_eeprom_gpio();
    boot_platform_log("BOOT: P1-1 skeleton\r\n");
    return 0;
}

int boot_platform_recovery_key_held(void)
{
    uint32_t start;

    if (gpio_input_data_bit_read(GPIOA, GPIO_PINS_15) != RESET)
    {
        return 0;
    }
    start = boot_platform_millis();
    while (gpio_input_data_bit_read(GPIOA, GPIO_PINS_15) == RESET)
    {
        if ((uint32_t)(boot_platform_millis() - start) >= BOOT_RECOVERY_HOLD_MS)
        {
            return 1;
        }
        __WFI();
    }
    return 0;
}

void boot_platform_uart_putc(uint8_t byte)
{
    uint32_t start = boot_platform_millis();

    while (usart_flag_get(UART5, USART_TDBE_FLAG) == RESET)
    {
        if ((uint32_t)(boot_platform_millis() - start) >= BOOT_QSPI_TIMEOUT_MS)
        {
            return;
        }
    }
    usart_data_transmit(UART5, byte);
}

int boot_platform_uart_getc(uint8_t *byte, uint32_t timeout_ms)
{
    uint32_t start;

    if (byte == NULL)
    {
        return -1;
    }
    start = boot_platform_millis();
    while (usart_flag_get(UART5, USART_RDBF_FLAG) == RESET)
    {
        if ((uint32_t)(boot_platform_millis() - start) >= timeout_ms)
        {
            return -1;
        }
    }
    *byte = (uint8_t)usart_data_receive(UART5);
    return 0;
}

void boot_platform_log(const char *text)
{
    if (text == NULL)
    {
        return;
    }
    while (*text != '\0')
    {
        boot_platform_uart_putc((uint8_t)*text++);
    }
}

static void i2c_delay(void)
{
    volatile uint32_t count;
    for (count = 0u; count < 24u; ++count)
    {
        __NOP();
    }
}

static void i2c_sda(int high)
{
    if (high)
    {
        gpio_bits_set(GPIOB, GPIO_PINS_7);
    }
    else
    {
        gpio_bits_reset(GPIOB, GPIO_PINS_7);
    }
    i2c_delay();
}

static int i2c_scl(int high)
{
    uint32_t start;

    if (!high)
    {
        gpio_bits_reset(GPIOB, GPIO_PINS_6);
        i2c_delay();
        return 0;
    }

    gpio_bits_set(GPIOB, GPIO_PINS_6);
    start = boot_platform_millis();
    while (gpio_input_data_bit_read(GPIOB, GPIO_PINS_6) == RESET)
    {
        if ((uint32_t)(boot_platform_millis() - start) >= 2u)
        {
            return -1;
        }
    }
    i2c_delay();
    return 0;
}

static int i2c_start(void)
{
    i2c_sda(1);
    if (i2c_scl(1) != 0)
    {
        return -1;
    }
    i2c_sda(0);
    return i2c_scl(0);
}

static void i2c_stop(void)
{
    i2c_sda(0);
    (void)i2c_scl(1);
    i2c_sda(1);
}

static int i2c_write_byte(uint8_t value)
{
    uint32_t bit;
    int acknowledged;

    for (bit = 0u; bit < 8u; ++bit)
    {
        i2c_sda((value & 0x80u) != 0u);
        if (i2c_scl(1) != 0)
        {
            return -1;
        }
        (void)i2c_scl(0);
        value <<= 1;
    }

    i2c_sda(1);
    if (i2c_scl(1) != 0)
    {
        return -1;
    }
    acknowledged = gpio_input_data_bit_read(GPIOB, GPIO_PINS_7) == RESET;
    (void)i2c_scl(0);
    return acknowledged ? 0 : -1;
}

static int i2c_read_byte(uint8_t *value, int acknowledge)
{
    uint32_t bit;
    uint8_t data = 0u;

    if (value == NULL)
    {
        return -1;
    }
    i2c_sda(1);
    for (bit = 0u; bit < 8u; ++bit)
    {
        data <<= 1;
        if (i2c_scl(1) != 0)
        {
            return -1;
        }
        if (gpio_input_data_bit_read(GPIOB, GPIO_PINS_7) != RESET)
        {
            data |= 1u;
        }
        (void)i2c_scl(0);
    }

    i2c_sda(acknowledge ? 0 : 1);
    if (i2c_scl(1) != 0)
    {
        return -1;
    }
    (void)i2c_scl(0);
    i2c_sda(1);
    *value = data;
    return 0;
}

static int eeprom_probe(void)
{
    int result;

    if (i2c_start() != 0)
    {
        return -1;
    }
    result = i2c_write_byte((uint8_t)(BOOT_EEPROM_ADDRESS << 1));
    i2c_stop();
    return result;
}

static int eeprom_write_page(uint8_t address, const uint8_t *src, uint8_t len)
{
    uint32_t start;
    uint8_t i;

    if (i2c_start() != 0 ||
        i2c_write_byte((uint8_t)(BOOT_EEPROM_ADDRESS << 1)) != 0 ||
        i2c_write_byte(address) != 0)
    {
        i2c_stop();
        return -1;
    }
    for (i = 0u; i < len; ++i)
    {
        if (i2c_write_byte(src[i]) != 0)
        {
            i2c_stop();
            return -1;
        }
    }
    i2c_stop();

    start = boot_platform_millis();
    while (eeprom_probe() != 0)
    {
        if ((uint32_t)(boot_platform_millis() - start) >= BOOT_I2C_ACK_TIMEOUT_MS)
        {
            return -1;
        }
    }
    return 0;
}

int boot_platform_eeprom_read(uint8_t address, uint8_t *dst, uint16_t len)
{
    uint16_t i;

    if ((dst == NULL && len != 0u) ||
        (uint16_t)address + len > BOOT_EEPROM_CAPACITY)
    {
        return -1;
    }
    if (len == 0u)
    {
        return 0;
    }
    if (i2c_start() != 0 ||
        i2c_write_byte((uint8_t)(BOOT_EEPROM_ADDRESS << 1)) != 0 ||
        i2c_write_byte(address) != 0 ||
        i2c_start() != 0 ||
        i2c_write_byte((uint8_t)((BOOT_EEPROM_ADDRESS << 1) | 1u)) != 0)
    {
        i2c_stop();
        return -1;
    }

    for (i = 0u; i < len; ++i)
    {
        if (i2c_read_byte(dst + i, i + 1u < len) != 0)
        {
            i2c_stop();
            return -1;
        }
    }
    i2c_stop();
    return 0;
}

int boot_platform_eeprom_write(uint8_t address, const uint8_t *src, uint16_t len)
{
    uint16_t offset = 0u;
    uint8_t verify[16];

    if ((src == NULL && len != 0u) || len == 0u ||
        (uint16_t)address + len > BOOT_EEPROM_RESERVED_ADDR)
    {
        return len == 0u ? 0 : -1;
    }

    while (offset < len)
    {
        uint8_t current = (uint8_t)(address + offset);
        uint8_t room = (uint8_t)(BOOT_EEPROM_PAGE_SIZE -
                                 (current & (BOOT_EEPROM_PAGE_SIZE - 1u)));
        uint16_t left = len - offset;
        uint8_t take = left < room ? (uint8_t)left : room;

        if (eeprom_write_page(current, src + offset, take) != 0)
        {
            return -1;
        }
        offset += take;
    }

    offset = 0u;
    while (offset < len)
    {
        uint16_t left = len - offset;
        uint16_t take = left < sizeof(verify) ? left : sizeof(verify);
        if (boot_platform_eeprom_read((uint8_t)(address + offset), verify, take) != 0 ||
            memcmp(verify, src + offset, take) != 0)
        {
            return -1;
        }
        offset += take;
    }
    return 0;
}

static int qspi_wait_flag(uint32_t flag, uint32_t timeout_ms)
{
    uint32_t start = boot_platform_millis();
    while (qspi_flag_get(QSPI1, flag) == RESET)
    {
        if ((uint32_t)(boot_platform_millis() - start) >= timeout_ms)
        {
            return -1;
        }
    }
    return 0;
}

static int qspi_send(uint8_t instruction)
{
    qspi_cmd_type command;

    memset(&command, 0, sizeof(command));
    command.instruction_code = instruction;
    command.instruction_length = QSPI_CMD_INSLEN_1_BYTE;
    command.address_length = QSPI_CMD_ADRLEN_0_BYTE;
    command.operation_mode = QSPI_OPERATE_MODE_111;
    command.read_status_config = QSPI_RSTSC_HW_AUTO;
    command.read_status_enable = FALSE;
    command.write_data_enable = TRUE;
    qspi_cmd_operation_kick(QSPI1, &command);
    if (qspi_wait_flag(QSPI_CMDSTS_FLAG, BOOT_QSPI_TIMEOUT_MS) != 0)
    {
        return -1;
    }
    qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);
    return 0;
}

static int qspi_read_command(uint8_t instruction,
                             uint32_t address,
                             qspi_cmd_adrlen_type address_len,
                             uint8_t *dst, size_t len);

static int qspi_wait_ready(uint32_t timeout_ms)
{
    uint32_t start = boot_platform_millis();
    uint8_t status;

    do
    {
        if (qspi_read_command(0x05u, 0u, QSPI_CMD_ADRLEN_0_BYTE,
                              &status, sizeof(status)) != 0)
        {
            return -1;
        }
        if ((status & 1u) == 0u)
        {
            return 0;
        }
    } while ((uint32_t)(boot_platform_millis() - start) < timeout_ms);
    return -1;
}

static int qspi_address_command(uint8_t instruction, uint32_t address)
{
    qspi_cmd_type command;

    memset(&command, 0, sizeof(command));
    command.instruction_code = instruction;
    command.instruction_length = QSPI_CMD_INSLEN_1_BYTE;
    command.address_code = address;
    command.address_length = QSPI_CMD_ADRLEN_3_BYTE;
    command.operation_mode = QSPI_OPERATE_MODE_111;
    command.read_status_config = QSPI_RSTSC_HW_AUTO;
    command.read_status_enable = FALSE;
    command.write_data_enable = TRUE;
    qspi_cmd_operation_kick(QSPI1, &command);
    if (qspi_wait_flag(QSPI_CMDSTS_FLAG, BOOT_QSPI_TIMEOUT_MS) != 0)
    {
        return -1;
    }
    qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);
    return 0;
}

static int qspi_program_page(uint32_t address,
                             const uint8_t *src, size_t len)
{
    qspi_cmd_type command;
    size_t index;

    if (len == 0u || len > BOOT_QSPI_PAGE_SIZE ||
        (address & (BOOT_QSPI_PAGE_SIZE - 1u)) + len > BOOT_QSPI_PAGE_SIZE ||
        qspi_send(0x06u) != 0)
    {
        return -1;
    }

    memset(&command, 0, sizeof(command));
    command.instruction_code = 0x02u;
    command.instruction_length = QSPI_CMD_INSLEN_1_BYTE;
    command.address_code = address;
    command.address_length = QSPI_CMD_ADRLEN_3_BYTE;
    command.data_counter = (uint32_t)len;
    command.operation_mode = QSPI_OPERATE_MODE_111;
    command.read_status_config = QSPI_RSTSC_HW_AUTO;
    command.read_status_enable = FALSE;
    command.write_data_enable = TRUE;
    qspi_cmd_operation_kick(QSPI1, &command);
    for (index = 0u; index < len; ++index)
    {
        if (qspi_wait_flag(QSPI_TXFIFORDY_FLAG, BOOT_QSPI_TIMEOUT_MS) != 0)
        {
            return -1;
        }
        qspi_byte_write(QSPI1, src[index]);
    }
    if (qspi_wait_flag(QSPI_CMDSTS_FLAG, BOOT_QSPI_TIMEOUT_MS) != 0)
    {
        return -1;
    }
    qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);
    return qspi_wait_ready(BOOT_QSPI_BUSY_TIMEOUT_MS);
}

static int qspi_read_command(uint8_t instruction,
                             uint32_t address,
                             qspi_cmd_adrlen_type address_len,
                             uint8_t *dst,
                             size_t len)
{
    qspi_cmd_type command;
    size_t i;

    memset(&command, 0, sizeof(command));
    command.instruction_code = instruction;
    command.instruction_length = QSPI_CMD_INSLEN_1_BYTE;
    command.address_code = address;
    command.address_length = address_len;
    command.data_counter = (uint32_t)len;
    command.operation_mode = QSPI_OPERATE_MODE_111;
    command.read_status_config = QSPI_RSTSC_HW_AUTO;
    command.read_status_enable = FALSE;
    command.write_data_enable = FALSE;
    qspi_cmd_operation_kick(QSPI1, &command);
    if (qspi_wait_flag(QSPI_CMDSTS_FLAG, BOOT_QSPI_TIMEOUT_MS) != 0)
    {
        return -1;
    }
    qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);
    for (i = 0u; i < len; ++i)
    {
        dst[i] = qspi_byte_read(QSPI1);
    }
    return 0;
}

static int qspi_jedec_allowed(uint32_t jedec)
{
    return jedec == 0xEF4018u || jedec == 0x1C4018u ||
           jedec == 0x1C4017u || jedec == 0xEF4017u;
}

int boot_platform_qspi_init(void)
{
    gpio_init_type gpio;
    uint8_t id[3];
    uint32_t jedec;

    crm_periph_clock_enable(CRM_QSPI1_PERIPH_CLOCK, TRUE);
    crm_periph_clock_enable(CRM_GPIOB_PERIPH_CLOCK, TRUE);
    crm_periph_clock_enable(CRM_GPIOC_PERIPH_CLOCK, TRUE);

    gpio_default_para_init(&gpio);
    gpio.gpio_drive_strength = GPIO_DRIVE_STRENGTH_STRONGER;
    gpio.gpio_out_type = GPIO_OUTPUT_PUSH_PULL;
    gpio.gpio_mode = GPIO_MODE_MUX;
    gpio.gpio_pull = GPIO_PULL_NONE;

    gpio.gpio_pins = GPIO_PINS_9 | GPIO_PINS_10 | GPIO_PINS_8;
    gpio_init(GPIOC, &gpio);
    gpio_pin_mux_config(GPIOC, GPIO_PINS_SOURCE9, GPIO_MUX_9);
    gpio_pin_mux_config(GPIOC, GPIO_PINS_SOURCE10, GPIO_MUX_9);
    gpio_pin_mux_config(GPIOC, GPIO_PINS_SOURCE8, GPIO_MUX_9);
    gpio.gpio_pins = GPIO_PINS_3;
    gpio_init(GPIOB, &gpio);
    gpio_pin_mux_config(GPIOB, GPIO_PINS_SOURCE3, GPIO_MUX_10);
    gpio.gpio_pins = GPIO_PINS_1;
    gpio_init(GPIOB, &gpio);
    gpio_pin_mux_config(GPIOB, GPIO_PINS_SOURCE1, GPIO_MUX_9);
    gpio.gpio_pins = GPIO_PINS_11;
    gpio_init(GPIOC, &gpio);
    gpio_pin_mux_config(GPIOC, GPIO_PINS_SOURCE11, GPIO_MUX_9);

    qspi_xip_enable(QSPI1, FALSE);
    qspi_clk_division_set(QSPI1, QSPI_CLK_DIV_2);
    qspi_sck_mode_set(QSPI1, QSPI_SCK_MODE_0);
    qspi_busy_config(QSPI1, QSPI_BUSY_OFFSET_0);
    qspi_auto_ispc_enable(QSPI1);

    if (qspi_send(0x66u) != 0 || qspi_send(0x99u) != 0)
    {
        return -1;
    }
    boot_platform_delay_ms(1u);
    if (qspi_read_command(0x9Fu, 0u, QSPI_CMD_ADRLEN_0_BYTE, id, sizeof(id)) != 0)
    {
        return -1;
    }
    jedec = ((uint32_t)id[0] << 16) | ((uint32_t)id[1] << 8) | id[2];
    return qspi_jedec_allowed(jedec) ? 0 : -1;
}

int boot_platform_qspi_read(uint32_t address, uint8_t *dst, size_t len)
{
    size_t offset = 0u;

    if ((dst == NULL && len != 0u) || address > OTA_EXT_WINDOW_LENGTH ||
        len > OTA_EXT_WINDOW_LENGTH - address)
    {
        return -1;
    }
    while (offset < len)
    {
        size_t take = len - offset;
        if (take > BOOT_QSPI_READ_CHUNK)
        {
            take = BOOT_QSPI_READ_CHUNK;
        }
        if (qspi_read_command(0x03u, address + (uint32_t)offset,
                              QSPI_CMD_ADRLEN_3_BYTE, dst + offset, take) != 0)
        {
            return -1;
        }
        offset += take;
    }
    return 0;
}

int boot_platform_qspi_erase_4k(uint32_t address)
{
    if ((address & (BOOT_FLASH_COPY_BLOCK_SIZE - 1u)) != 0u ||
        address >= OTA_EXT_SELFTEST ||
        address > OTA_EXT_SELFTEST - BOOT_FLASH_COPY_BLOCK_SIZE ||
        qspi_send(0x06u) != 0 || qspi_address_command(0x20u, address) != 0)
    {
        return -1;
    }
    return qspi_wait_ready(BOOT_QSPI_BUSY_TIMEOUT_MS);
}

int boot_platform_qspi_program(uint32_t address,
                               const uint8_t *src, size_t len)
{
    size_t offset = 0u;

    if ((src == NULL && len != 0u) || address >= OTA_EXT_SELFTEST ||
        len > OTA_EXT_SELFTEST - address)
    {
        return -1;
    }
    while (offset < len)
    {
        size_t take = BOOT_QSPI_PAGE_SIZE -
                      ((address + (uint32_t)offset) &
                       (BOOT_QSPI_PAGE_SIZE - 1u));
        if (take > len - offset)
        {
            take = len - offset;
        }
        if (qspi_program_page(address + (uint32_t)offset,
                              src + offset, take) != 0)
        {
            return -1;
        }
        offset += take;
    }
    return 0;
}

int boot_platform_flash_erase_4k(uint32_t address)
{
    const volatile uint32_t *word;
    flash_status_type first_status;
    flash_status_type second_status = FLASH_OPERATE_DONE;
    size_t offset;

    if ((address & (BOOT_FLASH_COPY_BLOCK_SIZE - 1u)) != 0u ||
        address < OTA_APP_ORIGIN ||
        address > OTA_APP_ORIGIN + OTA_APP_LENGTH - BOOT_FLASH_COPY_BLOCK_SIZE)
    {
        return -1;
    }

    /* The AT32F435 FLM declares 0x800-byte erase sectors; OTA copies 4 KiB blocks. */
    flash_unlock();
    first_status = flash_sector_erase(address);
    if (first_status == FLASH_OPERATE_DONE)
    {
        second_status = flash_sector_erase(address + BOOT_FLASH_ERASE_UNIT_SIZE);
    }
    flash_lock();
    if (first_status != FLASH_OPERATE_DONE || second_status != FLASH_OPERATE_DONE)
    {
        return -1;
    }

    word = (const volatile uint32_t *)(uintptr_t)address;
    for (offset = 0u; offset < BOOT_FLASH_COPY_BLOCK_SIZE; offset += sizeof(*word))
    {
        if (*word++ != 0xFFFFFFFFu)
        {
            return -1;
        }
    }
    return 0;
}

int boot_platform_flash_program(uint32_t address, const uint8_t *src, size_t len)
{
    size_t offset;

    if (src == NULL || len == 0u || (address & 3u) != 0u || (len & 3u) != 0u ||
        address < OTA_APP_ORIGIN || address >= OTA_APP_ORIGIN + OTA_APP_LENGTH ||
        len > OTA_APP_ORIGIN + OTA_APP_LENGTH - address)
    {
        return -1;
    }

    flash_unlock();
    for (offset = 0u; offset < len; offset += 4u)
    {
        uint32_t word = (uint32_t)src[offset] |
                        ((uint32_t)src[offset + 1u] << 8) |
                        ((uint32_t)src[offset + 2u] << 16) |
                        ((uint32_t)src[offset + 3u] << 24);
        if (flash_word_program(address + (uint32_t)offset, word) != FLASH_OPERATE_DONE)
        {
            flash_lock();
            return -1;
        }
    }
    flash_lock();
    return memcmp((const void *)(uintptr_t)address, src, len) == 0 ? 0 : -1;
}

int boot_platform_flash_read(uint32_t address, uint8_t *dst, size_t len)
{
    if ((dst == NULL && len != 0u) || address < OTA_APP_ORIGIN ||
        address > OTA_APP_ORIGIN + OTA_APP_LENGTH ||
        len > OTA_APP_ORIGIN + OTA_APP_LENGTH - address)
    {
        return -1;
    }
    memcpy(dst, (const void *)(uintptr_t)address, len);
    return 0;
}

int boot_platform_watchdog_start(void)
{
    wdt_register_write_enable(TRUE);
    wdt_divider_set(WDT_CLK_DIV_256);
    wdt_reload_value_set(BOOT_TEST_WATCHDOG_RELOAD);
    wdt_enable();
    wdt_counter_reload();
    return 0;
}

void boot_platform_hold(void)
{
    for (;;)
    {
        __WFI();
    }
}
