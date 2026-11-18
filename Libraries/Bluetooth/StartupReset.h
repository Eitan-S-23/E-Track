#ifndef ETRACK_BLUETOOTH_STARTUP_RESET_H
#define ETRACK_BLUETOOTH_STARTUP_RESET_H

#include <stdint.h>
#include <string.h>

namespace ETrackBluetooth
{
// Startup only: invalidate a radio link that survived an MCU-only reset.
class StartupReset
{
public:
    enum Result { NotAttempted, Ready, TimedOut, TxTimedOut };
    StartupReset() : result_(NotAttempted), elapsed_(0) {}
    Result result() const { return result_; }
    uint32_t elapsed() const { return elapsed_; }

    template<class Port>
    Result Run(Port& port)
    {
        if (result_ != NotAttempted) return result_;
        result_ = TimedOut;
        const uint32_t start = port.now();

        // A queued power-on READY must not acknowledge this new reset.
        int pending = port.available();
        if (pending > 512) pending = 512;
        while (pending-- > 0) (void)port.read();

        static const char command[] = "AT+REBOOT=1\r\n";
        while (!port.writable())
        {
            if ((uint32_t)(port.now() - start) >= 50u)
                return Finish(TxTimedOut, port.now() - start);
            port.wait();
        }
        if ((uint32_t)(port.now() - start) >= 50u)
            return Finish(TxTimedOut, port.now() - start);
        // Keep the AT command in one serial burst, as in the qualified writer.
        if (port.write(command, sizeof(command) - 1u) != sizeof(command) - 1u)
            return Finish(TxTimedOut, port.now() - start);

        char line[16];
        unsigned length = 0;
        bool overflow = false, acknowledged = false;
        while ((uint32_t)(port.now() - start) < 1000u)
        {
            const int byte = port.read();
            if (byte < 0) { port.wait(); continue; }
            if (byte == '\n')
            {
                if (!overflow && length > 0 && line[length - 1u] == '\r')
                {
                    --length;
                    if (length == 2u && memcmp(line, "OK", 2) == 0) acknowledged = true;
                    if (acknowledged && length == 6u && memcmp(line, "+READY", 6) == 0)
                        return Finish(Ready, port.now() - start);
                }
                length = 0; overflow = false;
            }
            else if (length < sizeof(line)) line[length++] = (char)byte;
            else overflow = true;
        }
        return Finish(TimedOut, port.now() - start);
    }

private:
    Result result_;
    uint32_t elapsed_;
    Result Finish(Result value, uint32_t elapsed)
    {
        result_ = value; elapsed_ = elapsed;
        return result_;
    }
};
}

#endif
