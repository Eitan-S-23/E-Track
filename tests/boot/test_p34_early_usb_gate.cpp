#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <initializer_list>

#define P34_EARLY_FAULT_VECTORS 1
#define MSC_USE_SD_CARD 1
#define SD_CARD_BLOCK_SIZE 512
#define USBD_MSC_BULK_IN_EPT 0x81
#define USBD_MSC_BULK_OUT_EPT 0x01
#define MIN(a, b) ((a) < (b) ? (a) : (b))
enum usb_sts_type { USB_OK, USB_FAIL };
#include "types.inc"

static bool ready, io_ok;
static unsigned readiness_calls, revoke_at, reads, writes, capacities;
static uint32_t sectors;
namespace HAL {
bool SD_GetReady() {
    if (++readiness_calls == revoke_at) ready = false;
    return ready;
}
}
struct Card {
    uint32_t cardSize() { ++capacities; assert(ready); return sectors; }
    bool readBlocks(uint32_t, uint8_t*, uint32_t) {
        ++reads; assert(ready); return io_ok;
    }
    bool writeBlocks(uint32_t, uint8_t*, uint32_t) {
        ++writes; assert(ready); return io_ok;
    }
};
static Card card;
struct Disk { Card* card() { return &::card; } };
static Disk SD;
struct Handler { void* pdata; };
struct usbd_core_type { Handler* class_handler; };
static sense_type sense_data;
static unsigned sent_data, received_data, failed_csw, passed_csw, stalls;

static void usbd_ept_send(usbd_core_type* dev, uint8_t, uint8_t* data, uint32_t len)
{
    msc_type* state = static_cast<msc_type*>(dev->class_handler->pdata);
    if (data == reinterpret_cast<uint8_t*>(&state->csw_struct)) {
        assert(len == CSW_CMD_LENGTH);
        if (state->csw_struct.bCSWStatus == CSW_BCSWSTATUS_FAILED) ++failed_csw;
        else { assert(state->csw_struct.bCSWStatus == CSW_BCSWSTATUS_PASS); ++passed_csw; }
    } else sent_data += len;
}
static void usbd_ept_recv(usbd_core_type* dev, uint8_t, uint8_t* data, uint32_t len)
{
    msc_type* state = static_cast<msc_type*>(dev->class_handler->pdata);
    if (data != reinterpret_cast<uint8_t*>(&state->cbw_struct)) received_data += len;
}
static void usbd_set_stall(usbd_core_type*, uint8_t) { ++stalls; }
static uint32_t usbd_get_recv_len(usbd_core_type*, uint8_t) { return CBW_CMD_LENGTH; }

// Unselected opcodes are not part of this bounded fixture; the real dispatcher is included.
#define UNUSED_COMMAND(name) usb_sts_type name(void*, uint8_t) { return USB_FAIL; }
UNUSED_COMMAND(bot_scsi_inquiry)
UNUSED_COMMAND(bot_scsi_start_stop)
UNUSED_COMMAND(bot_scsi_allow_medium_removal)
UNUSED_COMMAND(bot_scsi_mode_sense6)
UNUSED_COMMAND(bot_scsi_mode_sense10)
UNUSED_COMMAND(bot_scsi_request_sense)
UNUSED_COMMAND(bot_scsi_verify)
#include "functions.inc"

struct Fixture {
    msc_type state;
    Handler handler;
    usbd_core_type device;
    Fixture(bool is_ready, uint32_t size) : state{}, handler{&state}, device{&handler} {
        ready = is_ready; sectors = size; io_ok = true;
        reads = writes = capacities = readiness_calls = revoke_at = 0;
        sent_data = received_data = failed_csw = passed_csw = stalls = 0;
        sense_data = {};
        state.blk_nbr[0] = 999; state.blk_size[0] = 512;
        std::memset(state.data, 0xFF, sizeof(state.data));
    }
    void command(uint8_t opcode, unsigned blocks = 1, uint32_t lba = 0) {
        state.msc_state = MSC_STATE_MACHINE_IDLE;
        state.data_len = 77;
        state.cbw_struct = {};
        state.cbw_struct.dCBWSignature = CBW_DCBWSIGNATURE;
        state.cbw_struct.bCBWCBLength = 10;
        state.cbw_struct.bmCBWFlags = opcode == MSC_CMD_WRITE_10 ? 0 : 0x80;
        state.cbw_struct.CBWCB[0] = opcode;
        for (unsigned i = 0; i < 4; ++i) state.cbw_struct.CBWCB[2+i] = lba >> (24-8*i);
        state.cbw_struct.CBWCB[7] = blocks >> 8;
        state.cbw_struct.CBWCB[8] = blocks;
        state.cbw_struct.dCBWDataTransferLength = opcode == MSC_CMD_TEST_UNIT ? 0 :
            opcode == MSC_CMD_READ_CAPACITY ? 8 : opcode == MSC_CMD_READ_FORMAT_CAPACITY ? 12 : blocks*512;
        bot_cbw_decode(&device);
    }
    void prime() {
        assert(bot_scsi_capacity(&device, 0) == USB_OK);
        assert(state.blk_nbr[0] == sectors && state.blk_size[0] == 512);
    }
    void unavailable() {
        assert(reads == 0 && writes == 0 && capacities == 0);
        assert(state.blk_nbr[0] == 0 && state.blk_size[0] == 0 && state.data_len == 0);
        assert(state.csw_struct.bCSWStatus == CSW_BCSWSTATUS_FAILED);
        assert(sense_data.sense_key == SENSE_KEY_NOT_READY && sense_data.asc == MEDIUM_NOT_PRESENT);
        assert(sent_data == 0 && passed_csw == 0 && stalls != 0);
        for (unsigned i = 0; i < 12; ++i) assert(state.data[i] == 0);
    }
};

int main()
{
    unsigned cases = 0;
    const uint8_t commands[] = {MSC_CMD_TEST_UNIT, MSC_CMD_READ_CAPACITY,
        MSC_CMD_READ_FORMAT_CAPACITY, MSC_CMD_READ_10, MSC_CMD_WRITE_10};
    // Cold, capacity-known initializing, failed initialization and absent media.
    for (unsigned state = 0; state < 4; ++state) for (uint8_t command : commands) {
        Fixture f(false, state == 1 || state == 2 ? 8192 : 0);
        f.command(command); f.unavailable(); ++cases;
    }
    for (uint8_t command : commands) {
        Fixture f(true, 8192); f.prime(); f.command(command);
        assert(stalls == 0 && failed_csw == 0);
        if (command == MSC_CMD_WRITE_10) bot_scsi_dataout_handler(&f.device, 1);
        assert(command != MSC_CMD_READ_10 || reads == 1);
        assert(command != MSC_CMD_WRITE_10 || writes == 1);
        ++cases;
    }
    for (uint8_t command : commands) {
        Fixture f(true, 8192); f.prime(); ready = false; capacities = 0;
        f.command(command); f.unavailable(); ++cases;
    }
    for (uint8_t command : {uint8_t(MSC_CMD_READ_CAPACITY), uint8_t(MSC_CMD_READ_FORMAT_CAPACITY)}) {
        Fixture f(true, 0); f.command(command);
        assert(f.state.blk_nbr[0] == 0 && f.state.blk_size[0] == 0 && f.state.data_len == 0);
        assert(sent_data == 0 && stalls && passed_csw == 0); ++cases;
    }
    for (uint8_t command : {uint8_t(MSC_CMD_READ_10), uint8_t(MSC_CMD_WRITE_10)}) {
        Fixture f(true, 8192); f.prime(); f.command(command, 1, 8192);
        assert(reads == 0 && writes == 0 && stalls && passed_csw == 0); ++cases;
    }
    {
        Fixture f(true, 8192); f.prime(); f.command(MSC_CMD_READ_10, 16);
        assert(reads == 1 && sent_data == 4096 && f.state.csw_struct.dCSWDataResidue == 4096);
        ready = false; bot_scsi_datain_handler(&f.device, 1);
        assert(reads == 1 && sent_data == 4096 && failed_csw == 1 && passed_csw == 0);
        assert(f.state.csw_struct.dCSWDataResidue == 4096 && f.state.data_len == 0); ++cases;
    }
    {
        Fixture f(true, 8192); f.prime(); f.command(MSC_CMD_WRITE_10, 16);
        bot_scsi_dataout_handler(&f.device, 1);
        assert(writes == 1 && f.state.csw_struct.dCSWDataResidue == 4096);
        ready = false; bot_scsi_dataout_handler(&f.device, 1);
        assert(writes == 1 && failed_csw == 1 && passed_csw == 0);
        assert(f.state.csw_struct.dCSWDataResidue == 4096 && f.state.data_len == 0); ++cases;
    }
    {
        Fixture f(true, 8192); f.prime(); f.command(MSC_CMD_WRITE_10);
        ready = false; bot_scsi_dataout_handler(&f.device, 1);
        assert(writes == 0 && failed_csw == 1 && passed_csw == 0); ++cases;
    }
    for (uint8_t command : {uint8_t(MSC_CMD_READ_10), uint8_t(MSC_CMD_WRITE_10)}) {
        Fixture f(true, 8192); f.prime(); io_ok = false; f.command(command);
        if (command == MSC_CMD_WRITE_10) bot_scsi_dataout_handler(&f.device, 1);
        assert(f.state.csw_struct.bCSWStatus == CSW_BCSWSTATUS_FAILED && passed_csw == 0);
        assert(sense_data.sense_key == SENSE_KEY_MEDIUM_ERROR);
        assert(f.state.data_len == 0 && f.state.csw_struct.dCSWDataResidue == 512); ++cases;
    }
    {
        Fixture f(true, 8192); f.prime(); readiness_calls = 0; revoke_at = 2;
        f.command(MSC_CMD_READ_10);
        assert(reads == 0 && passed_csw == 0 && stalls); ++cases;
    }
    std::printf("EARLY_USB_GATE_PASS cases=%u\n", cases);
}
