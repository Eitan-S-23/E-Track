/* Additional integration fixture; does not alter the previously bound harness. */
#define main previous_main
#include "p34_ram_writer_host.c"
#undef main

int main(int argc, char **argv)
{
    FILE *output;
    rr_io io = {NULL, source, read_nor, erase, program};
    boot_sha256_ctx_t sha;
    uint8_t pinned[32];
    if (argc != 3 || previous_main(2, argv) != 0) return 2;
    mode = 0; mutations = 0; fired = 0;
    memset(nor, 0xa5, sizeof(nor));
    boot_sha256_init(&sha);
    boot_sha256_update(&sha, image, image_len);
    boot_sha256_final(&sha, pinned);
    if (rr_run(&io, &workspace, image_len, pinned) != RR_OK) return 3;
    output = fopen(argv[2], "wb");
    if (output == NULL) return 4;
    if (fwrite(nor, 1, sizeof(nor), output) != sizeof(nor)) {
        fclose(output); return 5;
    }
    if (fclose(output) != 0) return 6;
    puts("C_WRITER_SLOT_EMITTED");
    return 0;
}
