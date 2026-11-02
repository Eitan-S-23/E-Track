"""Decode original Android logger entries, bypassing the events text renderer."""
import hashlib
import struct

import runner as r

TAG = 0x45545035


def decode(raw, pid):
    messages, entries, _ = decode_prefix(raw, pid, allow_partial=False)
    return messages, entries


def decode_prefix(raw, pid, *, allow_partial=True):
    r.require(type(pid) is int and pid > 0, 'pinned Logcat PID required', 'EVIDENCE_GAP')
    offset, messages, entries = 0, [], 0
    partial = None
    while offset < len(raw):
        if len(raw)-offset < 4:
            r.require(allow_partial, 'partial binary Logcat header', 'EVIDENCE_GAP')
            partial = dict(offset=offset, bytes=len(raw)-offset, expectedBytes=None,
                           sha256=hashlib.sha256(raw[offset:]).hexdigest())
            break
        length, header = struct.unpack_from('<HH', raw, offset)
        r.require(header in (20, 24, 28) and 0 < length <= 5120, 'unknown binary Logcat entry', 'EVIDENCE_GAP')
        if len(raw)-offset < header+length:
            r.require(allow_partial, 'truncated binary Logcat entry', 'EVIDENCE_GAP')
            partial = dict(offset=offset, bytes=len(raw)-offset, expectedBytes=header+length,
                           sha256=hashlib.sha256(raw[offset:]).hexdigest())
            break
        entry_pid, tid, sec, ns = struct.unpack_from('<iiii', raw, offset+4)
        r.require(entry_pid > 0 and tid > 0 and sec > 0 and 0 <= ns < 1_000_000_000,
                  'binary Logcat process/clock mismatch', 'EVIDENCE_GAP')
        if header >= 24:
            r.require(struct.unpack_from('<I', raw, offset+20)[0] == 2,
                      'binary Logcat buffer is not events', 'EVIDENCE_GAP')
        body = raw[offset+header:offset+header+length]
        r.require(len(body)>=4, 'short event tag', 'EVIDENCE_GAP')
        # Bind the actual binary header identity, not just a command-line filter.
        if entry_pid == pid and struct.unpack_from('<I', body)[0] == TAG:
            r.require(len(body)>=9 and body[4]==2 and struct.unpack_from('<I', body,5)[0]==len(body)-9,
                      'noncanonical P35 binary string event', 'EVIDENCE_GAP')
            value=body[9:]
            r.require(value.startswith((b'OTA_P35_STATE ',b'OTA_P35_CAPTURE ',b'OTA_P35_ERROR ')) and
                      not any(x in value for x in (b'\0',b'\r',b'\n')),
                      'invalid P35 binary message framing', 'EVIDENCE_GAP')
            try:
                value.decode('utf8', 'strict')
            except UnicodeError as error:
                raise r.Stop('EVIDENCE_GAP', 'invalid binary message UTF-8') from error
            messages.append(value+b'\n')
        offset += header+length
        entries += 1
    return b''.join(messages), entries, partial


def audit_pair(live, terminal, pid, capture_id, original, states, status):
    prefix, count, tail = decode_prefix(live, pid)
    end, end_count = decode(terminal, pid)
    a = r.audit_logcat_mirror(prefix, capture_id, states, status)
    z = r.audit_logcat_mirror(end, capture_id, states, status)
    missing = sorted(set(a['missingSequences']) & set(z['missingSequences']))
    # Both sources remain separate originals, including any interrupted live
    # frame. This proves coverage, not a repaired or lossless live binary file.
    report = dict(source='diagnostic-only', captureId=capture_id, wireFormat='android-binary-events',
        live=a, terminal=z, liveEntries=count, terminalEntries=end_count, partialLiveTail=tail,
        liveWireSha256=hashlib.sha256(live).hexdigest(), terminalWireSha256=hashlib.sha256(terminal).hexdigest(),
        missingSequences=missing, originalRecords=len(states), nativeMirror=status, usedForInjection=False,
        retainedMatch=a['retainedMatch'] and z['retainedMatch'],
        completeCombinedCoverage=not missing and a['retainedMatch'] and z['retainedMatch'] and
            not a['parseErrors'] and not z['parseErrors'] and original.splitlines()[0] in prefix.splitlines() and
            original.splitlines()[-1] in end.splitlines(),
        exactLiveCaptureBytes=tail is None and prefix==original, exactEquality=tail is None and prefix==original)
    return report, prefix, end
