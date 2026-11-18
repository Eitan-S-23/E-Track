#include "Bluetooth/StartupReset.h"
#include <assert.h>
#include <stdio.h>
#include <string>
#include <vector>

using ETrackBluetooth::StartupReset;

struct Port
{
    struct Byte { uint32_t at; unsigned char value; };
    uint32_t clock = 0, start = 0, replyDelay = 5, spacing = 0;
    bool writableNow = true, noise = false;
    unsigned stallAfter = 100, consumed = 0, waits = 0, writes = 0;
    std::string sent, reply = "OK\r\n+READY\r\n";
    std::vector<Byte> bytes;
    uint32_t now() { return clock; }
    int available()
    {
        unsigned count = 0;
        for (unsigned i = consumed; i < bytes.size(); ++i)
        {
            if ((uint32_t)(clock - start) < bytes[i].at) break;
            ++count;
        }
        return (int)count;
    }
    int read()
    {
        if (noise && !sent.empty()) { ++clock; return 'x'; }
        if (available() == 0) return -1;
        ++clock;
        return bytes[consumed++].value;
    }
    bool writable() { return writableNow && sent.size() < stallAfter; }
    unsigned write(const char* command, unsigned length)
    {
        ++writes;
        const unsigned count = length < stallAfter ? length : stallAfter;
        sent.append(command, count);
        if (sent == "AT+REBOOT=1\r\n")
        {
            for (unsigned i = 0; i < reply.size(); ++i)
                bytes.push_back({replyDelay + i * spacing, (unsigned char)reply[i]});
        }
        return count;
    }
    void wait() { ++clock; ++waits; }
    void stale(const std::string& text)
    {
        for (char c : text) bytes.push_back({0, (unsigned char)c});
    }
};

int main(int argc, char** argv)
{
    assert(argc == 2);
    const std::string name(argv[1]);
    Port port;
    StartupReset reset;
    StartupReset::Result expected = StartupReset::Ready;
    if (name == "ready_preserves_new_link") port.reply += "!ETC1|HELLO|new\n";
    else if (name == "fragmented") port.spacing = 20;
    else if (name == "wrap") port.start = port.clock = UINT32_MAX - 10u;
    else if (name == "silent" || name == "timeout_once") { port.reply.clear(); expected = StartupReset::TimedOut; }
    else if (name == "no_ok") { port.reply = "+READY\r\n"; expected = StartupReset::TimedOut; }
    else if (name == "bad_ready") { port.reply = "OK\r\n+READY_extra\r\n"; expected = StartupReset::TimedOut; }
    else if (name == "late") { port.replyDelay = 1001; expected = StartupReset::TimedOut; }
    else if (name == "noise") { port.noise = true; expected = StartupReset::TimedOut; }
    else if (name == "stale_ready") { port.stale("OK\r\n+READY\r\n"); port.reply.clear(); expected = StartupReset::TimedOut; }
    else if (name == "tx_blocked") { port.writableNow = false; expected = StartupReset::TxTimedOut; }
    else if (name == "tx_partial") { port.stallAfter = 5; expected = StartupReset::TxTimedOut; }
    else if (name == "line_recovery") port.reply = std::string(64, 'x') + "\r\nnot+READY\r\nOK\r\n+READY\r\n";
    else assert(name == "ready_once");

    assert(reset.Run(port) == expected);
    assert(reset.result() == expected);
    assert(reset.elapsed() <= 1000);
    assert(port.sent.find("RESET") == std::string::npos);
    if (expected == StartupReset::TxTimedOut)
    {
        assert(reset.elapsed() == (name == "tx_partial" ? 0u : 50u));
        assert(port.sent.size() == (name == "tx_partial" ? 5u : 0u));
    }
    else assert(port.sent == "AT+REBOOT=1\r\n");
    assert(port.writes == (name == "tx_blocked" ? 0u : 1u));
    if (expected == StartupReset::TimedOut) assert(reset.elapsed() == 1000);
    if (name == "ready_preserves_new_link")
    {
        std::string remaining;
        while (port.available()) remaining += (char)port.read();
        assert(remaining == "!ETC1|HELLO|new\n");
    }
    const std::string sent = port.sent;
    const uint32_t clock = port.clock;
    const unsigned consumed = port.consumed;
    assert(reset.Run(port) == expected);
    assert(port.sent == sent && port.clock == clock && port.consumed == consumed);
    printf("PASS %s\n", name.c_str());
}
