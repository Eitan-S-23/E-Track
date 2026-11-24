#define main previous_main
#include "p34_ram_writer_host.c"
#undef main
#include "source_mailbox.h"

static rr_source_mailbox mailbox;
static rr_source channel;
static uint32_t ticks, served, deliveries;
static int delivery_mode;

static uint32_t clock_now(void *ctx)
{
    uint32_t seq = mailbox.request_commit, i;
    uint8_t data[4096];
    (void)ctx;
    ++ticks;
    if (!seq || seq == served) return ticks;
    served = seq; ++deliveries;
    assert(mailbox.request_offset <= image_len && mailbox.request_length <= image_len-mailbox.request_offset);
    memcpy(data,image+mailbox.request_offset,mailbox.request_length);
    if (delivery_mode == 1 && mutations) data[0] ^= 1u;
    mailbox.response_commit = 0;
    mailbox.response_generation[0] = mailbox.generation[0];
    mailbox.response_generation[1] = mailbox.generation[1];
    if (delivery_mode == 2) ++mailbox.response_generation[0];
    mailbox.response_offset = mailbox.request_offset;
    mailbox.response_length = mailbox.request_length;
    mailbox.response_crc = boot_crc32(data,mailbox.request_length);
    for (i = 0; i < mailbox.request_length; ++i) mailbox.response_data[i] = data[i];
    mailbox.response_commit = seq;
    return ticks;
}

static int mailbox_read(void *ctx, uint32_t offset, uint8_t *dst, uint32_t length)
{
    (void)ctx;
    return rr_source_read(&channel,offset,dst,length);
}

int main(int argc, char **argv)
{
    rr_io io = {NULL,mailbox_read,read_nor,erase,program};
    boot_sha256_ctx_t sha;
    uint8_t pinned[32];
    uint32_t generation[2] = {0x12345678,0x9abcdef0};
    FILE *out;
    int result;
    if (argc != 3 || previous_main(2,argv) != 0) return 2;
    boot_sha256_init(&sha); boot_sha256_update(&sha,image,image_len); boot_sha256_final(&sha,pinned);
    for (delivery_mode = 0; delivery_mode < 3; ++delivery_mode) {
        mode = 0; mutations = fired = 0;
        ticks = served = deliveries = 0;
        memset(nor,0xa5,sizeof(nor));
        assert(rr_source_init(&channel,&mailbox,image_len,generation,20u,clock_now,NULL) == 0);
        result = rr_run(&io,&workspace,image_len,pinned);
        if (delivery_mode == 0) {
            assert(result == RR_OK && memcmp(nor+4096,image,image_len) == 0);
            out = fopen(argv[2],"wb"); assert(out != NULL);
            assert(fwrite(nor,1,sizeof(nor),out) == sizeof(nor)); assert(fclose(out) == 0);
        } else if (delivery_mode == 1) {
            assert(result == RR_SOURCE && mutations == 1u);
        } else {
            assert(result == RR_SOURCE && mutations == 0u);
        }
        printf("MAILBOX_WRITER mode=%d rc=%d requests=%lu writes=%lu\n",delivery_mode,result,
               (unsigned long)deliveries,(unsigned long)mutations);
    }
    puts("MAILBOX_WRITER_HOST_PASS cases=3");
    return 0;
}
