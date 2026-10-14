#ifndef P34_ACK_BATCH_H
#define P34_ACK_BATCH_H

#include <stdint.h>
#include <string.h>

/* Diagnostic transport batching: preserve every byte and FIFO order. */
class P34AckBatch
{
public:
    P34AckBatch() : used_(0), active_(false), failed_(false) {}

    int begin()
    {
        if (active_ || used_ || failed_) return -1;
        active_ = true;
        return 0;
    }

    template <typename Writer>
    int send(const uint8_t *bytes, uint16_t size, bool eligible, Writer write)
    {
        if (failed_) return -1;
        if (!active_ || !eligible || size != 19u)
        {
            if (flush(write) != 0) return -1;
            return transmit(bytes, size, write);
        }
        memcpy(bytes_ + used_, bytes, size);
        used_ = (uint16_t)(used_ + size);
        return used_ == sizeof(bytes_) ? flush(write) : 0;
    }

    template <typename Writer>
    int end(Writer write)
    {
        active_ = false;
        return flush(write);
    }

private:
    template <typename Writer>
    int transmit(const uint8_t *bytes, uint16_t size, Writer write)
    {
        if (failed_) return -1;
        if (write(bytes, size) != 0)
        {
            failed_ = true;  // An uncertain UART write is never replayed.
            return -1;
        }
        return 0;
    }

    template <typename Writer>
    int flush(Writer write)
    {
        if (failed_) return -1;
        const uint16_t size = used_;
        used_ = 0;
        return size ? transmit(bytes_, size, write) : 0;
    }

    uint8_t bytes_[12u * 19u];
    uint16_t used_;
    bool active_;
    bool failed_;
};

#endif
