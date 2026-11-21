#ifndef ETRACK_COMPANION_CONTROL_H
#define ETRACK_COMPANION_CONTROL_H

#include "Common/HAL/CompanionUpdate.h"
#include <stdio.h>
#include <string.h>

namespace ETrackCompanion
{
// Shared by firmware and host tests. No allocation, UI, network or Flash writes.
class Control
{
public:
    typedef bool (*Send)(void*, const char*, unsigned);
    typedef const char* (*ReadUid)(void*);
    Control(Send sender, void* context, ReadUid readUid = NULL)
        : sender(sender), context(context), readUid(readUid), length(0), dropping(false), busy(false),
          sequence(0), offerTick(0), waitTick(0), waitMs(0), byteTick(0),
          installPending(false), installTick(0)
    {
        memset(&value, 0, sizeof(value));
        shownSha[0] = '\0';
        consumedOffer[0] = '\0';
        SetStatus("PHONE_REQUIRED");
    }

    const HAL::CompanionUpdateInfo& Info() const { return value; }

    static uint16_t Crc(const char* bytes, unsigned count)
    {
        uint16_t crc = 0xffffu;
        for (unsigned i = 0; i < count; ++i)
        {
            crc ^= (uint16_t)((uint8_t)bytes[i] << 8);
            for (unsigned bit = 0; bit < 8; ++bit)
                crc = (uint16_t)((crc & 0x8000u) ? (crc << 1) ^ 0x1021u : crc << 1);
        }
        return crc;
    }

    void Poll(uint32_t now, bool binaryActive)
    {
        bool wasBusy = busy;
        busy = binaryActive;
        if (busy)
        {
            installPending = false;
            length = 0; dropping = false;
            value.hasOffer = false; value.prompt = false; value.checking = false;
            SetStatus("UPGRADING");
            return;
        }
        if (wasBusy) SetStatus("PHONE_REQUIRED");
        if (installPending && (uint32_t)(now - installTick) >= 120000u)
            CancelInstall();
        if (value.hasOffer && (uint32_t)(now - offerTick) >= 300000u)
        {
            value.hasOffer = false; value.prompt = false;
            SetStatus("PHONE_REQUIRED");
        }
        if (value.checking && (uint32_t)(now - waitTick) >= waitMs)
        {
            value.checking = false;
            SetStatus("PHONE_REQUIRED");
        }
    }

    bool Feed(uint8_t byte, uint32_t now)
    {
        if (busy) return false;
        if ((length != 0 || dropping) && (uint32_t)(now - byteTick) > 2000u) { length = 0; dropping = false; }
        byteTick = now;
        if (length == 0 && !dropping && byte != '!') return false;
        if (byte == '\n')
        {
            if (!dropping && length != 0) { line[length] = '\0'; Parse(now); }
            length = 0; dropping = false;
            return true;
        }
        if (byte < 33u || byte > 126u || length >= sizeof(line) - 1u)
        {
            dropping = true; length = 0;
        }
        else if (!dropping) line[length++] = (char)byte;
        return true;
    }

    bool Check(uint32_t now)
    {
        if (busy || value.session[0] == '\0') { SetStatus(busy ? "BUSY" : "PHONE_REQUIRED"); return false; }
        if (value.checking) return false;
        installPending = false;
        if (++sequence == 0) ++sequence;
        value.request = sequence;
        if (!Emit("CHECK", "")) { SetStatus("PHONE_REQUIRED"); return false; }
        value.hasOffer = false; value.prompt = false;
        Wait("CHECKING", now, 10000u);
        return true;
    }

    bool Choose(bool updateNow, uint32_t now)
    {
        Poll(now, busy);
        if (busy || !value.hasOffer) return false;
        char fields[160];
        int count = snprintf(fields, sizeof(fields), "|%s|%lu|%s|%s", value.offer,
            (unsigned long)value.version, value.packageSha256, updateNow ? "NOW" : "LATER");
        if (count < 0 || (unsigned)count >= sizeof(fields) || !Emit("CHOICE", fields)) return false;
        strcpy(consumedOffer, value.offer);
        value.hasOffer = false; value.prompt = false;
        installPending = updateNow;
        if (updateNow) { installTick = now; Wait("CHECKING", now, 120000u); }
        else { value.checking = false; SetStatus("DEFERRED"); }
        return true;
    }

    void Presented()
    {
        if (busy || !value.hasOffer) return;
        strcpy(shownSha, value.packageSha256);
        value.prompt = false;
        Receipt("SHOWN");
    }

    bool Matches(const HAL::CompanionUpdateInfo* displayed) const
    {
        return displayed != NULL && HAL::CompanionSameOffer(*displayed, value);
    }

    bool InstallPending(uint32_t now)
    {
        Poll(now, busy);
        return installPending;
    }

    void CancelInstall()
    {
        if (!installPending) return;
        installPending = false;
        value.checking = false;
        SetStatus("PHONE_REQUIRED");
    }

    void SetStatus(const char* status)
    {
        snprintf(value.status, sizeof(value.status), "%s", status);
    }

private:
    Send sender;
    void* context;
    ReadUid readUid;
    HAL::CompanionUpdateInfo value;
    char line[320];
    char shownSha[65];
    char consumedOffer[33];
    unsigned length;
    bool dropping, busy;
    uint32_t sequence, offerTick, waitTick, waitMs, byteTick;
    bool installPending;
    uint32_t installTick;

    static bool Hex(const char* text, unsigned count)
    {
        if (strlen(text) != count) return false;
        for (unsigned i = 0; i < count; ++i)
            if (!((text[i] >= '0' && text[i] <= '9') || (text[i] >= 'a' && text[i] <= 'f'))) return false;
        return true;
    }

    static bool Number(const char* text, uint32_t* output)
    {
        unsigned n = (unsigned)strlen(text);
        if (n == 0 || n > 10 || (n > 1 && text[0] == '0')) return false;
        uint32_t result = 0;
        for (unsigned i = 0; i < n; ++i)
        {
            if (text[i] < '0' || text[i] > '9') return false;
            unsigned digit = (unsigned)(text[i] - '0');
            if (result > (UINT32_MAX - digit) / 10u) return false;
            result = result * 10u + digit;
        }
        *output = result;
        return true;
    }

    void EmitUid(const char* session)
    {
        const char* uid = readUid ? readUid(context) : NULL;
        if (busy || sender == NULL || uid == NULL || !Hex(uid, 24)) return;
        char body[80], output[88];
        snprintf(body, sizeof(body), "!ETC1|UID|%s|0|%s", session, uid);
        snprintf(output, sizeof(output), "%s*%04x\n", body, (unsigned)Crc(body, (unsigned)strlen(body)));
        (void)sender(context, output, (unsigned)strlen(output));
    }

    bool Emit(const char* kind, const char* fields)
    {
        if (busy || sender == NULL) return false;
        char output[320];
        int count = snprintf(output, sizeof(output), "!ETC1|%s|%s|%lu%s", kind, value.session,
            (unsigned long)value.request, fields);
        if (count < 0 || (unsigned)count + 6u >= sizeof(output)) return false;
        snprintf(output + count, sizeof(output) - (unsigned)count, "*%04x\n", (unsigned)Crc(output, (unsigned)count));
        return sender(context, output, (unsigned)strlen(output));
    }

    void Receipt(const char* kind)
    {
        char fields[104];
        snprintf(fields, sizeof(fields), "|%s|%s", value.offer, value.packageSha256);
        (void)Emit(kind, fields);
    }

    void Wait(const char* status, uint32_t now, uint32_t timeout)
    {
        SetStatus(status); value.checking = true; waitTick = now; waitMs = timeout;
    }

    void Parse(uint32_t now)
    {
        char* star = strrchr(line, '*');
        if (star == NULL || !Hex(star + 1, 4)) return;
        unsigned expected = 0;
        for (unsigned i = 1; i <= 4; ++i)
            expected = expected * 16u + (unsigned)(star[i] <= '9' ? star[i] - '0' : star[i] - 'a' + 10);
        if (Crc(line, (unsigned)(star - line)) != expected) return;
        *star = '\0';
        char* fields[10];
        unsigned count = 0;
        char* start = line;
        for (;;)
        {
            if (count >= 10) return;
            fields[count++] = start;
            char* separator = strchr(start, '|');
            if (separator == NULL) break;
            *separator = '\0'; start = separator + 1;
        }
        uint32_t request;
        if (count < 4 || strcmp(fields[0], "!ETC1") != 0 || !Hex(fields[2], 32) || !Number(fields[3], &request)) return;
        if (strcmp(fields[1], "IDENTIFY") == 0 && count == 4 && request == 0)
        {
            EmitUid(fields[2]);
            return;
        }
        if (strcmp(fields[1], "HELLO") == 0 && count == 4 && request == 0)
        {
            if (strcmp(value.session, fields[2]) != 0)
            {
                const uint32_t revision = value.offerRevision + 1u;
                memset(&value, 0, sizeof(value));
                value.offerRevision = revision;
                installPending = false;
                strcpy(value.session, fields[2]); sequence = 0;
                SetStatus("CONNECTED");
            }
            uint32_t previous = value.request; value.request = 0;
            (void)Emit("CAPS", "|1");
            EmitUid(fields[2]);
            value.request = previous;
            return;
        }
        if (strcmp(fields[2], value.session) != 0 ||
            (request != value.request && (request != 0 || value.checking))) return;
        if (strcmp(fields[1], "STATE") == 0 && count == 5)
        {
            const char* state = fields[4];
            if (strcmp(state, "CHECKING") == 0) { value.request = request; Wait(state, now, 120000u); return; }
            if (strcmp(state, "STARTING") == 0) { value.request = request; value.hasOffer = false; value.prompt = false; Wait(state, now, 120000u); return; }
            if (strcmp(state, "DOWNLOADING") == 0 || strcmp(state, "VERIFYING") == 0)
                { value.request = request; Wait(state, now, 600000u); return; }
            const char* allowed[] = {"NO_UPDATE", "DEFERRED", "BUSY", "NO_NETWORK", "PHONE_REQUIRED",
                "INCOMPATIBLE", "FAILED", "STARTING", "COMPLETE", "WAIT_WIFI"};
            for (unsigned i = 0; i < sizeof(allowed) / sizeof(allowed[0]); ++i)
                if (strcmp(state, allowed[i]) == 0)
                {
                    installPending = false;
                    value.checking = false; value.hasOffer = false; value.prompt = false;
                    SetStatus(state); return;
                }
        }
        if (strcmp(fields[1], "OFFER") == 0 && count == 9)
        {
            uint32_t version;
            if (!Hex(fields[4], 32) || !Number(fields[5], &version) || version == 0 || version > 2100000000u ||
                !Hex(fields[6], 64) || !Hex(fields[7], 64) ||
                (strcmp(fields[8], "0") != 0 && strcmp(fields[8], "1") != 0)) return;
            // Exact retransmission acknowledges again without restarting its expiry.
            bool same = value.hasOffer && strcmp(value.offer, fields[4]) == 0 &&
                value.version == version && strcmp(value.packageSha256, fields[6]) == 0 &&
                strcmp(value.targetSha256, fields[7]) == 0 && value.request == request;
            if (strcmp(consumedOffer, fields[4]) == 0) return;
            if (strcmp(value.offer, fields[4]) == 0 && !same) return;
            if (!same)
            {
                installPending = false;
                ++value.offerRevision;
                strcpy(value.offer, fields[4]); strcpy(value.packageSha256, fields[6]); strcpy(value.targetSha256, fields[7]);
                value.version = version; value.request = request; offerTick = now;
                value.hasOffer = true; value.checking = false;
                value.prompt = fields[8][0] == '1' && strcmp(shownSha, value.packageSha256) != 0;
                SetStatus("READY");
            }
            Receipt("SEEN");
        }
    }
};
}

#endif
