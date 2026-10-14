#ifndef SERIAL_TEST_ARDUINO_H
#define SERIAL_TEST_ARDUINO_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define SERIAL_RX_BUFFER_SIZE 8
#define SERIAL_CONFIG_DEFAULT SERIAL_8N1
#define SERIAL_PREEMPTIONPRIORITY_DEFAULT 0
#define SERIAL_SUBPRIORITY_DEFAULT 0
#define SERIAL_1_ENABLE 0
#define SERIAL_2_ENABLE 0
#define SERIAL_3_ENABLE 0
#define SERIAL_5_ENABLE 0
#ifndef CONFIG_OTA_BLE_PROFILE
#define CONFIG_OTA_BLE_PROFILE 0
#endif

struct serial_test_dwt_type { uint32_t CYCCNT; };
extern serial_test_dwt_type serial_test_dwt;
#define DWT (&serial_test_dwt)
enum { RESET = 0, SET = 1, FALSE = 0, TRUE = 1 };
enum usart_data_bit_num_type { USART_DATA_7BITS, USART_DATA_8BITS, USART_DATA_9BITS };
enum usart_parity_selection_type { USART_PARITY_NONE, USART_PARITY_EVEN, USART_PARITY_ODD };
enum usart_stop_bit_num_type { USART_STOP_1_BIT, USART_STOP_2_BIT, USART_STOP_0_5_BIT, USART_STOP_1_5_BIT };
enum { USART_PERR_FLAG = 1u, USART_FERR_FLAG = 2u, USART_NERR_FLAG = 4u,
       USART_ROERR_FLAG = 8u, USART_IDLEF_FLAG = 16u, USART_RDBF_FLAG = 32u,
       USART_TDBE_FLAG = 128u, USART_RDBF_INT = 32u };
struct usart_type { uint32_t sts; uint16_t dt; };
extern usart_type serial_test_usarts[4];
#define USART1 (&serial_test_usarts[0])
#define USART2 (&serial_test_usarts[1])
#define USART3 (&serial_test_usarts[2])
#define UART5 (&serial_test_usarts[3])
int usart_flag_get(usart_type *, uint32_t);
uint16_t usart_data_receive(usart_type *);
void usart_flag_clear(usart_type *, uint32_t);
void usart_data_transmit(usart_type *, uint16_t);

typedef int IRQn_Type;
enum { USART1_IRQn, USART2_IRQn, USART3_IRQn, UART5_IRQn };
enum { CRM_GPIOA_PERIPH_CLOCK, CRM_GPIOB_PERIPH_CLOCK, CRM_USART1_PERIPH_CLOCK,
       CRM_USART2_PERIPH_CLOCK, CRM_USART3_PERIPH_CLOCK, CRM_UART5_PERIPH_CLOCK };
enum { GPIO_Pin_2 = 4, GPIO_Pin_3 = 8, GPIO_Pin_8 = 256, GPIO_Pin_9 = 512,
       GPIO_Pin_10 = 1024, GPIO_Pin_11 = 2048, GPIO_DRIVE_STRENGTH_STRONGER = 0,
       GPIO_MODE_MUX = 0, GPIO_PULL_NONE = 0, GPIO_OUTPUT_PUSH_PULL = 0, GPIO_MUX_7 = 7, GPIO_MUX_8 = 8 };
struct gpio_type {};
extern gpio_type serial_test_gpios[2];
#define GPIOA (&serial_test_gpios[0])
#define GPIOB (&serial_test_gpios[1])
struct gpio_init_type { uint32_t gpio_pins, gpio_drive_strength, gpio_mode, gpio_pull, gpio_out_type; };
inline void crm_periph_clock_enable(int, int) {}
inline void gpio_default_para_init(gpio_init_type *value) { memset(value, 0, sizeof(*value)); }
inline void gpio_init(gpio_type *, gpio_init_type *) {}
inline uint16_t GPIO_GetPinSource(uint16_t value) { return value; }
inline void gpio_pin_mux_config(gpio_type *, uint16_t, int) {}
inline void usart_init(usart_type *, uint32_t, usart_data_bit_num_type, usart_stop_bit_num_type) {}
inline void usart_parity_selection_config(usart_type *, usart_parity_selection_type) {}
inline void usart_transmitter_enable(usart_type *, int) {}
inline void usart_receiver_enable(usart_type *, int) {}
inline void nvic_irq_enable(IRQn_Type, uint8_t, uint8_t) {}
inline void usart_interrupt_enable(usart_type *, uint32_t, int) {}
inline void usart_enable(usart_type *, int) {}
#endif
