#include <stdio.h>
#include <string.h>
#include "OTA/ota_ble_frame.h"
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

int main(void)
{
    ota_ble_demux_t demux = {0};
    ota_ble_frame_t frame;
    unsigned count = 0;
    int value;
#ifdef _WIN32
    if (_setmode(_fileno(stdin), _O_BINARY) == -1)
        return 5;
#endif
    ota_ble_demux_init(&demux);
    while ((value = getchar()) != EOF)
    {
        ota_ble_parse_result_t result = ota_ble_demux_feed(
            &demux, (uint8_t)value, NULL, NULL, &frame);
        unsigned i;
        if (result == OTA_BLE_PARSE_IDLE)
            continue;
        if (result != OTA_BLE_PARSE_FRAME || count >= 3 ||
            frame.cmd != OTA_BLE_CMD_DATA || frame.session != 7 ||
            frame.seq != count + 1 || frame.len != 132)
            return 1;
        if (frame.payload[0] != (uint8_t)(count * 128) ||
            frame.payload[1] != (uint8_t)((count * 128) >> 8) ||
            frame.payload[2] != 0 || frame.payload[3] != 0)
            return 2;
        for (i = 4; i < 132; ++i)
            if (frame.payload[i] != (uint8_t)(i - 4 + count))
                return 3;
        ++count;
    }
    if (ferror(stdin) || count != 3 || demux.state != OTA_BLE_DEMUX_IDLE ||
        demux.parser.bad_frames != 0)
        return 4;
    puts("PASS: original MCU demux accepted three unchanged DATA frames");
    return 0;
}
