#ifndef ETRACK_BLUETOOTH_STARTUP_NAME_H
#define ETRACK_BLUETOOTH_STARTUP_NAME_H

#include <stdint.h>
#include <string.h>

namespace ETrackBluetooth
{
// Doc/ble.pdf: NAME is persistent and takes effect on the following REBOOT.
class StartupName
{
public:
    enum Result { NotAttempted, Unchanged, Updated, Rejected, TimedOut, TxTimedOut };
    StartupName() : result_(NotAttempted), elapsed_(0) {}
    Result result() const { return result_; }
    uint32_t elapsed() const { return elapsed_; }

    template<class Port>
    Result Run(Port& port)
    {
        if (result_ != NotAttempted) return result_;
        result_ = TimedOut;
        const uint32_t start = port.now();
        Drain(port);
        uint32_t phase = port.now();
        if (!Send(port, "AT+NAME?\r\n", phase)) return Finish(TxTimedOut, port.now() - start);
        if (Read(port, phase, true) == SameName) return Finish(Unchanged, port.now() - start);

        // A missing query reply does not authorize a different name or a retry loop.
        Drain(port);
        phase = port.now();
        if (!Send(port, "AT+NAME=E-Track\r\n", phase)) return Finish(TxTimedOut, port.now() - start);
        const Reply reply = Read(port, phase, false);
        return Finish(reply == Ok ? Updated : reply == Error ? Rejected : TimedOut, port.now() - start);
    }

private:
    enum Reply { SameName, OtherName, Ok, Error, Expired };
    Result result_;
    uint32_t elapsed_;
    Result Finish(Result value, uint32_t elapsed) { result_ = value; elapsed_ = elapsed; return value; }

    template<class Port> static void Drain(Port& port)
    {
        const uint32_t start = port.now();
        int pending = port.available();
        if (pending > 512) pending = 512;
        while (pending-- > 0 && (uint32_t)(port.now() - start) < 50u) (void)port.read();
    }

    template<class Port> static bool Send(Port& port, const char* command, uint32_t start)
    {
        while (!port.writable())
        {
            if ((uint32_t)(port.now() - start) >= 50u) return false;
            port.wait();
        }
        if ((uint32_t)(port.now() - start) >= 50u) return false;
        const unsigned bytes = (unsigned)strlen(command);
        return port.write(command, bytes) == bytes;
    }

    template<class Port> static Reply Read(Port& port, uint32_t start, bool query)
    {
        char line[40];
        unsigned length = 0;
        bool overflow = false;
        while ((uint32_t)(port.now() - start) < 300u)
        {
            const int byte = port.read();
            if (byte < 0) { port.wait(); continue; }
            if (byte == '\n')
            {
                if (!overflow && length > 0 && line[length - 1u] == '\r')
                {
                    --length;
                    if (length == 5u && memcmp(line, "ERROR", 5) == 0) return Error;
                    if (!query && length == 2u && memcmp(line, "OK", 2) == 0) return Ok;
                    if (query && length > 6u && memcmp(line, "+NAME:", 6) == 0)
                    {
                        unsigned offset = 6u;
                        while (offset < length && line[offset] == ' ') ++offset;
                        const unsigned bytes = length - offset;
                        if (bytes > 0u && bytes <= 20u)
                            return bytes == 7u && memcmp(line + offset, "E-Track", 7) == 0 ? SameName : OtherName;
                    }
                }
                length = 0; overflow = false;
            }
            else if (length < sizeof(line)) line[length++] = (char)byte;
            else overflow = true;
        }
        return Expired;
    }
};
}

#endif
