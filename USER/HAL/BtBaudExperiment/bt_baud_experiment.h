/*
 * P3-4 波特率实验控制模块（仅实验构型；生产构型不包含本头文件）
 *
 * 设计约束（来自 P3-4 host 整改提示词）：
 * 1) 观测记录用显式长度的字节缓冲，不用 %s；封存后不可再拼接；一条记录
 *    编码后以一次 SEGGER_RTT_Write 输出，只有返回值等于记录长度才算成功，
 *    拒写时保留待发记录。
 * 2) 下行命令必须整行校验后才执行：超长/含非法字节整条拒绝并持续消费到
 *    行尾；busy 期继续有界消费并丢弃，清除半行与待执行命令，不做延迟补执行。
 * 3) 控制 epoch 必须接到真实会话获取/释放边界（由平台 op 提供），执行副作用
 *    前再次确认 epoch 与空闲所有权。epoch 变化**主动作废**授权性证据
 *    （KNOWN/deferred/set-ineffective 与两侧证据槽），而不是只拒绝「带旧
 *    epoch 的命令」：命令可以带当前 epoch 发出，过期证据却仍会放行改速、
 *    重启与恢复完成判定。作废后 known_baud 仅作上电观测提示。
 * 4) 本地只调 MCU UART 速率，不发模块改速命令；切换前有界等待 TX 真正完成。
 * 5) 切速/恢复使用显式 KNOWN/PENDING/UNKNOWN 状态机，探针有界，证据绑定
 *    baud/epoch/记录序号/查询窗口。
 * 6) 参数解析必须 fail-closed：十进制逐位累加并检查溢出，超范围输入整条拒绝，
 *    不得靠 uint32 回绕变成“恰好合法”的 epoch 或白名单速率。
 * 7) 模块应答必须按手册形态整行解析：行首 `[+]UART` + 合法数字 + 合法结尾才
 *    算有效，非法后缀、超长数字、两个互相冲突的数值、`AT+UART=` 回显一律判无效；
 *    版本查询同理，不接受回显或任意含关键字文本。
 * 8) KNOWN 态收到矛盾证据（本机速率上模块报别的档位）不得只记日志后继续保留
 *    改速资格：矛盾即失效并重新取证。
 * 9) 原始 AT 文本入口按白名单收窄（本操作单只放行 `AT+REBOOT=1`）：改速走受控
 *    `rate set`，查询走受控 `probe`，禁止通用入口绕过状态/epoch/busy/速率约束；
 *    重启只能在受控 deferred 分支内发出。代码允许不等于外部设备已获授权。
 * 10) 本地重配失败必须区分“切换前失败、硬件确实未变”（可保留旧速率）与“已重配
 *    但回读失败/超差、实际状态不确定”（必须作废 mcu_baud 并回到 UNKNOWN）。
 * 11) 探针预算按 step 隔离的档位位图计数，**接受即计数**：通过门禁即置位，
 *    其后超时/中止/切换失败均不退额；第二证据必须显式 `rate rearm`。在飞期间
 *    的 `rate set`/`rate rearm` 一律拒绝，step 漂移的旧探针结果按 step 作废。
 *    固件局部限制不代替执行者的累计操作台账。
 *
 * 本文件是 header-only 的平台无关模块：目标固件由 USER/HAL/HAL_Bluetooth.cpp
 * 以真实 op 接入；host 自测编译同一个头文件，只把 I/O 与时间替换为替身。
 * 测试因此执行的是实际决策代码，而不是另写的成功流程。
 */
#ifndef E_TRACK_BT_BAUD_EXPERIMENT_H
#define E_TRACK_BT_BAUD_EXPERIMENT_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* ===================== 编译期常量 ===================== */

#define BT_BX_RX_CAP        192u  /* 单条观测记录的最大原始字节数 */
#define BT_BX_LINE_CAP       80u  /* 下行命令行容量（含结尾 NUL 之前） */
#define BT_BX_REC_SLOTS       4u  /* 待发记录槽位数（RTT 拒写时保留） */
#define BT_BX_QUIET_MS      120u  /* 静默分帧窗口 */
#define BT_BX_QUERY_MS     3000u  /* 单条查询等待上限 */
#define BT_BX_TX_DRAIN_MS  1000u  /* 切换前等待最后一位发完的上限 */
#define BT_BX_BUSY_DISCARD   64u  /* busy 期单次 poll 有界丢弃字节上限 */
#define BT_BX_LOG_CAP       320u  /* 单条日志/状态行缓冲。status 行字段最多，
                                   * 各计数用满 9-10 位十进制时接近 275 字节，
                                   * 256 会在长会话（大计数）时整行丢弃。 */

/* 记录线上编码上界：`BXRX(<seq> b=<baud> e=<epoch> [OVF ][STALE ]len=<n>): <HEX>\r\n`
 * 5+10+3+6+3+10+1+4+6+4+3+3+2*192+2 = 444。必须小于实际 RTT 上行环容量。 */
#define BT_BX_WIRE_MAX (BT_BX_RX_CAP * 2u + 64u)

/* 可选编译期核对：实际 RTT 上行环容量必须大于记录上界。 */
#ifdef BT_BX_RTT_CAP
typedef char bt_bx_rtt_cap_assert[(BT_BX_WIRE_MAX < BT_BX_RTT_CAP) ? 1 : -1];
#endif

/* ===================== 速率档位表（升序） ===================== */

#define BT_BX_RATE_N 4u

typedef struct
{
    uint32_t baud; /* 实际线路速率 */
    uint32_t idx;  /* 手册 AT+UART=N 的档位序号 */
} bt_bx_rate_t;

static const bt_bx_rate_t bt_bx_rates[BT_BX_RATE_N] =
{
    {115200u, 5u},
    {230400u, 6u},
    {460800u, 7u},
    {921600u, 8u}
};

static uint32_t bt_bx_rate_idx(uint32_t baud)
{
    unsigned i;
    for (i = 0u; i < BT_BX_RATE_N; ++i)
    {
        if (bt_bx_rates[i].baud == baud)
        {
            return bt_bx_rates[i].idx;
        }
    }
    return 0u;
}

static uint32_t bt_bx_rate_baud(uint32_t idx)
{
    unsigned i;
    for (i = 0u; i < BT_BX_RATE_N; ++i)
    {
        if (bt_bx_rates[i].idx == idx)
        {
            return bt_bx_rates[i].baud;
        }
    }
    return 0u;
}

static int bt_bx_rate_known(uint32_t baud)
{
    return bt_bx_rate_idx(baud) != 0u;
}

/* 档位表下标（0..BT_BX_RATE_N-1）；非白名单速率返回 BT_BX_RATE_N。 */
static unsigned bt_bx_rate_slot(uint32_t baud)
{
    unsigned i;

    for (i = 0u; i < BT_BX_RATE_N; ++i)
    {
        if (bt_bx_rates[i].baud == baud)
        {
            return i;
        }
    }
    return (unsigned)BT_BX_RATE_N;
}

/* ===================== 状态机枚举 ===================== */

typedef enum
{
    BT_BX_STATE_UNKNOWN = 0, /* 无有效证据或证据矛盾：停止设置与下一档实验 */
    BT_BX_STATE_KNOWN   = 1, /* 已确认某速率上可通信且模块配置一致 */
    BT_BX_STATE_PENDING = 2  /* 已发送一次设置命令，结果未定 */
} bt_bx_rate_state_t;

typedef enum
{
    BT_BX_ABORT_NONE    = 0,
    BT_BX_ABORT_SESSION = 1, /* OTA 会话/ISR 活跃 */
    BT_BX_ABORT_EPOCH   = 2, /* 会话代次变化 */
    BT_BX_ABORT_BAUD    = 3, /* 本地速率被改动 */
    BT_BX_ABORT_STEP    = 4  /* 所属 step 已前进：旧 step 证据作废 */
} bt_bx_abort_t;

/* ===================== 平台操作（唯一硬件边界） ===================== */

typedef struct bt_bx_ops_t
{
    void *io;

    uint32_t (*now_ms)(void *io);
    /* 1 = 会话活跃或 ISR 活跃（此时禁止任何观测输出与下行执行） */
    int (*busy)(void *io);
    /* 真实会话代次：必须在会话获取/释放边界递增，而非周期轮询推断 */
    uint32_t (*epoch)(void *io);
    /* 读 RTT 下行；返回读到的字节数 */
    unsigned (*rtt_read)(void *io, char *dst, unsigned cap);
    /* 写 RTT 上行（NO_BLOCK_SKIP）；返回实际写入字节数 */
    unsigned (*rtt_write)(void *io, const char *src, unsigned len);
    /* 向模块写一行 AT：自行追加手册行尾 \r\n；返回写入字节数 */
    unsigned (*at_write)(void *io, const char *text, unsigned len);
    /* 本地 MCU UART 切速：先有界等待 TX 完成，再清 RX 残留并重配。
     * 返回 0 成功；-1 TX 完成等待超时（未动硬件）；-2 非法/不支持（未动硬件）；
     * -3 已调用 begin() 但回读失败/超差——**重配后实际状态不确定**；
     * -4 前置检查失败（未动硬件）。-1/-2/-4 可安全保留原速率，-3 不可。 */
    int (*mcu_set_baud)(void *io, uint32_t baud);
    /* 复位 demux 残留（调用方保证此刻 OTA 空闲） */
    void (*reset_demux)(void *io);
} bt_bx_ops_t;

/* ===================== 观测记录 ===================== */

typedef struct
{
    uint8_t  data[BT_BX_RX_CAP];
    uint16_t len;
    uint8_t  ovf;  /* 采集期缓冲满：记录不完整，不得充当应答证据 */
    uint8_t  held; /* 已封存待输出 */
    uint32_t seq;
    uint32_t baud; /* 采集时 MCU 速率 */
    uint32_t epoch;
} bt_bx_record_t;

/* ===================== 探针与证据 ===================== */

typedef struct
{
    uint8_t  attempted;
    uint8_t  comm_ok;         /* 在该速率上收到连贯应答 */
    uint8_t  reported_valid;  /* 应答中解析出模块配置序号 */
    uint8_t  reported_mapped; /* 该序号可映射到已知档位 */
    uint32_t reported_idx;
    uint32_t reported_baud;
    uint32_t seq; /* 承认为证据的记录序号（0 = 无） */
} bt_bx_ev_t;

typedef struct
{
    uint8_t  active;
    uint8_t  leg; /* 0 = AT+UART?，1 = AT+VER? */
    uint8_t  window_armed; /* 1 = 本 leg 窗口已建立，记录可参与判定 */
    uint8_t  aborted;
    uint8_t  started;
    uint8_t  comm_ok;
    uint8_t  reported_valid;
    uint8_t  reported_mapped;
    uint32_t reported_idx;
    uint32_t reported_baud;
    uint32_t baud;
    uint32_t epoch_at_start;
    uint32_t step_at_start;
    uint32_t uart_seq;
    uint32_t ver_seq;
    uint32_t leg_sent_ms;
    uint32_t leg_seq_floor; /* 本 leg 窗口的最小记录序号（排除旧日志） */
} bt_bx_probe_t;

/* ===================== 模块上下文 ===================== */

typedef struct
{
    const bt_bx_ops_t *ops;
    uint32_t mcu_baud;

    /* 采集缓冲（封存后清空，绝不与新数据拼接） */
    uint8_t  cap[BT_BX_RX_CAP];
    uint16_t cap_len;
    uint8_t  cap_ovf;
    uint32_t cap_last_ms;
    uint32_t cap_baud;
    uint32_t cap_epoch;

    /* 待发记录环 */
    bt_bx_record_t q[BT_BX_REC_SLOTS];
    uint8_t  q_head;
    uint8_t  q_count;
    uint32_t next_seq;

    /* 下行命令行 */
    char     line[BT_BX_LINE_CAP];
    uint16_t line_len;
    uint8_t  line_over; /* 超长：整行拒绝 */
    uint8_t  line_bad;  /* 含 NUL/非法控制字符：整行拒绝 */

    /* 计数（常驻 RAM，不因日志拥塞丢失） */
    uint32_t rx_bytes;
    uint32_t rec_emitted;
    uint32_t rec_dropped;  /* 队列满而丢弃的封存记录 */
    uint32_t rtt_reject;   /* 记录写入未完整成功的次数 */
    uint32_t log_dropped;  /* 日志/状态行未写全或超缓冲 */
    uint32_t cmd_rejected; /* 整行拒绝的命令数 */
    uint32_t down_discarded; /* busy 期丢弃的下行字节数 */

    /* 探针 */
    bt_bx_probe_t probe;

    /* 逐 step、逐速率的探针使用位图（位序 = bt_bx_rates[] 下标）。
     * 一次探针被**接受**即置位，其后无论超时、中止还是本地切换失败都
     * 不再退额；需要同一档位的第二证据必须 `rate rearm` 前进 step。
     * 只记“最近一次探针速率”会让 A→B→A 绕过“同 step 每速率一次”。 */
    uint32_t probe_used_mask;
    uint32_t probe_used_step;

    /* 状态机 */
    uint8_t  rate_state;
    uint8_t  ready_seen;      /* 仅启动观测，不构成查询确认 */
    uint8_t  deferred;        /* 模块在旧速率报告目标配置：疑似延迟生效 */
    uint8_t  set_ineffective; /* 模块仍报旧配置：设置未生效 */
    uint32_t known_baud;
    uint32_t old_baud;
    uint32_t target_baud;
    uint32_t step; /* 每步每速率只允许一组查询 */
    /* 门禁通过并已调用 at_write 的受控重启次数（status 行 rb=）。
     * 计数口径是「控制器发出的重启尝试」，与模块是否真的重启无关：
     * 部分写出的重启同样占用操作者的重启额度。 */
    uint32_t reboots;
    bt_bx_ev_t ev_old;
    bt_bx_ev_t ev_target;

    /* 授权性证据的**采集代次**。KNOWN / deferred / set-ineffective 与两侧
     * 证据槽都绑定它：OTA 会话获取/释放会推进 epoch，此时旧证据必须主动
     * 作废，而不是只拒绝「带旧 epoch 的命令」——命令可以带**当前** epoch
     * 发出，却仍被过期证据放行改速、重启或恢复完成判定。
     * 作废后 known_baud 保留为「上电观测提示」（status 可见），但它不再
     * 授权任何动作；重新授权只能靠新一轮探针在本代次重新确认。
     * ev_valid=0 表示「当前没有授权性证据」，因此不能用 epoch==0 代替。 */
    uint32_t ev_epoch;
    uint8_t  ev_valid;
} bt_bx_t;

/* ===================== 字符串构造（无 libc printf 依赖） ===================== */

typedef struct
{
    char    *buf;
    unsigned cap;
    unsigned len;
    uint8_t  ovf;
} bt_bx_sb_t;

static void bt_bx_sb_init(bt_bx_sb_t *sb, char *buf, unsigned cap)
{
    sb->buf = buf;
    sb->cap = cap;
    sb->len = 0u;
    sb->ovf = 0u;
    if (cap > 0u)
    {
        buf[0] = '\0';
    }
}

static void bt_bx_sb_ch(bt_bx_sb_t *sb, char c)
{
    if (sb->len + 1u >= sb->cap)
    {
        sb->ovf = 1u;
        return;
    }
    sb->buf[sb->len++] = c;
    sb->buf[sb->len] = '\0';
}

static void bt_bx_sb_str(bt_bx_sb_t *sb, const char *s)
{
    while (*s != '\0')
    {
        bt_bx_sb_ch(sb, *s);
        ++s;
    }
}

static void bt_bx_sb_u32(bt_bx_sb_t *sb, uint32_t v)
{
    char tmp[10];
    unsigned n = 0u;

    if (v == 0u)
    {
        bt_bx_sb_ch(sb, '0');
        return;
    }
    while (v != 0u && n < sizeof(tmp))
    {
        tmp[n++] = (char)('0' + (char)(v % 10u));
        v /= 10u;
    }
    while (n > 0u)
    {
        bt_bx_sb_ch(sb, tmp[--n]);
    }
}

static void bt_bx_sb_hex8(bt_bx_sb_t *sb, uint8_t b)
{
    static const char hexd[] = "0123456789abcdef";
    bt_bx_sb_ch(sb, hexd[(b >> 4) & 0x0Fu]);
    bt_bx_sb_ch(sb, hexd[b & 0x0Fu]);
}

/* 开一条 `BX<tag>: ` 行 */
static void bt_bx_line_begin(bt_bx_sb_t *sb, char *buf, unsigned cap,
                             const char *tag)
{
    bt_bx_sb_init(sb, buf, cap);
    bt_bx_sb_str(sb, "BX");
    bt_bx_sb_str(sb, tag);
    bt_bx_sb_str(sb, ": ");
}

static void bt_bx_write(bt_bx_t *bx, bt_bx_sb_t *sb)
{
    unsigned w;

    if (sb->ovf || sb->len == 0u)
    {
        bx->log_dropped++;
        return;
    }
    w = bx->ops->rtt_write(bx->ops->io, sb->buf, sb->len);
    if (w != sb->len)
    {
        bx->log_dropped++;
    }
}

/* ===================== 初始化 ===================== */

static void bt_bx_reset_ev(bt_bx_ev_t *ev)
{
    memset(ev, 0, sizeof(*ev));
}

static void bt_bx_init(bt_bx_t *bx, const bt_bx_ops_t *ops, uint32_t baud)
{
    memset(bx, 0, sizeof(*bx));
    bx->ops = ops;
    bx->mcu_baud = baud;
    bx->rate_state = (uint8_t)BT_BX_STATE_UNKNOWN;
    bx->next_seq = 1u; /* 0 保留为“无记录” */
    bx->step = 1u;
    bt_bx_reset_ev(&bx->ev_old);
    bt_bx_reset_ev(&bx->ev_target);
}

/* ===================== 采集与封存 ===================== */

static void bt_bx_capture(bt_bx_t *bx, uint8_t byte)
{
    if (bx->cap_len == 0u)
    {
        bx->cap_baud = bx->mcu_baud;
        bx->cap_epoch = bx->ops->epoch(bx->ops->io);
        bx->cap_ovf = 0u;
    }
    if (bx->cap_len < BT_BX_RX_CAP)
    {
        bx->cap[bx->cap_len] = byte;
        bx->cap_len = (uint16_t)(bx->cap_len + 1u);
    }
    else
    {
        bx->cap_ovf = 1u;
    }
    bx->cap_last_ms = bx->ops->now_ms(bx->ops->io);
    bx->rx_bytes++;
}

static void bt_bx_probe_on_record(bt_bx_t *bx, const bt_bx_record_t *rec);

/* 封存当前采集缓冲。返回 1 = 已封存；0 = 无内容；-1 = 队列满而丢失。 */
static int bt_bx_capture_seal(bt_bx_t *bx)
{
    bt_bx_record_t *slot;

    if (bx->cap_len == 0u)
    {
        return 0;
    }
    if (bx->q_count >= BT_BX_REC_SLOTS)
    {
        bx->rec_dropped++;
        bx->cap_len = 0u;
        bx->cap_ovf = 0u;
        return -1;
    }
    slot = &bx->q[(unsigned)(bx->q_head + bx->q_count) % BT_BX_REC_SLOTS];
    memcpy(slot->data, bx->cap, bx->cap_len);
    slot->len = bx->cap_len;
    slot->ovf = bx->cap_ovf;
    slot->held = 1u;
    slot->seq = bx->next_seq++;
    slot->baud = bx->cap_baud;
    slot->epoch = bx->cap_epoch;
    bx->q_count++;
    bx->cap_len = 0u;
    bx->cap_ovf = 0u;
    bt_bx_probe_on_record(bx, slot);
    return 1;
}

/* 记录一次输出尝试：只有完整写入才算成功，否则保持待发。 */
static void bt_bx_emit(bt_bx_t *bx)
{
    bt_bx_record_t *rec;
    char wire[BT_BX_WIRE_MAX];
    bt_bx_sb_t sb;
    unsigned w;
    unsigned i;
    uint32_t epoch;

    if (bx->q_count == 0u)
    {
        return;
    }
    rec = &bx->q[bx->q_head];
    epoch = bx->ops->epoch(bx->ops->io);

    /* 记录行形如 `BXRX(12 b=115200 e=3 len=10): 2b55...0d0a`。
     * 此处不用 bt_bx_line_begin：记录序号要直接跟在开括号后，中间不能插
     * `: ` 分隔符。 */
    bt_bx_sb_init(&sb, wire, sizeof(wire));
    bt_bx_sb_str(&sb, "BXRX(");
    bt_bx_sb_u32(&sb, rec->seq);
    bt_bx_sb_str(&sb, " b=");
    bt_bx_sb_u32(&sb, rec->baud);
    bt_bx_sb_str(&sb, " e=");
    bt_bx_sb_u32(&sb, rec->epoch);
    bt_bx_sb_ch(&sb, ' ');
    if (rec->ovf)
    {
        bt_bx_sb_str(&sb, "OVF ");
    }
    if (rec->epoch != epoch)
    {
        /* 跨状态边界记录：保留原始代次并显式标注，不混入下一轮 */
        bt_bx_sb_str(&sb, "STALE ");
    }
    bt_bx_sb_str(&sb, "len=");
    bt_bx_sb_u32(&sb, rec->len);
    bt_bx_sb_str(&sb, "): ");
    for (i = 0u; i < rec->len; ++i)
    {
        bt_bx_sb_hex8(&sb, rec->data[i]);
    }
    bt_bx_sb_str(&sb, "\r\n");

    if (sb.ovf)
    {
        /* 编码本身超缓冲：记录不可能完整输出，按丢失计数并丢弃，
         * 避免队列被永久占满。 */
        bx->log_dropped++;
        bx->rec_dropped++;
        rec->held = 0u;
        bx->q_head = (uint8_t)((bx->q_head + 1u) % BT_BX_REC_SLOTS);
        bx->q_count--;
        return;
    }
    w = bx->ops->rtt_write(bx->ops->io, sb.buf, sb.len);
    if (w != sb.len)
    {
        /* 拒写：保留待发记录，下次 poll 重试；同一记录只会完整输出一次 */
        bx->rtt_reject++;
        return;
    }
    rec->held = 0u;
    bx->q_head = (uint8_t)((bx->q_head + 1u) % BT_BX_REC_SLOTS);
    bx->q_count--;
    bx->rec_emitted++;
}

/* ===================== 应答形态判定 ===================== */

/* 全部字节为可打印 ASCII 或 CR/LF。错速率下收到的字节流几乎不可能满足。 */
static int bt_bx_frame_is_text(const uint8_t *d, uint16_t len)
{
    uint16_t i;
    int printable = 0;

    if (len == 0u)
    {
        return 0;
    }
    for (i = 0u; i < len; ++i)
    {
        uint8_t c = d[i];
        if (c == '\r' || c == '\n')
        {
            continue;
        }
        if (c < 0x20u || c >= 0x7Fu)
        {
            return 0;
        }
        printable = 1;
    }
    return printable;
}

/* 记录尾部必须落在真实行终止符（CR/LF）上。
 *
 * 静默分帧只说明「这段时间没有新字节」，**不能**证明模块已经把应答发完：
 * 缓冲末尾的残片可能正是被截断的应答前缀（`+UART: 5` 少了最后一位数字）。
 * 行以终止符切分，故无终止符的行只可能是最后一行的尾片；末尾不是终止符
 * 即整帧不作为证据。 */
static int bt_bx_frame_terminated(const uint8_t *d, uint16_t len)
{
    uint8_t c;

    if (len == 0u)
    {
        return 0;
    }
    c = d[len - 1u];
    return (c == (uint8_t)'\r' || c == (uint8_t)'\n') ? 1 : 0;
}

static int bt_bx_upper(uint8_t c)
{
    if (c >= (uint8_t)'a' && c <= (uint8_t)'z')
    {
        return (int)(c - 32u);
    }
    return (int)c;
}

/* 大小写不敏感的全串相等（AT 命令不区分大小写）。必须是全串比较：
 * 前缀或子串匹配会把 `AT+REBOOT=1;AT+UART=8` 一类拼接命令放进白名单。 */
static int bt_bx_streq_ci(const char *a, const char *b)
{
    unsigned i = 0u;

    for (;;)
    {
        int ca = bt_bx_upper((uint8_t)a[i]);
        int cb = bt_bx_upper((uint8_t)b[i]);

        if (ca != cb)
        {
            return 0;
        }
        if (ca == 0)
        {
            return 1;
        }
        ++i;
    }
}

static int bt_bx_match_kw(const uint8_t *d, uint16_t len, uint16_t at,
                          const char *kw)
{
    unsigned k = 0u;

    while (kw[k] != '\0')
    {
        if (at + k >= len)
        {
            return 0;
        }
        if (bt_bx_upper(d[at + k]) != (int)(uint8_t)kw[k])
        {
            return 0;
        }
        ++k;
    }
    return 1;
}

/* 十进制逐位累加：溢出返回 1（此时 *v 无意义）。所有来自线上的十进制
 * 数字（epoch、速率、应答里的档位号）都必须走这里，禁止靠 uint32 回绕
 * 把超范围输入变成某个恰好合法的值。 */
static int bt_bx_u32_step(uint32_t *v, uint32_t digit)
{
    if (*v > (0xFFFFFFFFu - digit) / 10u)
    {
        return 1;
    }
    *v = *v * 10u + digit;
    return 0;
}

/* 行首关键字判定：`[+]KW`；关键字结束位置写入 out_after。
 * 只承认行首形态，帧内任意位置出现关键字不算应答——这正是 `AT+VER?`
 * 回显被误判成版本应答的原因。 */
static int bt_bx_line_kw(const uint8_t *d, uint16_t start, uint16_t end,
                         const char *kw, uint16_t *out_after)
{
    uint16_t i = start;
    unsigned k = 0u;

    if (i < end && d[i] == (uint8_t)'+')
    {
        ++i;
    }
    while (kw[k] != '\0')
    {
        if (i + k >= end || bt_bx_upper(d[i + k]) != (int)(uint8_t)kw[k])
        {
            return 0;
        }
        ++k;
    }
    *out_after = (uint16_t)(i + k);
    return 1;
}

/* 解析 `+UART: <n>`（手册页 11：应答 `+UART: NUM\r\n`）。
 *
 * 形态判据（fail-closed，只承认完整应答）：
 *  - 只认**行首**的应答行（可选 `+`），不再向前扫描帧内首个 `UART`；
 *  - `UART` 后必须是 `:` 与至少一位十进制数字；
 *  - 数字后只允许空格/制表符或行尾，出现任何其它字符（`+UART: 5XYZ`）
 *    整帧判为无效，不做前缀截断接受；
 *  - 数字必须完整解析且不得回绕，超长十进制不做静默截断；
 *  - 同一帧内出现两个不同数值即为冲突应答，整帧无效；
 *  - 帧必须以真实行终止符收尾：静默分帧不能证明协议行完整，无终止符的
 *    尾片整帧无效（bt_bx_frame_terminated）。
 * 返回 1 表示本帧给出唯一且形态完整的配置序号。 */
static int bt_bx_frame_parse_uart(const uint8_t *d, uint16_t len,
                                  uint32_t *out_idx)
{
    uint16_t i = 0u;
    int found = 0;
    uint32_t val = 0u;

    if (!bt_bx_frame_is_text(d, len) || !bt_bx_frame_terminated(d, len))
    {
        return 0;
    }
    while (i < len)
    {
        uint16_t eol = i;
        uint16_t after;
        uint16_t j;
        uint32_t v = 0u;
        unsigned digits = 0u;
        int bad = 0;

        while (eol < len && d[eol] != (uint8_t)'\r' && d[eol] != (uint8_t)'\n')
        {
            ++eol;
        }
        if (!bt_bx_line_kw(d, i, eol, "UART", &after))
        {
            /* 非应答行（AT 回显、错误文本）：忽略，不判无效 */
            i = (uint16_t)(eol + 1u);
            continue;
        }
        j = after;
        while (j < eol && (d[j] == (uint8_t)' ' || d[j] == (uint8_t)'\t'))
        {
            ++j;
        }
        if (j >= eol || d[j] != (uint8_t)':')
        {
            bad = 1;
        }
        else
        {
            ++j;
            while (j < eol && (d[j] == (uint8_t)' ' || d[j] == (uint8_t)'\t'))
            {
                ++j;
            }
            while (j < eol && d[j] >= (uint8_t)'0' && d[j] <= (uint8_t)'9')
            {
                if (bt_bx_u32_step(&v, (uint32_t)(d[j] - (uint8_t)'0')))
                {
                    bad = 1;
                }
                ++digits;
                ++j;
            }
            if (digits == 0u)
            {
                bad = 1;
            }
            while (j < eol && (d[j] == (uint8_t)' ' || d[j] == (uint8_t)'\t'))
            {
                ++j;
            }
            if (j != eol)
            {
                bad = 1; /* 数字后仍有非空字符：非法后缀 */
            }
        }
        if (bad)
        {
            return 0; /* 疑似应答但形态非法：整帧不作为证据 */
        }
        if (found && val != v)
        {
            return 0; /* 同一帧内冲突应答 */
        }
        found = 1;
        val = v;
        i = (uint16_t)(eol + 1u);
    }
    if (!found)
    {
        return 0;
    }
    *out_idx = val;
    return 1;
}

/* 版本应答判据（手册页 12：`AT+VER?` → `+VER:V0.0.1\r\n`）。
 *
 * 形态判据（fail-closed，只承认手册形态的完整应答行）：
 *  - 只认行首 `[+]VER` 且关键字后必须紧跟 `:`；`+VERSION`、`+VERXYZ` 这类
 *    以 VER 开头的前缀变体不是本模块的版本应答，整帧不作为证据；
 *  - `:` 之后去掉空格/制表符后必须有非空内容：`+VER:`、`+VER:   ` 是空应答，
 *    不构成版本确认；
 *  - 帧必须以真实行终止符收尾，缓冲末尾的版本残片无效。
 * 不接受帧内任意位置出现 VER——那会把 `AT+VER?` 回显当成应答。 */
static int bt_bx_frame_is_version(const uint8_t *d, uint16_t len)
{
    uint16_t i = 0u;

    if (!bt_bx_frame_is_text(d, len) || !bt_bx_frame_terminated(d, len))
    {
        return 0;
    }
    while (i < len)
    {
        uint16_t eol = i;
        uint16_t after;
        uint16_t j;

        while (eol < len && d[eol] != (uint8_t)'\r' && d[eol] != (uint8_t)'\n')
        {
            ++eol;
        }
        if (bt_bx_line_kw(d, i, eol, "VER", &after) && after < eol &&
            d[after] == (uint8_t)':')
        {
            j = (uint16_t)(after + 1u);
            while (j < eol && (d[j] == (uint8_t)' ' || d[j] == (uint8_t)'\t'))
            {
                ++j;
            }
            if (j < eol)
            {
                return 1;
            }
        }
        i = (uint16_t)(eol + 1u);
    }
    return 0;
}

static int bt_bx_frame_has_ready(const uint8_t *d, uint16_t len)
{
    uint16_t i;

    if (!bt_bx_frame_is_text(d, len))
    {
        return 0;
    }
    for (i = 0u; i + 5u <= len; ++i)
    {
        if (bt_bx_match_kw(d, len, i, "READY"))
        {
            return 1;
        }
    }
    return 0;
}

/* ===================== 探针记录匹配 ===================== */

static void bt_bx_probe_on_record(bt_bx_t *bx, const bt_bx_record_t *rec)
{
    bt_bx_probe_t *p = &bx->probe;

    if (bt_bx_frame_has_ready(rec->data, rec->len))
    {
        /* READY 只是启动观测，不构成任何查询确认 */
        bx->ready_seen = 1u;
    }
    if (!p->active)
    {
        return;
    }
    /* 窗口未建立：正在为本次查询封存旧采集缓冲，此刻产生的记录必然采集于
     * 查询之前。记录照常保存与输出，但不得参与本窗口判定。 */
    if (!p->window_armed)
    {
        return;
    }
    /* 窗口/代次绑定：记录序号、MCU 速率、会话代次、溢出都必须在窗口内成立 */
    if (rec->seq < p->leg_seq_floor || rec->ovf ||
        rec->baud != p->baud || rec->epoch != p->epoch_at_start)
    {
        return;
    }
    if (p->leg == 0u)
    {
        uint32_t idx = 0u;
        if (!p->comm_ok && bt_bx_frame_parse_uart(rec->data, rec->len, &idx))
        {
            p->comm_ok = 1u;
            p->reported_valid = 1u;
            p->reported_idx = idx;
            p->reported_mapped = (uint8_t)(bt_bx_rate_baud(idx) != 0u ? 1u : 0u);
            p->reported_baud = bt_bx_rate_baud(idx);
            p->uart_seq = rec->seq;
        }
    }
    else
    {
        if (!p->comm_ok && bt_bx_frame_is_version(rec->data, rec->len))
        {
            p->comm_ok = 1u;
            p->ver_seq = rec->seq;
        }
    }
}

/* ===================== 本地 MCU UART 切速 ===================== */

/* 状态机求值函数定义在切速之后；切速失败需要它把不确定态打回 UNKNOWN。 */
static void bt_bx_set_unknown(bt_bx_t *bx, const char *why);

static int bt_bx_mcu_switch(bt_bx_t *bx, uint32_t baud)
{
    int rc;
    char lbuf[BT_BX_LOG_CAP];
    bt_bx_sb_t sb;

    if (!bt_bx_rate_known(baud))
    {
        return -2;
    }
    if (baud == bx->mcu_baud)
    {
        return 0;
    }
    /* 切换前封存旧速率记录：保留旧 baud/epoch，无法保存则报告丢失 */
    if (bt_bx_capture_seal(bx) < 0)
    {
        bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), "UART");
        bt_bx_sb_str(&sb, "seallost baud=");
        bt_bx_sb_u32(&sb, bx->mcu_baud);
        bt_bx_sb_str(&sb, "\r\n");
        bt_bx_write(bx, &sb);
    }
    rc = bx->ops->mcu_set_baud(bx->ops->io, baud);
    if (rc != 0)
    {
        /* 两类失败必须分开处理：
         *  - rc == -3：平台已调用 begin() 但回读失败/超差，**硬件是否已改变
         *    不确定**。旧 mcu_baud 簿记不再可信，保留它会让后续“本机速率”
         *    判断、`rate set` 门禁与探针窗口全部建立在错误前提上。
         *    处置：作废 mcu_baud（0 = 未知）并把状态机打到 UNKNOWN，
         *    只有经受控重配（`uart`）并由探针重新取证才能恢复。
         *  - 其余（-1 TX 超时 / -2 不支持 / -4 前置检查失败）：重配未发生，
         *    硬件确实未变，保留原状态与旧速率是准确的。 */
        int uncertain = (rc == -3);
        if (uncertain)
        {
            bx->mcu_baud = 0u;
            bt_bx_set_unknown(bx, "mcu-baud-uncertain");
        }
        bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), "UART");
        bt_bx_sb_str(&sb, "switch failed rc=");
        bt_bx_sb_u32(&sb, (uint32_t)(-rc));
        bt_bx_sb_str(&sb, " want=");
        bt_bx_sb_u32(&sb, baud);
        bt_bx_sb_str(&sb, " keep=");
        if (uncertain)
        {
            bt_bx_sb_str(&sb, "uncertain mcu=0 reason=post-reconfig");
        }
        else
        {
            bt_bx_sb_u32(&sb, bx->mcu_baud);
            bt_bx_sb_str(&sb, " reason=pre-reconfig");
        }
        bt_bx_sb_str(&sb, "\r\n");
        bt_bx_write(bx, &sb);
        return rc;
    }
    bx->mcu_baud = baud;
    /* 仅在确认 OTA 空闲（调用方已保证）后复位 demux 残留 */
    bx->ops->reset_demux(bx->ops->io);
    bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), "UART");
    bt_bx_sb_str(&sb, "ok mcu=");
    bt_bx_sb_u32(&sb, baud);
    bt_bx_sb_str(&sb, " note=mcu-only\r\n");
    bt_bx_write(bx, &sb);
    return 0;
}

/* ===================== 探针推进 ===================== */

static void bt_bx_probe_send_leg(bt_bx_t *bx)
{
    bt_bx_probe_t *p = &bx->probe;
    const char *q = (p->leg == 0u) ? "AT+UART?" : "AT+VER?";

    /* 窗口建立顺序固定为：关窗 → 封存旧缓冲 → 设下界 → 开窗 → 发送查询。
     * 封存会让旧采集缓冲变成一条记录并经过 on_record；关窗期间它一律不参与
     * 判定（它采集于查询之前），但记录本身照常保留并输出。若先开窗再封存，
     * 旧日志就会在下界尚未建立时被记账为本 leg 的应答。 */
    p->window_armed = 0u;
    (void)bt_bx_capture_seal(bx);
    p->leg_seq_floor = bx->next_seq;
    p->leg_sent_ms = bx->ops->now_ms(bx->ops->io);
    p->window_armed = 1u;
    (void)bx->ops->at_write(bx->ops->io, q, (unsigned)strlen(q));
}

static void bt_bx_probe_abort(bt_bx_t *bx, bt_bx_abort_t why)
{
    bt_bx_probe_t *p = &bx->probe;
    char lbuf[BT_BX_LOG_CAP];
    bt_bx_sb_t sb;

    p->active = 0u;
    p->window_armed = 0u;
    p->aborted = (uint8_t)why;
    bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), "PB");
    bt_bx_sb_str(&sb, "abort why=");
    bt_bx_sb_u32(&sb, (uint32_t)why);
    bt_bx_sb_str(&sb, " baud=");
    bt_bx_sb_u32(&sb, p->baud);
    bt_bx_sb_str(&sb, "\r\n");
    bt_bx_write(bx, &sb);
}

static void bt_bx_rate_eval(bt_bx_t *bx);

static void bt_bx_probe_finish(bt_bx_t *bx)
{
    bt_bx_probe_t *p = &bx->probe;
    char lbuf[BT_BX_LOG_CAP];
    bt_bx_sb_t sb;

    p->active = 0u;
    p->window_armed = 0u;
    p->started = 1u;
    bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), "PB");
    bt_bx_sb_str(&sb, "done baud=");
    bt_bx_sb_u32(&sb, p->baud);
    bt_bx_sb_str(&sb, " comm=");
    bt_bx_sb_u32(&sb, p->comm_ok ? 1u : 0u);
    bt_bx_sb_str(&sb, " idx=");
    if (p->reported_valid)
    {
        bt_bx_sb_u32(&sb, p->reported_idx);
        if (!p->reported_mapped)
        {
            bt_bx_sb_str(&sb, "(unmapped)");
        }
    }
    else
    {
        bt_bx_sb_str(&sb, "none");
    }
    bt_bx_sb_str(&sb, " useq=");
    bt_bx_sb_u32(&sb, p->uart_seq);
    bt_bx_sb_str(&sb, " vseq=");
    bt_bx_sb_u32(&sb, p->ver_seq);
    bt_bx_sb_str(&sb, "\r\n");
    bt_bx_write(bx, &sb);

    bt_bx_rate_eval(bx);
}

static void bt_bx_probe_poll(bt_bx_t *bx)
{
    bt_bx_probe_t *p = &bx->probe;
    uint32_t now;

    if (!p->active)
    {
        return;
    }
    /* step 已前进说明本次在飞探针属于旧一轮证据窗口（例如操作者在探针未返回
     * 时执行了 rate rearm / rate set / 重新 probe）。旧窗口的应答不得进入新
     * step，因此先中止并作废，再让新命令按新 step 重新取证。 */
    if (p->step_at_start != bx->step)
    {
        bt_bx_probe_abort(bx, BT_BX_ABORT_STEP);
        return;
    }
    if (bx->mcu_baud != p->baud)
    {
        bt_bx_probe_abort(bx, BT_BX_ABORT_BAUD);
        return;
    }
    now = bx->ops->now_ms(bx->ops->io);
    if (p->leg == 0u)
    {
        if (!p->comm_ok && (uint32_t)(now - p->leg_sent_ms) < BT_BX_QUERY_MS)
        {
            return;
        }
        p->leg = 1u;
        bt_bx_probe_send_leg(bx);
        return;
    }
    if (!p->comm_ok && (uint32_t)(now - p->leg_sent_ms) < BT_BX_QUERY_MS)
    {
        return;
    }
    bt_bx_probe_finish(bx);
}

/* ===================== 状态机求值 ===================== */

static void bt_bx_log_state(bt_bx_t *bx, const char *why)
{
    char lbuf[BT_BX_LOG_CAP];
    bt_bx_sb_t sb;

    bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), "RATE");
    bt_bx_sb_str(&sb, why);
    bt_bx_sb_str(&sb, " state=");
    bt_bx_sb_u32(&sb, (uint32_t)bx->rate_state);
    bt_bx_sb_str(&sb, " known=");
    bt_bx_sb_u32(&sb, bx->known_baud);
    bt_bx_sb_str(&sb, " old=");
    bt_bx_sb_u32(&sb, bx->old_baud);
    bt_bx_sb_str(&sb, " target=");
    bt_bx_sb_u32(&sb, bx->target_baud);
    bt_bx_sb_str(&sb, " step=");
    bt_bx_sb_u32(&sb, bx->step);
    bt_bx_sb_str(&sb, " deferred=");
    bt_bx_sb_u32(&sb, bx->deferred ? 1u : 0u);
    bt_bx_sb_str(&sb, " seteff=");
    bt_bx_sb_u32(&sb, bx->set_ineffective ? 1u : 0u);
    bt_bx_sb_str(&sb, "\r\n");
    bt_bx_write(bx, &sb);
}

static void bt_bx_set_unknown(bt_bx_t *bx, const char *why)
{
    bx->rate_state = (uint8_t)BT_BX_STATE_UNKNOWN;
    bx->known_baud = 0u;
    bt_bx_log_state(bx, why);
}

/* 作废当前事务的两侧证据位（不动 state/old/target/本机速率）。
 * 模块重启后它回到上电态，重启前采集的任何应答都不再是「当前有效证据」；
 * 清零后 PENDING 规则退化为「证据未齐」，重启门禁也随之关闭，必须重新取证。 */
static void bt_bx_probe_evidence_reset(bt_bx_t *bx)
{
    memset(&bx->ev_old, 0, sizeof(bx->ev_old));
    memset(&bx->ev_target, 0, sizeof(bx->ev_target));
}

/* 把「当前授权性证据」绑定到本代次。凡是写入 KNOWN / deferred /
 * set-ineffective 或两侧证据槽的路径都必须调用它；否则那些证据会以
 * 「无代次」状态长期放行，正是 M1 复核的缺陷形态。 */
static void bt_bx_evidence_stamp(bt_bx_t *bx)
{
    bx->ev_epoch = bx->ops->epoch(bx->ops->io);
    bx->ev_valid = 1u;
}

/* 当前是否存在**本代次**采集的授权性证据。作为 bt_bx_poll 主动作废之外
 * 的第二道闸：判据函数直接调用时（例如宿主测试、或未来新增的调用点）
 * 同样不会拿过期证据放行。 */
static int bt_bx_evidence_current(const bt_bx_t *bx)
{
    return (bx->ev_valid != 0u) &&
           (bx->ev_epoch == bx->ops->epoch(bx->ops->io));
}

/* 会话边界（epoch 变化）后**主动作废**授权性证据。
 * 只拒绝带旧 epoch 的命令不够：操作者可以带当前 epoch 发命令，而过期的
 * KNOWN / deferred 仍会放行改速与重启。作废范围 = 状态机的授权位（state /
 * deferred / set-ineffective）+ 两侧证据槽；本机速率、old/target 与
 * known_baud 保留：known_baud 仅作「上电观测提示」，不授权任何动作，
 * 操作者据此选择先探哪个档位，重新确认后才会恢复授权。
 * 无证据可作废时静默（不写状态行），避免每次启动都刷一行废日志。 */
static void bt_bx_evidence_expire(bt_bx_t *bx, uint32_t epoch)
{
    if (bx->ev_valid != 0u && bx->ev_epoch == epoch)
    {
        return;
    }
    if (bx->ev_valid != 0u &&
        (bx->rate_state != (uint8_t)BT_BX_STATE_UNKNOWN ||
         bx->deferred != 0u || bx->set_ineffective != 0u ||
         bx->ev_old.attempted != 0u || bx->ev_target.attempted != 0u))
    {
        bx->rate_state = (uint8_t)BT_BX_STATE_UNKNOWN;
        bx->deferred = 0u;
        bx->set_ineffective = 0u;
        bt_bx_probe_evidence_reset(bx);
        bt_bx_log_state(bx, "evidence-expired");
    }
    bx->ev_valid = 0u;
}

/* 把一次探针结果写入对应证据槽，然后按规则求值。 */
static void bt_bx_rate_eval(bt_bx_t *bx)
{
    bt_bx_probe_t *p = &bx->probe;
    bt_bx_ev_t *slot = NULL;

    /* 本次探针在本代次内结算（bt_bx_poll 在探针轮询前先作废跨代次在飞探针，
     * 因此到这里 epoch_at_start 必然等于当前 epoch），结果即本代次证据。 */
    bt_bx_evidence_stamp(bx);

    if (bx->rate_state == (uint8_t)BT_BX_STATE_PENDING)
    {
        if (p->baud == bx->old_baud)
        {
            slot = &bx->ev_old;
        }
        else if (p->baud == bx->target_baud)
        {
            slot = &bx->ev_target;
        }
    }

    if (slot != NULL)
    {
        slot->attempted = 1u;
        slot->comm_ok = p->comm_ok;
        slot->reported_valid = p->reported_valid;
        slot->reported_mapped = p->reported_mapped;
        slot->reported_idx = p->reported_idx;
        slot->reported_baud = p->reported_baud;
        slot->seq = p->uart_seq != 0u ? p->uart_seq : p->ver_seq;
    }

    if (bx->rate_state == (uint8_t)BT_BX_STATE_KNOWN)
    {
        /* KNOWN 态：探针只用于确认/发现，不触发 PENDING 规则。 */
        if (p->comm_ok && p->reported_valid && p->reported_mapped)
        {
            if (p->reported_baud != p->baud)
            {
                /* 在本机速率上收到另一档位配置：证据矛盾。
                 * 不能只记日志后继续保留 KNOWN——那会让 known==mcu 的一致性
                 * 名存实亡，并保留 `rate set` 资格。矛盾即失效，重新取证。 */
                bx->deferred = 0u;
                bx->set_ineffective = 0u;
                bt_bx_set_unknown(bx, "confirm-contradict");
            }
            else if (p->reported_baud != bx->known_baud)
            {
                bx->known_baud = p->reported_baud;
                bt_bx_log_state(bx, "reknown");
            }
            else
            {
                bt_bx_log_state(bx, "confirm");
            }
        }
        else
        {
            bt_bx_log_state(bx, "confirm-no-reply");
        }
        return;
    }

    if (bx->rate_state != (uint8_t)BT_BX_STATE_PENDING)
    {
        /* UNKNOWN 态：只有“在本机速率上收到同一档位的配置确认”才回到 KNOWN。
         * 速率与报告值不一致属于矛盾证据，保持 UNKNOWN。 */
        if (p->comm_ok && p->reported_valid && p->reported_mapped &&
            p->reported_baud == p->baud)
        {
            bx->rate_state = (uint8_t)BT_BX_STATE_KNOWN;
            bx->known_baud = p->baud;
            bx->old_baud = 0u;
            bx->target_baud = 0u;
            bx->deferred = 0u;
            bx->set_ineffective = 0u;
            bt_bx_log_state(bx, "known");
        }
        return;
    }

    /* PENDING：target 侧确认优先（唯一可直接收口的路径）。 */
    if (bx->ev_target.attempted && bx->ev_target.comm_ok &&
        bx->ev_target.reported_valid && bx->ev_target.reported_mapped)
    {
        if (bx->ev_target.reported_baud == bx->target_baud)
        {
            bx->rate_state = (uint8_t)BT_BX_STATE_KNOWN;
            bx->known_baud = bx->target_baud;
            bx->old_baud = 0u;
            bx->target_baud = 0u;
            bx->deferred = 0u;
            bx->set_ineffective = 0u;
            bt_bx_log_state(bx, "known-target");
            return;
        }
        /* 目标速率可通信但模块报的是别的档位：证据矛盾。 */
        bt_bx_set_unknown(bx, "target-mismatch");
        return;
    }
    if (!bx->ev_old.attempted ||
        (bx->target_baud != 0u && !bx->ev_target.attempted))
    {
        return; /* 证据未齐，等另一侧 */
    }
    if (bx->ev_old.comm_ok && bx->ev_old.reported_valid &&
        bx->ev_old.reported_mapped)
    {
        if (bx->ev_old.reported_baud == bx->target_baud)
        {
            /* 仅旧速率可通信但已报目标配置：按可能延迟生效处理。 */
            bx->deferred = 1u;
            bt_bx_log_state(bx, "deferred");
            return;
        }
        if (bx->ev_old.reported_baud == bx->old_baud)
        {
            /* 设置未生效：回到 KNOWN(old)，不自动反复设置。 */
            bx->set_ineffective = 1u;
            bx->rate_state = (uint8_t)BT_BX_STATE_KNOWN;
            bx->known_baud = bx->old_baud;
            bx->old_baud = 0u;
            bx->target_baud = 0u;
            bt_bx_log_state(bx, "set-ineffective");
            return;
        }
    }
    /* 两侧均无有效应答，或证据矛盾。 */
    bt_bx_set_unknown(bx, "no-evidence");
}

/* ===================== 下行命令行 ===================== */

static void bt_bx_line_reset(bt_bx_t *bx)
{
    bx->line_len = 0u;
    bx->line_over = 0u;
    bx->line_bad = 0u;
}

/* 解析 `<epoch> [余下]`；成功返回 1 并给出余下指针（无余下时指向空串）。
 * epoch 后必须是空格或行尾——`rate rearm <epoch>` 这类命令不带后续参数，
 * 若只接受空格形式，常规写法会被判成 bad epoch arg 而静默失效。
 * 数字必须完整解析且不得回绕：`4294967296` 会被拒绝，不允许靠 uint32
 * 回绕变成“恰好当前 epoch”而通过门禁。 */
static int bt_bx_take_epoch(bt_bx_t *bx, const char *arg, uint32_t *out_epoch,
                            const char **out_rest, const char *tag)
{
    uint32_t v = 0u;
    unsigned n = 0u;
    int ovf = 0;
    char lbuf[BT_BX_LOG_CAP];
    bt_bx_sb_t sb;

    while (arg[n] >= '0' && arg[n] <= '9')
    {
        if (bt_bx_u32_step(&v, (uint32_t)(arg[n] - '0')))
        {
            ovf = 1;
        }
        ++n;
    }
    if (n == 0u || ovf != 0 || (arg[n] != ' ' && arg[n] != '\0'))
    {
        bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), tag);
        bt_bx_sb_str(&sb, ovf != 0 ? "epoch arg overflow\r\n"
                                   : "bad epoch arg\r\n");
        bt_bx_write(bx, &sb);
        return 0;
    }
    *out_epoch = v;
    *out_rest = (arg[n] == ' ') ? (arg + n + 1u) : (arg + n);
    return 1;
}

/* 十进制参数（速率等）：必须整串解析且不得回绕。超范围输入一律拒绝——
 * `4295082496` 回绕后正好等于白名单里的 115200，静默接受等于绕过门禁。 */
static int bt_bx_parse_u32(const char *s, uint32_t *out)
{
    uint32_t v = 0u;
    unsigned n = 0u;

    while (s[n] >= '0' && s[n] <= '9')
    {
        if (bt_bx_u32_step(&v, (uint32_t)(s[n] - '0')))
        {
            return 0;
        }
        ++n;
    }
    if (n == 0u || s[n] != '\0')
    {
        return 0;
    }
    *out = v;
    return 1;
}

static void bt_bx_reject(bt_bx_t *bx, const char *tag, const char *why)
{
    char lbuf[BT_BX_LOG_CAP];
    bt_bx_sb_t sb;

    bx->cmd_rejected++;
    bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), tag);
    bt_bx_sb_str(&sb, "rejected ");
    bt_bx_sb_str(&sb, why);
    bt_bx_sb_str(&sb, "\r\n");
    bt_bx_write(bx, &sb);
}

/* 执行副作用前的最后一道门：epoch 未变且仍持有空闲所有权。 */
static int bt_bx_owns_idle(bt_bx_t *bx, uint32_t epoch, const char *tag)
{
    if (bx->ops->busy(bx->ops->io) ||
        bx->ops->epoch(bx->ops->io) != epoch)
    {
        bt_bx_reject(bx, tag, "ownership-lost");
        return 0;
    }
    return 1;
}

/* 恢复完成判据（status 行 restored=）：操作者判定「可以进生产镜像烧录」的
 * 唯一代码口径。必须**同时**满足：
 *   1) 无在飞探针（不会被尚未结算的查询改判）；
 *   2) 本机速率在基线上；
 *   3) 模块在基线上被**当前有效证据**确认——KNOWN 只会由本轮探针确认写入，
 *      会话边界（epoch 变化）会主动作废证据并让状态退回 UNKNOWN，重启也会
 *      作废证据并让状态退回 PENDING，因此旧证据无法蒙混过关；
 *   4) 证据确实属于当前代次（bt_bx_evidence_current）：这是第 3 条之外的第二
 *      道闸，覆盖「状态位尚未被轮询作废，但判据已被直接调用」的场景。
 *
 * 关键：`known == target` **不是**恢复完成。一个尚未收口的提速事务
 * （old=115200,target=230400）确认目标后同样会给出 known=230400，把
 * 「事务目标」当成「恢复目标」会在模块还在提速档位时放行生产流程。
 * 恢复目标只由基线速率本身判定；任何其它 KNOWN 值都必须先走受控降速。
 * 基线取档位表 0 号，避免再写一份字面量与之漂移。 */
static int bt_bx_restored(const bt_bx_t *bx)
{
    return (bx->probe.active == 0u) &&
           (bx->rate_state == (uint8_t)BT_BX_STATE_KNOWN) &&
           (bx->known_baud == bt_bx_rates[0].baud) &&
           (bx->mcu_baud == bt_bx_rates[0].baud) &&
           (bt_bx_evidence_current(bx) != 0);
}

static void bt_bx_cmd_status(bt_bx_t *bx)
{
    char lbuf[BT_BX_LOG_CAP];
    bt_bx_sb_t sb;

    bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), "ST");
    bt_bx_sb_str(&sb, "baud=");
    bt_bx_sb_u32(&sb, bx->mcu_baud);
    bt_bx_sb_str(&sb, " epoch=");
    bt_bx_sb_u32(&sb, bx->ops->epoch(bx->ops->io));
    bt_bx_sb_str(&sb, " busy=");
    bt_bx_sb_u32(&sb, bx->ops->busy(bx->ops->io) ? 1u : 0u);
    bt_bx_sb_str(&sb, " state=");
    bt_bx_sb_u32(&sb, (uint32_t)bx->rate_state);
    bt_bx_sb_str(&sb, " known=");
    bt_bx_sb_u32(&sb, bx->known_baud);
    bt_bx_sb_str(&sb, " old=");
    bt_bx_sb_u32(&sb, bx->old_baud);
    bt_bx_sb_str(&sb, " target=");
    bt_bx_sb_u32(&sb, bx->target_baud);
    bt_bx_sb_str(&sb, " restored=");
    bt_bx_sb_u32(&sb, bt_bx_restored(bx) ? 1u : 0u);
    bt_bx_sb_str(&sb, " rb=");
    bt_bx_sb_u32(&sb, bx->reboots);
    bt_bx_sb_str(&sb, " step=");
    bt_bx_sb_u32(&sb, bx->step);
    bt_bx_sb_str(&sb, " probe=");
    bt_bx_sb_u32(&sb, bx->probe.active ? 1u : 0u);
    bt_bx_sb_str(&sb, " ready=");
    bt_bx_sb_u32(&sb, bx->ready_seen ? 1u : 0u);
    bt_bx_sb_str(&sb, " rxc=");
    bt_bx_sb_u32(&sb, (uint32_t)bx->cap_len);
    bt_bx_sb_str(&sb, " q=");
    bt_bx_sb_u32(&sb, (uint32_t)bx->q_count);
    bt_bx_sb_str(&sb, " seq=");
    bt_bx_sb_u32(&sb, bx->next_seq - 1u);
    bt_bx_sb_str(&sb, " rx=");
    bt_bx_sb_u32(&sb, bx->rx_bytes);
    bt_bx_sb_str(&sb, " emit=");
    bt_bx_sb_u32(&sb, bx->rec_emitted);
    bt_bx_sb_str(&sb, " drop=");
    bt_bx_sb_u32(&sb, bx->rec_dropped);
    bt_bx_sb_str(&sb, " rej=");
    bt_bx_sb_u32(&sb, bx->rtt_reject);
    bt_bx_sb_str(&sb, " logdrop=");
    bt_bx_sb_u32(&sb, bx->log_dropped);
    bt_bx_sb_str(&sb, " cmdr=");
    bt_bx_sb_u32(&sb, bx->cmd_rejected);
    bt_bx_sb_str(&sb, " disc=");
    bt_bx_sb_u32(&sb, bx->down_discarded);
    bt_bx_sb_str(&sb, "\r\n");
    bt_bx_write(bx, &sb);
}

/* AT 文本白名单：只放行本操作单确需的命令。
 * 之所以收窄到整串白名单而不是「允许任意 AT」，是因为原始文本入口能绕过
 * `rate set` 的 KNOWN/白名单门禁（直接发 `AT+UART=N`）、能改与实验无关的
 * 模块配置，也能在在飞探针窗口内注入查询污染证据。改速一律走受控
 * `rate set`；速率/版本查询一律走受控 `probe`。 */
static const char *const bt_bx_at_allow[] = { "AT+REBOOT=1" };

static int bt_bx_at_allowed(const char *text)
{
    unsigned i;

    if (*text != 'A' && *text != 'a')
    {
        return 0;
    }
    for (i = 0u; i < (unsigned)(sizeof(bt_bx_at_allow) / sizeof(bt_bx_at_allow[0])); ++i)
    {
        if (bt_bx_streq_ci(text, bt_bx_at_allow[i]) != 0)
        {
            return 1;
        }
    }
    return 0;
}

/* 重启门禁：只允许在「已发一次设置命令且旧速率上已确认模块报了目标档位」
 * （deferred）的受控分支里重启。此时模块在 old 档位可通信、本机也在 old，
 * 重启后仍能捕获 `+READY`，不会丢失 AT 通道。
 * 其他状态（UNKNOWN / KNOWN / 无 deferred）一律拒绝：既不能拿重启当恢复
 * 万能手段，也不能在无法观测后果时盲发重启。
 * deferred 属授权性证据，同样绑定采集代次：会话边界后即失效，必须在当前
 * 代次重新取证（两侧探针）才能再次重启。 */
static int bt_bx_at_reboot_allowed(const bt_bx_t *bx)
{
    /* 在飞探针期间重启会同时污染窗口判定与 +READY 证据，直接拒绝。 */
    if (bx->probe.active != 0u)
    {
        return 0;
    }
    if (bt_bx_evidence_current(bx) == 0)
    {
        return 0;
    }
    return (bx->rate_state == (uint8_t)BT_BX_STATE_PENDING) &&
           (bx->deferred != 0u) &&
           (bx->ev_old.attempted != 0u) && (bx->ev_old.comm_ok != 0u) &&
           (bx->old_baud != 0u) &&
           (bx->mcu_baud == bx->old_baud);
}

static void bt_bx_cmd_at(bt_bx_t *bx, const char *arg)
{
    uint32_t epoch;
    const char *text;
    unsigned n;
    char lbuf[BT_BX_LOG_CAP];
    bt_bx_sb_t sb;

    if (!bt_bx_take_epoch(bx, arg, &epoch, &text, "AT"))
    {
        return;
    }
    if (bx->ops->epoch(bx->ops->io) != epoch)
    {
        bt_bx_reject(bx, "AT", "stale-epoch");
        return;
    }
    if (*text == '\0')
    {
        bt_bx_reject(bx, "AT", "empty");
        return;
    }
    if (!bt_bx_at_allowed(text))
    {
        /* 非白名单 AT 一律零 TX 拒绝：原始入口不得成为绕过 rate set 门禁、
         * 修改无关模块配置或污染在飞探针窗口的通道。 */
        bt_bx_reject(bx, "AT", "at-not-allowed");
        return;
    }
    if (bt_bx_streq_ci(text, "AT+REBOOT=1") != 0 && !bt_bx_at_reboot_allowed(bx))
    {
        bt_bx_reject(bx, "AT", "reboot-not-allowed");
        return;
    }
    if (!bt_bx_owns_idle(bx, epoch, "AT"))
    {
        return;
    }
    n = bx->ops->at_write(bx->ops->io, text, (unsigned)strlen(text));
    if (bt_bx_streq_ci(text, "AT+REBOOT=1") != 0)
    {
        /* 重启受理：模块即将回到上电态，重启前采集的两侧证据与 deferred/
         * seteff 观察一律作废（门禁因此要求重新取证后才能再次重启）。
         * 作废意味着此后没有「本代次的授权性证据」（ev_valid=0），而不是
         * 把证据重新打上当前代次的时间戳。
         * 本机速率、PENDING 事务与 old/target 保留：重启不改变本机 UART
         * 配置，事务仍需后续探针按实际 old/target 收口。
         * 计数口径为「已发出的受控重启尝试」，部分写出的同样计数——
         * 模块是否真的重启无法从 TX 字节数推定，按不确定处理并作废证据。 */
        bt_bx_probe_evidence_reset(bx);
        bx->deferred = 0u;
        bx->set_ineffective = 0u;
        bx->ev_valid = 0u;
        bx->reboots++;
    }
    bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), "AT");
    bt_bx_sb_str(&sb, "tx n=");
    bt_bx_sb_u32(&sb, n);
    bt_bx_sb_str(&sb, " epoch=");
    bt_bx_sb_u32(&sb, epoch);
    bt_bx_sb_str(&sb, "\r\n");
    bt_bx_write(bx, &sb);
}

static void bt_bx_cmd_uart(bt_bx_t *bx, const char *arg)
{
    uint32_t epoch;
    uint32_t rate;
    const char *rest;

    if (!bt_bx_take_epoch(bx, arg, &epoch, &rest, "UART"))
    {
        return;
    }
    if (!bt_bx_parse_u32(rest, &rate))
    {
        bt_bx_reject(bx, "UART", "bad-rate");
        return;
    }
    if (!bt_bx_rate_known(rate))
    {
        bt_bx_reject(bx, "UART", "rate-not-whitelisted");
        return;
    }
    if (bx->ops->epoch(bx->ops->io) != epoch)
    {
        bt_bx_reject(bx, "UART", "stale-epoch");
        return;
    }
    if (!bt_bx_owns_idle(bx, epoch, "UART"))
    {
        return;
    }
    (void)bt_bx_mcu_switch(bx, rate);
}

/* 探针使用位图按 step 隔离：step 前进即视为新一轮，位图整体清零。
 * 计数语义 = **接受即计数**：命令通过全部门禁即为「本 step 已用掉该档位」，
 * 其后无论本地切换失败（-1/-2/-3/-4）、查询超时、被中止，都不退额。
 * 因此同一档位的第二次尝试必须由操作者显式 `rate rearm` 前进 step，
 * 不存在「失败就免费重试」的路径，也堵住 A→B→A 交替速率绕过计数的做法。
 * 这是固件侧的局部限制；跨步骤的**累计操作台账**仍必须由执行者另记。 */
static void bt_bx_probe_used_sync(bt_bx_t *bx)
{
    if (bx->probe_used_step != bx->step)
    {
        bx->probe_used_mask = 0u;
        bx->probe_used_step = bx->step;
    }
}

static void bt_bx_probe_used_mark(bt_bx_t *bx, uint32_t baud)
{
    unsigned slot = bt_bx_rate_slot(baud);

    if (slot >= (unsigned)BT_BX_RATE_N)
    {
        return;
    }
    bt_bx_probe_used_sync(bx);
    bx->probe_used_mask |= (uint32_t)1u << slot;
}

static int bt_bx_probe_budget(bt_bx_t *bx, uint32_t baud)
{
    unsigned slot = bt_bx_rate_slot(baud);

    if (slot >= (unsigned)BT_BX_RATE_N)
    {
        return 0;
    }
    bt_bx_probe_used_sync(bx);
    return (bx->probe_used_mask & ((uint32_t)1u << slot)) ? 0 : 1;
}

static void bt_bx_cmd_probe(bt_bx_t *bx, const char *arg)
{
    uint32_t epoch;
    uint32_t rate;
    const char *rest;

    if (!bt_bx_take_epoch(bx, arg, &epoch, &rest, "PB"))
    {
        return;
    }
    if (!bt_bx_parse_u32(rest, &rate))
    {
        bt_bx_reject(bx, "PB", "bad-rate");
        return;
    }
    if (!bt_bx_rate_known(rate))
    {
        bt_bx_reject(bx, "PB", "rate-not-whitelisted");
        return;
    }
    if (bx->probe.active)
    {
        bt_bx_reject(bx, "PB", "probe-in-flight");
        return;
    }
    if (!bt_bx_probe_budget(bx, rate))
    {
        bt_bx_reject(bx, "PB", "already-probed-this-step");
        return;
    }
    if (bx->ops->epoch(bx->ops->io) != epoch)
    {
        bt_bx_reject(bx, "PB", "stale-epoch");
        return;
    }
    if (!bt_bx_owns_idle(bx, epoch, "PB"))
    {
        return;
    }
    /* 命令已被接受：先计入本 step 的档位用量，再做本地切换。切换失败
     * （含回读不确定的 -3）同样不退额，避免以失败换免费重试。 */
    bt_bx_probe_used_mark(bx, rate);
    /* 本地切到该速率只为本机收信；不改模块配置。 */
    if (bt_bx_mcu_switch(bx, rate) != 0)
    {
        return;
    }
    bt_bx_probe_abort(bx, BT_BX_ABORT_NONE); /* 清上一轮 abort 标记 */
    memset(&bx->probe, 0, sizeof(bx->probe));
    bx->probe.active = 1u;
    bx->probe.leg = 0u;
    bx->probe.baud = rate;
    bx->probe.epoch_at_start = epoch;
    bx->probe.step_at_start = bx->step;
    bt_bx_probe_send_leg(bx);
}

static void bt_bx_cmd_rate_set(bt_bx_t *bx, const char *arg)
{
    uint32_t epoch;
    uint32_t target;
    const char *rest;
    char cmd[24];
    char lbuf[BT_BX_LOG_CAP];
    bt_bx_sb_t sb;
    unsigned n;

    if (!bt_bx_take_epoch(bx, arg, &epoch, &rest, "RATE"))
    {
        return;
    }
    if (!bt_bx_parse_u32(rest, &target))
    {
        bt_bx_reject(bx, "RATE", "bad-target");
        return;
    }
    if (!bt_bx_rate_known(target))
    {
        bt_bx_reject(bx, "RATE", "target-not-whitelisted");
        return;
    }
    if (bx->rate_state != (uint8_t)BT_BX_STATE_KNOWN)
    {
        /* 未知状态停止盲目设置 */
        bt_bx_reject(bx, "RATE", "state-not-known");
        return;
    }
    if (bt_bx_evidence_current(bx) == 0)
    {
        /* KNOWN 位与证据代次不一致（证据已被会话边界作废）：改速资格来自
         * 「本代次确认过模块在 known 档位」，代次不符即不得改速。 */
        bt_bx_reject(bx, "RATE", "stale-evidence");
        return;
    }
    if (bx->probe.active)
    {
        /* 在飞探针的证据窗口属于当前 step。此处若改动 target/step，旧窗口的
         * 应答会落入新语义，因此一律拒绝，而不是显式中止：中止后重新取证
         * 必须由操作者显式重发命令，不在命令内部代做。 */
        bt_bx_reject(bx, "RATE", "probe-in-flight");
        return;
    }
    if (bx->known_baud != bx->mcu_baud)
    {
        bt_bx_reject(bx, "RATE", "mcu-baud-not-confirmed");
        return;
    }
    if (target == bx->known_baud)
    {
        bt_bx_reject(bx, "RATE", "target-equals-known");
        return;
    }
    if (bx->ops->epoch(bx->ops->io) != epoch)
    {
        bt_bx_reject(bx, "RATE", "stale-epoch");
        return;
    }
    if (!bt_bx_owns_idle(bx, epoch, "RATE"))
    {
        return;
    }
    /* 已确认的 old 上只发送一次设置命令；无应答不假定成功。 */
    bx->old_baud = bx->known_baud;
    bx->target_baud = target;
    bx->known_baud = 0u;
    bx->rate_state = (uint8_t)BT_BX_STATE_PENDING;
    bx->deferred = 0u;
    bx->set_ineffective = 0u;
    bx->step++;
    bt_bx_reset_ev(&bx->ev_old);
    bt_bx_reset_ev(&bx->ev_target);
    /* 事务本身是授权性证据（deferred 可换一次受控重启），按本代次打戳。 */
    bt_bx_evidence_stamp(bx);

    bt_bx_sb_init(&sb, cmd, sizeof(cmd));
    bt_bx_sb_str(&sb, "AT+UART=");
    bt_bx_sb_u32(&sb, bt_bx_rate_idx(target));
    n = bx->ops->at_write(bx->ops->io, cmd, sb.len);

    bt_bx_line_begin(&sb, lbuf, sizeof(lbuf), "RATE");
    bt_bx_sb_str(&sb, "set-tx n=");
    bt_bx_sb_u32(&sb, n);
    bt_bx_sb_str(&sb, " old=");
    bt_bx_sb_u32(&sb, bx->old_baud);
    bt_bx_sb_str(&sb, " target=");
    bt_bx_sb_u32(&sb, bx->target_baud);
    bt_bx_sb_str(&sb, " note=module-not-yet-switched\r\n");
    bt_bx_write(bx, &sb);
    bt_bx_log_state(bx, "pending");
}

static void bt_bx_cmd_rate_rearm(bt_bx_t *bx, const char *arg)
{
    uint32_t epoch;
    const char *rest;

    if (!bt_bx_take_epoch(bx, arg, &epoch, &rest, "RATE"))
    {
        return;
    }
    (void)rest;
    if (bx->ops->epoch(bx->ops->io) != epoch)
    {
        bt_bx_reject(bx, "RATE", "stale-epoch");
        return;
    }
    if (!bt_bx_owns_idle(bx, epoch, "RATE"))
    {
        return;
    }
    if (bx->probe.active)
    {
        /* 在飞探针仍属于当前 step。此处推进 step 会让旧窗口的应答变成
         * 「旧 step 结果到达」，虽然 bt_bx_probe_poll 会中止它，但中止本身
         * 会消耗一次证据窗口并可能掩盖操作者意图，故直接拒绝：
         * 先在 status 看到探针结束，再 rearm。 */
        bt_bx_reject(bx, "RATE", "probe-in-flight");
        return;
    }
    bx->step++;
    bx->probe.started = 0u;
    bt_bx_reset_ev(&bx->ev_old);
    bt_bx_reset_ev(&bx->ev_target);
    bt_bx_log_state(bx, "rearm");
}

static void bt_bx_exec(bt_bx_t *bx, const char *line)
{
    if (strcmp(line, "status") == 0)
    {
        bt_bx_cmd_status(bx);
        return;
    }
    if (strcmp(line, "rx!") == 0)
    {
        /* 显式丢弃采集缓冲：该窗口不再产生记录 */
        bx->cap_len = 0u;
        bx->cap_ovf = 0u;
        return;
    }
    if (strncmp(line, "at ", 3) == 0)
    {
        bt_bx_cmd_at(bx, line + 3);
        return;
    }
    if (strncmp(line, "uart ", 5) == 0)
    {
        bt_bx_cmd_uart(bx, line + 5);
        return;
    }
    if (strncmp(line, "probe ", 6) == 0)
    {
        bt_bx_cmd_probe(bx, line + 6);
        return;
    }
    if (strncmp(line, "rate set ", 9) == 0)
    {
        bt_bx_cmd_rate_set(bx, line + 9);
        return;
    }
    if (strncmp(line, "rate rearm ", 11) == 0)
    {
        bt_bx_cmd_rate_rearm(bx, line + 11);
        return;
    }
    bt_bx_reject(bx, "CMD", "unknown");
}

static void bt_bx_line_finish(bt_bx_t *bx)
{
    if (bx->line_over)
    {
        /* 超长：整条拒绝，绝不发送截断前缀 */
        bt_bx_reject(bx, "CMD", "line-too-long");
        bt_bx_line_reset(bx);
        return;
    }
    if (bx->line_bad)
    {
        bt_bx_reject(bx, "CMD", "illegal-byte");
        bt_bx_line_reset(bx);
        return;
    }
    if (bx->line_len == 0u)
    {
        return; /* 空行忽略，不计拒绝 */
    }
    bx->line[bx->line_len] = '\0';
    bt_bx_exec(bx, bx->line);
    bt_bx_line_reset(bx);
}

static void bt_bx_console_poll(bt_bx_t *bx)
{
    char buf[32];
    unsigned n;
    unsigned i;

    n = bx->ops->rtt_read(bx->ops->io, buf, sizeof(buf));
    for (i = 0u; i < n; ++i)
    {
        uint8_t ch = (uint8_t)buf[i];
        if (ch == (uint8_t)'\n' || ch == (uint8_t)'\r')
        {
            bt_bx_line_finish(bx);
            continue;
        }
        if (ch < 0x20u || ch >= 0x7Fu)
        {
            /* NUL/非法控制字符：整行拒绝，但仍继续消费到行尾 */
            bx->line_bad = 1u;
            continue;
        }
        if ((unsigned)bx->line_len + 1u >= BT_BX_LINE_CAP)
        {
            bx->line_over = 1u;
            continue;
        }
        bx->line[bx->line_len] = (char)ch;
        bx->line_len = (uint16_t)(bx->line_len + 1u);
    }
}

/* busy 期：有界消费并丢弃下行输入，清除半行与待执行命令。 */
static void bt_bx_discard_down(bt_bx_t *bx)
{
    char buf[32];
    unsigned total = 0u;

    while (total < BT_BX_BUSY_DISCARD)
    {
        unsigned n = bx->ops->rtt_read(bx->ops->io, buf, sizeof(buf));
        if (n == 0u)
        {
            break;
        }
        total += n;
    }
    bx->down_discarded += total;
}

/* ===================== 主轮询 ===================== */

static void bt_bx_poll(bt_bx_t *bx)
{
    uint32_t epoch;

    if (bx->ops->busy(bx->ops->io))
    {
        /* 忙：不输出观测，不执行命令；有界丢弃下行并清半行，禁止补执行 */
        bt_bx_discard_down(bx);
        bt_bx_line_reset(bx);
        if (bx->probe.active)
        {
            bt_bx_probe_abort(bx, BT_BX_ABORT_SESSION);
        }
        bx->cap_len = 0u;
        bx->cap_ovf = 0u;
        return;
    }

    epoch = bx->ops->epoch(bx->ops->io);
    /* 会话边界先作废授权性证据，再处理在飞探针：作废是状态事件，必须发生在
     * 本轮任何命令被执行（bt_bx_console_poll）之前，否则带当前 epoch 的命令
     * 会在旧证据尚未失效的窗口内被放行。 */
    bt_bx_evidence_expire(bx, epoch);
    if (bx->probe.active && bx->probe.epoch_at_start != epoch)
    {
        bt_bx_probe_abort(bx, BT_BX_ABORT_EPOCH);
    }

    if (bx->cap_len != 0u &&
        (uint32_t)(bx->ops->now_ms(bx->ops->io) - bx->cap_last_ms) >=
            BT_BX_QUIET_MS)
    {
        (void)bt_bx_capture_seal(bx);
    }

    bt_bx_emit(bx);
    bt_bx_probe_poll(bx);
    bt_bx_console_poll(bx);
}

#endif /* E_TRACK_BT_BAUD_EXPERIMENT_H */
