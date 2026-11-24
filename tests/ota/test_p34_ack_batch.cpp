#include "../../Tools/ota/p34_ack_batch.h"
#include <assert.h>
#include <vector>

int main()
{
    std::vector<uint8_t> output;
    std::vector<unsigned> sizes;
    auto writer = [&](const uint8_t *bytes, uint16_t size) {
        output.insert(output.end(), bytes, bytes + size);
        sizes.push_back(size);
        return 0;
    };
    uint8_t ack[19] = {};
    P34AckBatch batch;
    assert(batch.begin() == 0);
    for (unsigned i = 0; i < 12; ++i)
    {
        memset(ack, i, sizeof(ack));
        assert(batch.send(ack, sizeof(ack), true, writer) == 0);
        assert(sizes.size() == (i == 11 ? 1u : 0u));
    }
    assert(sizes[0] == 228);
    for (unsigned i = 0; i < output.size(); ++i) assert(output[i] == i / 19);
    assert(batch.end(writer) == 0 && sizes.size() == 1);

    assert(batch.begin() == 0);
    assert(batch.send(ack, 19, true, writer) == 0);
    const uint8_t control[] = {0xa5, 0x5a, 0x84};
    assert(batch.send(control, 3, false, writer) == 0);
    assert(sizes.size() == 3 && sizes[1] == 19 && sizes[2] == 3);
    assert(batch.end(writer) == 0);
    assert(batch.send(ack, 19, true, writer) == 0 && sizes.size() == 4);

    assert(batch.begin() == 0);
    assert(batch.begin() == -1);
    assert(batch.send(ack, 19, true, writer) == 0);
    assert(batch.end(writer) == 0 && sizes.size() == 5 && sizes.back() == 19);

    assert(batch.begin() == 0);
    assert(batch.send(ack, 18, true, writer) == 0 && sizes.back() == 18);
    assert(batch.end(writer) == 0);

    unsigned attempts = 0;
    auto failure = [&](const uint8_t *, uint16_t) { ++attempts; return -1; };
    P34AckBatch bad;
    assert(bad.begin() == 0);
    assert(bad.send(ack, 19, true, failure) == 0);
    assert(bad.send(control, 3, false, failure) == -1);
    assert(attempts == 1);
    assert(bad.end(failure) == -1 && bad.begin() == -1);
    assert(bad.send(ack, 19, false, failure) == -1 && attempts == 1);
    return 0;
}
