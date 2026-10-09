#include "HardwareSerial.h"
#include "OTA/ota_ble_frame.h"
#include <stdio.h>
#include <vector>

usart_type serial_test_usarts[4];
gpio_type serial_test_gpios[2];
static unsigned checks, failures, explicit_clears, overrun_events, callbacks;
static int after_read = -1, during_callback = -1;
static std::vector<uint8_t> observed;

#define CHECK(condition) do { ++checks; if (!(condition)) { ++failures; \
    printf("FAIL line %u: %s\n", (unsigned)__LINE__, #condition); } } while (0)

static void arrive(usart_type *uart, uint8_t byte)
{
    if (uart->sts & USART_RDBF_FLAG)
    {
        ++overrun_events;
        uart->sts |= USART_ROERR_FLAG;
    }
    uart->dt = byte;
    uart->sts |= USART_RDBF_FLAG;
}

int usart_flag_get(usart_type *uart, uint32_t flag)
{
    return (uart->sts & flag) ? SET : RESET;
}

uint16_t usart_data_receive(usart_type *uart)
{
    const uint16_t value = uart->dt;
    // Vendor contract: reading DT consumes RDBF; STS then DT clears errors.
    uart->sts &= ~(USART_RDBF_FLAG | USART_PERR_FLAG | USART_FERR_FLAG |
                   USART_NERR_FLAG | USART_ROERR_FLAG | USART_IDLEF_FLAG);
    if (after_read >= 0)
    {
        const uint8_t next = (uint8_t)after_read;
        after_read = -1;
        arrive(uart, next);
    }
    return value;
}

void usart_flag_clear(usart_type *uart, uint32_t flag)
{
    ++explicit_clears;
    // AT32 RDBF is also software-clearable, including a newly arrived byte.
    uart->sts &= ~flag;
}

void usart_data_transmit(usart_type *uart, uint16_t value) { uart->dt = value; }

static void collect(HardwareSerial *serial)
{
    ++callbacks;
    while (serial->available()) observed.push_back((uint8_t)serial->read());
    if (during_callback >= 0)
    {
        const uint8_t next = (uint8_t)during_callback;
        during_callback = -1;
        arrive(serial->getUSART(), next);
    }
}

static void reset()
{
    memset(serial_test_usarts, 0, sizeof(serial_test_usarts));
    explicit_clears = overrun_events = callbacks = 0;
    after_read = during_callback = -1;
    observed.clear();
}

static void ordinary()
{
    reset();
    HardwareSerial serial(USART1);
    serial.attachInterrupt(collect);
    serial.IRQHandler();
    CHECK(observed.empty() && callbacks == 0u);
    arrive(USART1, 0x42u);
    serial.IRQHandler();
    CHECK(observed.size() == 1u && observed[0] == 0x42u);
    CHECK((USART1->sts & USART_RDBF_FLAG) == 0u);
    serial.IRQHandler();
    CHECK(observed.size() == 1u && callbacks == 1u);
    CHECK(explicit_clears == 0u);
    CHECK(overrun_events == 0u);
}

static void overlap(bool callback)
{
    reset();
    HardwareSerial serial(USART1);
    if (callback) serial.attachInterrupt(collect);
    (callback ? during_callback : after_read) = 0x52;
    arrive(USART1, 0x51u);
    serial.IRQHandler();
    CHECK((USART1->sts & USART_RDBF_FLAG) != 0u);
    // No later arrival is needed: a final pending byte must cause another IRQ.
    serial.IRQHandler();
    if (!callback)
        while (serial.available()) observed.push_back((uint8_t)serial.read());
    CHECK(observed.size() == 2u);
    CHECK(observed.size() == 2u && observed[0] == 0x51u && observed[1] == 0x52u);
    CHECK(overrun_events == 0u);
}

static void ring_behavior()
{
    reset();
    HardwareSerial serial(USART1);
    CHECK(serial.read() == -1 && serial.peek() == -1);
    for (unsigned i = 0; i < SERIAL_RX_BUFFER_SIZE + 2u; ++i)
    {
        arrive(USART1, (uint8_t)i);
        serial.IRQHandler();
    }
    CHECK(serial.available() == SERIAL_RX_BUFFER_SIZE - 1);
    CHECK(serial.peek() == 0);
    for (unsigned i = 0; i < SERIAL_RX_BUFFER_SIZE - 1u; ++i) CHECK(serial.read() == (int)i);
    CHECK(serial.read() == -1);
    for (unsigned i = 0; i < 100u; ++i)
    {
        arrive(USART1, (uint8_t)i);
        serial.IRQHandler();
        CHECK(serial.read() == (int)i);
    }
    arrive(USART1, 0x71u);
    serial.IRQHandler();
    serial.flush();
    CHECK(serial.available() == 0 && serial.peek() == -1);
}

static void frame_stream(bool inject_overlap)
{
    reset();
    HardwareSerial serial(USART1);
    serial.attachInterrupt(collect);
    std::vector<uint8_t> wire;
    uint8_t payload[132], encoded[142];
    memset(payload, 0x39, sizeof(payload));
    for (unsigned seq = 0; seq < 32u; ++seq)
    {
        const size_t length = ota_ble_frame_encode(encoded, sizeof(encoded), OTA_BLE_CMD_DATA,
                                                    1u, (uint16_t)seq, payload, sizeof(payload));
        CHECK(length == sizeof(encoded));
        wire.insert(wire.end(), encoded, encoded + length);
    }
    for (size_t index = 0; index < wire.size(); ++index)
    {
        const bool overlap_now = inject_overlap && index == 29u * sizeof(encoded) + 64u;
        if (overlap_now) during_callback = wire[index + 1u];
        arrive(USART1, wire[index]);
        serial.IRQHandler();
        if (overlap_now)
        {
            ++index;
            if (USART1->sts & USART_RDBF_FLAG) serial.IRQHandler();
        }
    }
    ota_ble_demux_t demux = {};
    ota_ble_frame_t frame = {};
    unsigned frames = 0u, errors = 0u;
    ota_ble_demux_init(&demux);
    for (size_t i = 0; i < observed.size(); ++i)
    {
        const ota_ble_parse_result_t result = ota_ble_demux_feed(&demux, observed[i], NULL, NULL, &frame);
        if (result == OTA_BLE_PARSE_FRAME) ++frames;
        if (result == OTA_BLE_PARSE_ERR_CRC || result == OTA_BLE_PARSE_ERR_FRAME) ++errors;
    }
    printf("STREAM overlap=%u expected_bytes=%u received_bytes=%u frames=%u parser_errors=%u uart_overruns=%u\n",
           inject_overlap ? 1u : 0u, (unsigned)wire.size(), (unsigned)observed.size(), frames, errors, overrun_events);
    CHECK(observed == wire);
    CHECK(frames == 32u);
    CHECK(errors == 0u);
    CHECK(overrun_events == 0u);
}

int main()
{
    ordinary();
    overlap(false);
    overlap(true);
    ring_behavior();
    frame_stream(false);
    frame_stream(true);
    printf("RESULT: %s checks=%u failures=%u\n", failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
