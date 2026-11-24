#include "../../Tools/ota/p34_timed_ack_batch.h"
#include <assert.h>
#include <stdio.h>
#include <vector>

struct Sink
{
    std::vector<uint8_t> bytes;
    std::vector<unsigned> sizes;
    int write(const uint8_t *p, uint16_t n)
    {
        bytes.insert(bytes.end(), p, p + n);
        sizes.push_back(n);
        return 0;
    }
};

int main()
{
    uint8_t ack[19] = {};
    const uint8_t control[] = {0xa5, 0x5a, 0x84};
    Sink sink;
    auto write = [&](const uint8_t *p, uint16_t n) { return sink.write(p, n); };
    P34TimedAckBatch batch;
    assert(batch.begin(1) == 0);
    assert(batch.send(ack, 19, true, 10, write) == 0);
    assert(batch.end(10, true, write) == 0 && sink.sizes.empty());
    assert(batch.begin(1) == 0);
    memset(ack, 1, sizeof(ack));
    assert(batch.send(ack, 19, true, 12, write) == 0);
    assert(batch.end(12, true, write) == 0 && sink.sizes.size() == 1);
    assert(sink.sizes[0] == 38);
    for (unsigned i = 0; i < 38; ++i) assert(sink.bytes[i] == i / 19);

    // Empty pumps still flush; new bytes must not extend the original deadline.
    assert(batch.begin(1) == 0);
    assert(batch.send(ack, 19, true, 20, write) == 0);
    assert(batch.end(20, true, write) == 0);
    assert(batch.begin(1) == 0);
    assert(batch.send(ack, 19, true, 21, write) == 0);
    assert(batch.end(21, true, write) == 0 && sink.sizes.size() == 1);
    assert(batch.begin(1) == 0);
    assert(batch.end(22, true, write) == 0 && sink.sizes.size() == 2);

    // Control/error/durable ACKs cannot overtake deferred ACK bytes.
    assert(batch.begin(1) == 0);
    assert(batch.send(ack, 19, true, 30, write) == 0);
    assert(batch.send(control, 3, false, 30, write) == 0);
    assert(sink.sizes.size() == 4 && sink.sizes[2] == 19 && sink.sizes[3] == 3);
    assert(batch.send(ack, 19, true, 30, write) == 0);
    assert(batch.send(ack, 19, false, 30, write) == 0 && sink.sizes.size() == 6);
    assert(batch.end(30, true, write) == 0);

    // Full batches flush immediately, independent of elapsed time.
    assert(batch.begin(1) == 0);
    for (unsigned i = 0; i < 12; ++i)
        assert(batch.send(ack, 19, true, 40, write) == 0);
    assert(sink.sizes.size() == 7 && sink.sizes.back() == 228);
    assert(batch.send(ack, 19, true, 40, write) == 0);
    assert(batch.end(40, false, write) == 0 && sink.sizes.back() == 19);
    assert(batch.begin(2) == 0 && batch.end(40, true, write) == 0);

    // Explicit overlay-release drain is legal inside the active pump.
    assert(batch.begin(2) == 0);
    assert(batch.send(ack, 19, true, 50, write) == 0);
    assert(batch.drain(write) == 0 && batch.end(50, false, write) == 0);
    assert(batch.begin(3) == 0);
    assert(batch.send(ack, 19, true, UINT32_MAX, write) == 0);
    unsigned before = (unsigned)sink.sizes.size();
    assert(batch.end(0, true, write) == 0 && sink.sizes.size() == before);
    assert(batch.begin(3) == 0);
    assert(batch.end(1, true, write) == 0 && sink.sizes.size() == before + 1);

    // Uncertain writes are sticky failures and are never retried.
    unsigned calls = 0;
    auto fail = [&](const uint8_t *, uint16_t) { ++calls; return -1; };
    P34TimedAckBatch bad;
    assert(bad.begin(1) == 0 && bad.send(ack, 19, true, 0, fail) == 0);
    assert(bad.end(2, true, fail) == -1 && calls == 1);
    assert(bad.begin(1) == -1 && bad.drain(fail) == -1);
    assert(bad.send(control, 3, false, 3, fail) == -1 && calls == 1);

    P34TimedAckBatch stale;
    assert(stale.begin(1) == 0 && stale.send(ack, 19, true, 0, write) == 0);
    assert(stale.end(0, true, write) == 0 && stale.begin(2) == -1);
    before = (unsigned)sink.sizes.size();
    assert(stale.drain(write) == -1 && sink.sizes.size() == before);
    P34TimedAckBatch nested;
    assert(nested.begin(1) == 0 && nested.begin(1) == -1);
    P34TimedAckBatch invalid(3);
    assert(invalid.begin(1) == -1);

    // BEGIN can acquire the overlay (and change epoch) inside one pump.
    P34TimedAckBatch acquired;
    assert(acquired.begin(0) == 0 && acquired.rebind(1) == 0);
    assert(acquired.send(control, 3, false, 0, write) == 0);
    assert(acquired.send(ack, 19, true, 0, write) == 0);
    assert(acquired.end(0, true, write) == 0 && acquired.begin(1) == 0);
    assert(acquired.drain(write) == 0 && acquired.end(0, false, write) == 0);
    assert(acquired.begin(2) == 0 && acquired.end(0, false, write) == 0);
    P34TimedAckBatch changed_pending;
    assert(changed_pending.begin(1) == 0);
    assert(changed_pending.send(ack, 19, true, 0, write) == 0);
    before = (unsigned)sink.sizes.size();
    assert(changed_pending.rebind(2) == -1 && changed_pending.drain(write) == -1);
    assert(sink.sizes.size() == before);

    // Hold zero is byte/call equivalent to the prior per-pump policy.
    Sink baseline;
    auto baseline_write = [&](const uint8_t *p, uint16_t n) { return baseline.write(p, n); };
    P34TimedAckBatch immediate(0);
    for (unsigned i = 0; i < 100; ++i)
    {
        assert(immediate.begin(7) == 0);
        assert(immediate.send(ack, 19, true, i, baseline_write) == 0);
        assert(immediate.end(i, true, baseline_write) == 0);
    }
    assert(baseline.sizes.size() == 100 && baseline.bytes.size() == 1900);
#if defined(P34_OTA_PIPELINE) && P34_OTA_PIPELINE
    uint8_t credit[27] = {};
    Sink v2sink;
    auto v2write = [&](const uint8_t *p, uint16_t n) { return v2sink.write(p, n); };
    P34TimedAckBatch v2;
    assert(v2.begin(1) == 0);
    for (unsigned i = 0; i < 12; ++i)
    {
        memset(credit, (int)i, sizeof(credit));
        assert(v2.send(credit, 27, true, 10, v2write) == 0);
        assert(v2sink.sizes.size() == (i == 11 ? 1u : 0u));
    }
    assert(v2sink.sizes[0] == 324 && v2sink.bytes.size() == 324);
    for (unsigned i = 0; i < 324; ++i) assert(v2sink.bytes[i] == i / 27);
    assert(v2.send(credit, 27, true, 10, v2write) == 0);
    assert(v2.end(11, true, v2write) == 0 && v2sink.sizes.size() == 1);
    assert(v2.begin(1) == 0 && v2.end(12, true, v2write) == 0);
    assert(v2sink.sizes.size() == 2 && v2sink.sizes.back() == 27);
    assert(v2.begin(1) == 0 && v2.send(credit, 27, true, 20, v2write) == 0);
    assert(v2.send(ack, 19, true, 20, v2write) == 0);
    assert(v2sink.sizes.back() == 27);
    assert(v2.send(credit, 27, false, 20, v2write) == 0);
    assert(v2sink.sizes[v2sink.sizes.size() - 2] == 19 && v2sink.sizes.back() == 27);
    assert(v2.end(20, false, v2write) == 0);
    puts("V2_ACK_BATCH_PASS full12 deadline mixed-length durable-flush byte-order");
#endif
    puts("TIMED_ACK_BATCH_PASS");
    return 0;
}
