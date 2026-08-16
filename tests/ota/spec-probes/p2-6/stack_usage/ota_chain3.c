/* 模拟 OTA apply 调用链，用于 -fstack-usage 静态栈帧求和可行性验证。
 *
 * 结构刻意贴近真实 OTA 路径：
 *   ota_apply -> ota_stage_verify -> ota_hash_block -> ota_read_chunk
 * 每层有自己的局部缓冲，链上求和才是最大 SP 下探深度的静态上界。
 *
 * P2_6_TEST_ENABLE 用来观察插桩对内联/尾调用/栈帧的影响（裁定阻断 2）。
 */

#include <stddef.h>

extern volatile unsigned int sink;
extern void ota_sink_bytes(const unsigned char *p, size_t n);

#if defined(P2_6_TEST_ENABLE)
extern void P2_6_note(unsigned tag);
/* 体积膨胀型插桩：真实 P2-6 采集点包含多字段快照与多处条件记录，代码体积
 * 显著大于一次函数调用。用 P2_6_NOTE_BULK 次记录模拟该体积，用来观察
 * 「函数体积增大 -> gcc 拒绝内联 -> 父函数栈帧变小」这条反例路径。 */
#if !defined(P2_6_NOTE_BULK)
#define P2_6_NOTE_BULK 1
#endif
#define P2_6_NOTE(tag)                                      do {                                                        unsigned k_;                                             for (k_ = 0; k_ < (unsigned)P2_6_NOTE_BULK; k_++) {             P2_6_note((tag) + k_);                               }                                                    } while (0)
#else
#define P2_6_NOTE(tag) do { } while (0)
#endif

/* 插桩快照大小可由 -DP2_6_SNAP_SIZE 覆盖，便于扫描不同插桩强度。 */
#if !defined(P2_6_SNAP_SIZE)
#define P2_6_SNAP_SIZE 96
#endif

/* 插桩构型的观测快照缓冲。真实 P2-6 插桩同样需要在采集点持有快照结构体，
 * 所以这不是人为构造 —— 它会真实改变函数体积与内联决策。 */
#if defined(P2_6_SNAPSHOT)
extern void P2_6_take_snapshot(unsigned char *buf, size_t n);
#define P2_6_SNAP()                            \
    do {                                       \
        unsigned char snap[P2_6_SNAP_SIZE];    \
        P2_6_take_snapshot(snap, sizeof(snap)); \
        ota_sink_bytes(snap, sizeof(snap));    \
    } while (0)
#else
#define P2_6_SNAP() do { } while (0)
#endif

/* 构型 C：把观测快照放进更外的校验层。函数体积增大后 gcc 可能放弃内联，
 * 使原本被折叠进父帧的局部缓冲改为独立栈帧 —— 这会翻转 .su 的分布结构。 */
#if defined(P2_6_SNAPSHOT_BIG)
extern void P2_6_take_snapshot(unsigned char *buf, size_t n);
#define P2_6_SNAP_BIG()                             \
    do {                                            \
        unsigned char snap[P2_6_SNAP_SIZE];         \
        P2_6_take_snapshot(snap, sizeof(snap));     \
        ota_sink_bytes(snap, sizeof(snap));         \
    } while (0)
#else
#define P2_6_SNAP_BIG() do { } while (0)
#endif

/* 构型 D：快照置于最内层（每次 chunk 读取都持有）。 */
#if defined(P2_6_SNAP_INNER)
extern void P2_6_take_snapshot(unsigned char *buf, size_t n);
#define P2_6_SNAP_IN()                              \
    do {                                            \
        unsigned char snap[P2_6_SNAP_SIZE];         \
        P2_6_take_snapshot(snap, sizeof(snap));     \
        ota_sink_bytes(snap, sizeof(snap));         \
    } while (0)
#else
#define P2_6_SNAP_IN() do { } while (0)
#endif

/* 最内层：读一个 chunk 到本地缓冲 */
static int ota_read_chunk(unsigned idx, unsigned char *out, size_t n)
{
    unsigned char local[64];
    size_t i;
    for (i = 0; i < sizeof(local); i++) {
        local[i] = (unsigned char)(idx + i);
    }
    for (i = 0; i < n && i < sizeof(local); i++) {
        out[i] = local[i];
    }
    P2_6_SNAP_IN();
    ota_sink_bytes(local, sizeof(local));
    return (int)n;
}

/* 中间层：哈希一个 block，持有 128B 工作缓冲 */
static int ota_hash_block(unsigned idx)
{
    unsigned char work[128];
    int rc = ota_read_chunk(idx, work, sizeof(work));
    P2_6_NOTE(1);
    P2_6_SNAP();
    ota_sink_bytes(work, sizeof(work));
    return rc;
}

/* 校验层：持有 256B 摘要上下文 */
static int ota_stage_verify(unsigned nblk)
{
    unsigned char digest_ctx[256];
    unsigned i;
    int rc = 0;
    for (i = 0; i < nblk; i++) {
        rc += ota_hash_block(i);
        digest_ctx[i & 0xFFu] = (unsigned char)rc;
    }
    P2_6_NOTE(2);
    P2_6_SNAP_BIG();
    ota_sink_bytes(digest_ctx, sizeof(digest_ctx));
    return rc;
}

/* 顶层 apply：持有 512B 头部/元数据缓冲 */
int ota_apply(unsigned nblk)
{
    unsigned char header[512];
    int rc;
    header[0] = (unsigned char)nblk;
    rc = ota_stage_verify(nblk);
    P2_6_NOTE(3);
    ota_sink_bytes(header, sizeof(header));
    sink += (unsigned)rc;
    return rc;
}
