/* 支撑文件：把缓冲送进 volatile sink，防止优化掉局部数组导致栈帧归零。 */

#include <stddef.h>

volatile unsigned int sink;

void ota_sink_bytes(const unsigned char *p, size_t n)
{
    size_t i;
    unsigned acc = 0;
    for (i = 0; i < n; i++) {
        acc += p[i];
    }
    sink += acc;
}

#if defined(P2_6_TEST_ENABLE)
volatile unsigned int P2_6_notes;

void P2_6_note(unsigned tag)
{
    P2_6_notes += tag;
}
#endif

#if defined(P2_6_SNAPSHOT) || defined(P2_6_SNAPSHOT_BIG) \
    || defined(P2_6_SNAP_INNER)
void P2_6_take_snapshot(unsigned char *buf, size_t n)
{
    size_t i;
    for (i = 0; i < n; i++) {
        buf[i] = (unsigned char)(sink + i);
    }
}
#endif

