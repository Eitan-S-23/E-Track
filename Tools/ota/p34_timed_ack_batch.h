#ifndef E_TRACK_P34_TIMED_ACK_BATCH_H
#define E_TRACK_P34_TIMED_ACK_BATCH_H

#include <stdint.h>
#include <string.h>

/* Diagnostic candidate. Poll the oldest-byte deadline at every pump end;
 * scheduling stalls can delay that poll, so this is not a real-time guarantee. */
class P34TimedAckBatch
{
public:
    explicit P34TimedAckBatch(uint32_t hold_ms = 2u)
        : used_(0), active_(false), failed_(hold_ms > 2u),
          epoch_(0), first_ms_(0), hold_ms_(hold_ms) {}

    int begin(uint32_t epoch)
    {
        if (active_)
        {
            failed_ = true;
            return -1;
        }
        if (rebind(epoch) != 0) return -1;
        active_ = true;
        return 0;
    }

    int rebind(uint32_t epoch)
    {
        if (failed_ || (used_ && epoch != epoch_))
        {
            failed_ = true;
            return -1;
        }
        epoch_ = epoch;
        return 0;
    }

    template <typename Writer>
    int send(const uint8_t *bytes, uint16_t size, bool eligible,
             uint32_t now_ms, Writer write)
    {
        if (failed_) return -1;
        if (!bytes || !size)
        {
            failed_ = true;
            return -1;
        }
        if (!active_ || !eligible ||
            (size != 19u
#if defined(P34_OTA_PIPELINE) && P34_OTA_PIPELINE
             && size != 27u
#endif
            ))
        {
            if (drain(write) != 0) return -1;
            return transmit(bytes, size, write);
        }
#if defined(P34_OTA_PIPELINE) && P34_OTA_PIPELINE
        if (used_ && (size != frame_size_ || used_ + size > sizeof(bytes_)))
            if (drain(write) != 0) return -1;
        if (!used_)
        {
            first_ms_ = now_ms;
            frame_size_ = size;
        }
#else
        if (!used_) first_ms_ = now_ms;
#endif
        memcpy(bytes_ + used_, bytes, size);
        used_ = (uint16_t)(used_ + size);
#if defined(P34_OTA_PIPELINE) && P34_OTA_PIPELINE
        return used_ == 12u * frame_size_ ? drain(write) : 0;
#else
        return used_ == sizeof(bytes_) ? drain(write) : 0;
#endif
    }

    template <typename Writer>
    int end(uint32_t now_ms, bool session_active, Writer write)
    {
        if (failed_) return -1;
        active_ = false;
        return poll(now_ms, session_active, write);
    }

    template <typename Writer>
    int poll(uint32_t now_ms, bool session_active, Writer write)
    {
        if (failed_) return -1;
        if (!session_active || (used_ && (uint32_t)(now_ms - first_ms_) >= hold_ms_))
            return drain(write);
        return 0;
    }

    template <typename Writer>
    int drain(Writer write)
    {
        if (failed_) return -1;
        const uint16_t size = used_;
        used_ = 0;
        return size ? transmit(bytes_, size, write) : 0;
    }

private:
    template <typename Writer>
    int transmit(const uint8_t *bytes, uint16_t size, Writer write)
    {
        if (failed_) return -1;
        if (write(bytes, size) != 0)
        {
            failed_ = true;  // Never replay a failed or uncertain UART write.
            return -1;
        }
        return 0;
    }

    uint8_t bytes_[12u *
#if defined(P34_OTA_PIPELINE) && P34_OTA_PIPELINE
        27u
#else
        19u
#endif
    ];
    uint16_t used_;
#if defined(P34_OTA_PIPELINE) && P34_OTA_PIPELINE
    uint16_t frame_size_;
#endif
    bool active_;
    bool failed_;
    uint32_t epoch_;
    uint32_t first_ms_;
    const uint32_t hold_ms_;
};

#endif
