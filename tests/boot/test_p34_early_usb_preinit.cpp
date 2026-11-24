#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>

#define MSC_USE_SD_CARD
#define SD_CARD_BLOCK_SIZE 512
#define MSC_MAX_DATA_BUF_LEN 512
#define MIN(a, b) ((a) < (b) ? (a) : (b))

enum usb_sts_type { USB_OK, USB_FAIL };
enum { MSC_STATE_MACHINE_IDLE, MSC_STATE_MACHINE_DATA_IN, MSC_STATE_MACHINE_LAST_DATA };
enum { SENSE_KEY_ILLEGAL_REQUEST, ADDRESS_OUT_OF_RANGE, INVALID_COMMAND,
       SENSE_KEY_HARDWARE_ERROR, MEDIUM_NOT_PRESENT, USBD_MSC_BULK_IN_EPT };

static unsigned backend_calls;
static bool backend_ready;
static uint32_t capacity;
struct Card {
    uint32_t cardSize() { return capacity; }
    bool readBlocks(uint32_t, uint8_t*, uint32_t) {
        ++backend_calls;
        return backend_ready;
    }
};
static Card card;
struct Disk { Card* card() { return &::card; } };
static Disk SD;

struct Cbw {
    uint8_t bmCBWFlags;
    uint8_t CBWCB[16];
    uint32_t dCBWDataTransferLength;
};
struct msc_type {
    uint8_t data[512];
    uint32_t blk_nbr[1], blk_size[1], data_len, blk_addr, blk_len;
    int msc_state;
    Cbw cbw_struct;
    struct { uint32_t dCSWDataResidue; } csw_struct;
};
struct Class { void* pdata; };
struct usbd_core_type { Class* class_handler; };

static void bot_scsi_sense_code(void*, int, int) {}
static void usbd_ept_send(void*, int, uint8_t*, uint32_t) {}

// Exact function bodies extracted from the source-bound ON snapshot.
#include "functions.inc"

static void scenario(uint32_t sectors, bool ready, bool out_of_range,
                     unsigned expected_calls, usb_sts_type expected_result)
{
    capacity = sectors;
    backend_ready = ready;
    backend_calls = 0;
    msc_type state = {};
    Class handler = {&state};
    usbd_core_type device = {&handler};
    // The existing capacity command returns USB_OK even when the backend has no capacity.
    assert(bot_scsi_capacity(&device, 0) == USB_OK);
    state.cbw_struct.bmCBWFlags = 0x80;
    state.cbw_struct.CBWCB[8] = 1;
    state.cbw_struct.dCBWDataTransferLength = 512;
    if (out_of_range) {
        state.cbw_struct.CBWCB[4] = 0x20; // LBA 8192 with capacity 8192.
    }
    assert(bot_scsi_read10(&device, 0) == expected_result);
    assert(backend_calls == expected_calls);
}

int main()
{
    scenario(0, false, false, 0, USB_FAIL);
    scenario(8192, false, false, 1, USB_FAIL);
    scenario(8192, true, false, 1, USB_OK);
    scenario(8192, false, true, 0, USB_FAIL);
    std::puts("EARLY_USB_PREINIT_WITNESS cases=4 backend_called_before_ready=1");
}
