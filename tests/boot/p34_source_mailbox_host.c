#include "source_mailbox.h"
#include "boot_crypto.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static rr_source_mailbox box;
static rr_source source;
static uint32_t tick, last, deliveries;
static int mode;
static uint8_t input[9000];

static uint32_t now(void *ctx)
{
    uint32_t i, seq = box.request_commit;
    (void)ctx;
    ++tick;
    if (!seq || seq == last || mode == 1) return tick;
    last = seq; ++deliveries;
    box.response_commit = 0;
    box.response_generation[0] = box.generation[0];
    box.response_generation[1] = box.generation[1];
    box.response_offset = box.request_offset;
    box.response_length = box.request_length;
    for (i = 0; i < box.request_length; ++i) box.response_data[i] = input[box.request_offset+i];
    box.response_crc = boot_crc32(input+box.request_offset,box.request_length);
    if (mode == 2) ++box.response_generation[0];
    if (mode == 3) ++box.response_offset;
    if (mode == 4) --box.response_length;
    if (mode == 5) box.response_data[0] ^= 1u;
    box.response_commit = mode == 6 ? seq+1u : seq;
    return tick;
}

static void init(void)
{
    uint32_t generation[2] = {0x11223344,0x55667788};
    memset(&box,0xa5,sizeof(box));
    last = deliveries = 0; tick = UINT32_MAX-5u;
    assert(rr_source_init(&source,&box,sizeof(input),generation,20u,now,NULL) == 0);
}

int main(void)
{
    uint8_t result[4096];
    unsigned i, cases = 0;
    for (i = 0; i < sizeof(input); ++i) input[i] = (uint8_t)(i*37u);
    mode = 0; init();
    assert(rr_source_read(&source,1024,result,96) == 0 && deliveries == 1);
    assert(memcmp(result,input+1024,96) == 0); ++cases;
    assert(rr_source_read(&source,0,result,256) == 0 && deliveries == 1); ++cases;
    assert(rr_source_read(&source,4000,result,4096) == 0 && deliveries == 2);
    assert(memcmp(result,input+4000,4096) == 0); ++cases;
    assert(rr_source_read(&source,8192,result,808) == 0 && deliveries == 3);
    assert(memcmp(result,input+8192,808) == 0); ++cases;
    for (mode = 1; mode <= 6; ++mode) {
        uint32_t requests;
        init(); assert(rr_source_read(&source,0,result,32) == -1 && source.failed);
        requests = box.request_commit;
        assert(rr_source_read(&source,0,result,32) == -1 && box.request_commit == requests);
        ++cases;
    }
    mode = 0; init();
    assert(rr_source_read(&source,UINT32_MAX,result,2) == -1 && !box.request_commit); ++cases;
    init(); assert(rr_source_read(&source,8999,result,2) == -1 && !box.request_commit); ++cases;
    init(); source.sequence = UINT32_MAX;
    assert(rr_source_read(&source,0,result,1) == -1 && !box.request_commit); ++cases;
    printf("SOURCE_MAILBOX_HOST_PASS cases=%u\n",cases);
    return 0;
}
