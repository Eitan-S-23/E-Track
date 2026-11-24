#include "confirm.h"
#include "boot_state_machine.h"
#include "boot_crypto.h"
#include <string.h>

static const uint8_t (*arbitration_pair)[BCB_SIZE];
static const rc_plan *active_plan;
static const rc_request *active_request;
static const bcb_hal_t *raw_hal;
static rc_result *active_result;
static uint8_t target_pair[2][BCB_SIZE];
static unsigned target_slot;
static int drift;

static int pair_read(uint8_t address, uint8_t *data, uint16_t length)
{
    if (length != BCB_SIZE || (address != 0 && address != 64)) return -1;
    memcpy(data,arbitration_pair[address == 64],length); return 0;
}

static bcb_arbiter_result_t arbitrate(const uint8_t pair[2][BCB_SIZE], bcb_t *value)
{
    bcb_hal_t hal = {0,pair_read};
    arbitration_pair = pair;
    return bcb_arbiter(&hal,value);
}

static int read_pair(const bcb_hal_t *hal, uint8_t pair[2][BCB_SIZE])
{
    return hal->read_buffer(0,pair[0],BCB_SIZE) == 0 &&
           hal->read_buffer(64,pair[1],BCB_SIZE) == 0;
}

static int pinned(const uint8_t *data, size_t length, const char *hex)
{
    static const char digits[] = "0123456789abcdef";
    boot_sha256_ctx_t sha;
    uint8_t digest[32];
    unsigned i;
    boot_sha256_init(&sha); boot_sha256_update(&sha,data,length); boot_sha256_final(&sha,digest);
    for (i = 0; i < 32; ++i)
        if (digits[digest[i] >> 4] != hex[2*i] || digits[digest[i] & 15] != hex[2*i+1]) return 0;
    return 1;
}

static int image_read(void *ctx, uint32_t address, uint8_t *data, size_t length)
{
    uint32_t offset;
    (void)ctx;
    if (address < OTA_APP_ORIGIN) return -1;
    offset = address-OTA_APP_ORIGIN;
    if (offset > active_request->image_length || length > active_request->image_length-offset) return -1;
    memcpy(data,active_request->image+offset,length); return 0;
}

static int guarded_read(uint8_t address, uint8_t *data, uint16_t length)
{
    if (length != BCB_SIZE || (address != 0 && address != 64) ||
        raw_hal->read_buffer(address,data,length) != 0) return -1;
    if (!active_result->write_attempts &&
        memcmp(data,active_plan->before[address == 64],length) != 0) {
        drift = 1; return -1;
    }
    return 0;
}

static int guarded_write(uint8_t address, const uint8_t *data, uint16_t length)
{
    uint8_t pair[2][BCB_SIZE];
    if (drift || active_result->write_attempts || address != target_slot*64u || length != BCB_SIZE ||
        memcmp(data,target_pair[target_slot],BCB_SIZE) != 0) return -1;
    /* Recheck the complete pre-state immediately before the only permitted
     * host write. Exclusive ownership is still required across the bus call. */
    if (!read_pair(raw_hal,pair) || memcmp(pair,active_plan->before,sizeof(pair)) != 0) {
        drift = 1; return -1;
    }
    ++active_result->write_attempts;
    return raw_hal->write_buffer(address,data,length);
}

rc_status rc_confirm(const rc_plan *plan, const rc_request *request,
                     const bcb_hal_t *hal, rc_result *result)
{
    bcb_t initial, wanted, observed;
    bcb_arbiter_result_t selected, final;
    bcb_hal_t guard = {guarded_write,guarded_read};
    boot_state_io_t io;
    boot_state_outcome_t ignored_outcome;
    uint8_t repeated[2][BCB_SIZE], canonical[BCB_SIZE];
    unsigned original_slot;
    int already;
    if (!result) return RC_REJECTED;
    memset(result,0,sizeof(*result)); result->active = BCB_ARBITER_ERROR;
    if (!plan || !request || !hal || !hal->read_buffer || !hal->write_buffer ||
        !request->boot || !request->image || request->boot_length != 65536u ||
        request->image_length != 619580u || memcmp(plan->operation,request->operation,16) != 0)
        return RC_REJECTED;
    if (!pinned(request->boot,request->boot_length,
        "a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4") ||
        !pinned(request->image,request->image_length,
        "7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf")) return RC_REJECTED;
    selected = arbitrate(plan->before,&initial);
    if ((selected != BCB_ARBITER_A && selected != BCB_ARBITER_B) ||
        initial.state != BCB_STATE_CONFIRMED || initial.copy_phase != BCB_COPY_NONE ||
        initial.resume_block != 0 || (initial.cur_vcode != 30275u && initial.cur_vcode != 30276u))
        return RC_REJECTED;
    original_slot = selected == BCB_ARBITER_B;
    bcb_serialize(&initial,canonical);
    if (initial.reserved != 0 || initial.boot_try > BCB_INIT_BOOT_TRY ||
        memcmp(canonical,plan->before[original_slot],BCB_SIZE) != 0) return RC_REJECTED;
    target_slot = 1u-original_slot;
    memcpy(target_pair,plan->before,sizeof(target_pair));
    wanted = initial;
    wanted.state = BCB_STATE_CONFIRMED; wanted.boot_try = 0;
    wanted.copy_phase = BCB_COPY_NONE; wanted.resume_block = 0; wanted.cur_vcode = 30276u;
    already = initial.cur_vcode == 30276u && initial.boot_try == 0;
    if (!already) {
        wanted.seq = (uint16_t)(initial.seq+1u);
        bcb_serialize(&wanted,target_pair[target_slot]);
    }
    if (!read_pair(hal,result->before)) return RC_UNKNOWN;
    result->before_read = 1;
    if (memcmp(result->before,target_pair,sizeof(target_pair)) == 0) {
        if (!read_pair(hal,repeated)) return RC_UNKNOWN;
        if (memcmp(repeated,target_pair,sizeof(target_pair)) != 0) return RC_REJECTED;
        memcpy(result->after,repeated,sizeof(repeated)); result->after_read = 1;
        result->active = arbitrate(repeated,&observed);
        return RC_ALREADY;
    }
    if (already || memcmp(result->before,plan->before,sizeof(result->before)) != 0) return RC_REJECTED;
    active_plan = plan; active_request = request; raw_hal = hal; active_result = result; drift = 0;
    memset(&io,0,sizeof(io)); io.bcb_hal = &guard; io.internal_read = image_read;
    result->transaction_status = boot_state_machine_accept_physical_recovery(&io,&ignored_outcome);
    /* The kernel return/outcome is deliberately NOT the success oracle. */
    if (!read_pair(hal,result->after) || !read_pair(hal,repeated)) return RC_UNKNOWN;
    result->after_read = 1;
    if (memcmp(result->after,repeated,sizeof(repeated)) != 0) return RC_UNKNOWN;
    if (drift && !result->write_attempts) return RC_REJECTED;
    final = arbitrate(result->after,&observed); result->active = final;
    if (memcmp(result->after,target_pair,sizeof(target_pair)) == 0 &&
        final == (target_slot ? BCB_ARBITER_B : BCB_ARBITER_A)) return RC_CONFIRMED;
    if (final == selected &&
        memcmp(result->after[original_slot],plan->before[original_slot],BCB_SIZE) == 0)
        return RC_NOT_CONFIRMED;
    return RC_UNKNOWN;
}
