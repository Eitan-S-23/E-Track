#include "Bluetooth/StartupName.h"
#include <assert.h>
#include <stdio.h>
#include <string>
#include <vector>

using ETrackBluetooth::StartupName;

struct Port
{
    struct Byte { uint32_t at; unsigned char value; };
    uint32_t clock = 0, start = 0, replyDelay = 5, spacing = 0;
    bool writableNow = true, noise = false, partial = false;
    unsigned consumed = 0;
    std::string query = "+NAME: XTrace\r\n", reply = "OK\r\n";
    std::vector<std::string> commands;
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
        if (noise && !commands.empty()) { ++clock; return 'x'; }
        if (available() == 0) return -1;
        ++clock;
        return bytes[consumed++].value;
    }
    bool writable() { return writableNow; }
    unsigned write(const char* command, unsigned length)
    {
        commands.push_back(std::string(command, length));
        if (partial) return 2;
        const std::string& response = commands.back() == "AT+NAME?\r\n" ? query : reply;
        for (unsigned i = 0; i < response.size(); ++i)
            bytes.push_back({(uint32_t)(clock - start) + replyDelay + i * spacing, (unsigned char)response[i]});
        return length;
    }
    void wait() { ++clock; }
};

int main(int argc, char** argv)
{
    assert(argc == 2);
    const std::string name(argv[1]);
    Port port;
    StartupName naming;
    StartupName::Result expected = StartupName::Updated;
    if (name == "unchanged") { port.query = "+NAME: E-Track\r\n"; expected = StartupName::Unchanged; }
    else if (name == "unchanged_compact") { port.query = "+NAME:E-Track\r\n"; expected = StartupName::Unchanged; }
    else if (name == "legacy_hyphen") port.query = "+NAME: X-Trace\r\n";
    else if (name == "fragmented") port.spacing = 5;
    else if (name == "wrap") port.start = port.clock = UINT32_MAX - 10u;
    else if (name == "silent") { port.query.clear(); port.reply.clear(); expected = StartupName::TimedOut; }
    else if (name == "query_silent") port.query.clear();
    else if (name == "rejected") { port.reply = "ERROR\r\n"; expected = StartupName::Rejected; }
    else if (name == "echo_is_not_ack") { port.reply = "AT+NAME=E-Track\r\n"; expected = StartupName::TimedOut; }
    else if (name == "bad_ack") { port.reply = "notOK\r\nOK_extra\r\nOK\n"; expected = StartupName::TimedOut; }
    else if (name == "noise") { port.noise = true; expected = StartupName::TimedOut; }
    else if (name == "stale_name") {
        for (char c : std::string("+NAME: E-Track\r\n")) port.bytes.push_back({0, (unsigned char)c});
    }
    else if (name == "tx_blocked") { port.writableNow = false; expected = StartupName::TxTimedOut; }
    else if (name == "tx_partial") { port.partial = true; expected = StartupName::TxTimedOut; }
    else if (name == "line_recovery") port.query = std::string(50, 'x') + "\r\n+NAME: X-Trace\r\n";
    else if (name == "bad_query") port.query = "+NAME_extra: E-Track\r\n";
    else assert(name == "rename_once");

    assert(naming.Run(port) == expected);
    assert(naming.result() == expected);
    assert(naming.elapsed() <= 700u);
    assert(port.commands.size() <= 2u);
    if (!port.commands.empty()) assert(port.commands[0] == "AT+NAME?\r\n");
    if (port.commands.size() == 2u) assert(port.commands[1] == "AT+NAME=E-Track\r\n");
    if (expected == StartupName::Unchanged) assert(port.commands.size() == 1u);
    if (expected == StartupName::Updated || expected == StartupName::Rejected) assert(port.commands.size() == 2u);
    const auto commands = port.commands;
    const uint32_t clock = port.clock;
    assert(naming.Run(port) == expected);
    assert(port.commands == commands && port.clock == clock);
    printf("PASS name_%s\n", name.c_str());
}
