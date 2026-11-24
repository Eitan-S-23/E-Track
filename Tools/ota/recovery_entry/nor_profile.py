"""Pinned SFDP command geometry/timing only; never configure QE or protection."""
import hashlib
import struct

from .probe import require

SFDP_SHA = '19cbc7362f912e2b0700516740e3d781136c0c9e5ae4a5ef6c32b9832491edd9'


def decode(raw):
    require(isinstance(raw, bytes) and len(raw) >= 16 and raw[:4] == b'SFDP', 'missing SFDP signature/header')
    require(raw[5] == 1 and raw[4] == 5 and raw[7] == 0xff, 'qualified SFDP 1.5 protocol required')
    end = 8+8*(raw[6]+1)
    require(end <= len(raw), 'additional parameter headers required')
    headers = [raw[i:i+8] for i in range(8, end, 8)]
    bfpts = [h for h in headers if (h[7]<<8)|h[0] == 0xff00]
    require(len(bfpts) == 1, 'unique BFPT required')
    h = bfpts[0]
    require(h[1:3] == b'\x05\x01' and h[3] >= 16, 'qualified BFPT revision/length required')
    pointer, size = int.from_bytes(h[4:7], 'little'), h[3]*4
    require(pointer % 4 == 0 and pointer >= end and pointer+size <= len(raw), 'additional/aligned BFPT bytes required')
    words = struct.unpack_from('<16I', raw, pointer)
    require(words[1] == 0x07ffffff and (words[0] >> 17) & 3 == 0, '16 MiB/three-byte-only geometry required')
    require(words[0] & 3 == 1 and (words[0] >> 8) & 255 == 0x20, 'uniform 4 KiB 20h erase required')
    page = 1 << ((words[10] >> 4) & 15)
    require(page == 256, '256-byte page required')
    erases = []
    for index in range(4):
        pair = (words[7+index//2] >> (16*(index % 2))) & 0xffff
        exponent, opcode = pair & 255, pair >> 8
        if exponent == 0: continue
        require(8 <= exponent <= 24 and opcode not in (0, 255), 'invalid erase geometry')
        bits = (words[9] >> (4+7*index)) & 127
        typical = ((bits & 31)+1)*(1, 16, 128, 1000)[bits >> 5]
        maximum = typical*2*((words[9] & 15)+1)
        erases.append(dict(bytes=1<<exponent, opcode=opcode, typical_ms=typical, maximum_ms=maximum))
    require(erases[0]['bytes'] == 4096 and erases[0]['opcode'] == 0x20, 'first erase type must be 4 KiB/20h')
    pp_typical = (((words[10] >> 8) & 31)+1)*(64 if words[10] & (1<<13) else 8)
    pp_maximum = pp_typical*2*((words[10] & 15)+1)
    return dict(sfdp_revision='1.5', bfpt_pointer=pointer, bfpt_dwords=h[3], density_bytes=0x1000000,
                address_bytes=3, page_bytes=page, erases=erases,
                page_program_typical_us=pp_typical, page_program_maximum_us=pp_maximum,
                qer=(words[14] >> 20) & 7, suffix_proven=False, protection_proven=False,
                qer_used_for_configuration=False, status_write_allowed=False)


def pinned(raw):
    value = decode(raw)
    require(hashlib.sha256(raw).hexdigest() == SFDP_SHA, 'physical SFDP profile changed')
    require(value['erases'][0]['maximum_ms'] == 896 and value['page_program_maximum_us'] == 4224,
            'pinned timing mismatch')
    value['qer_discrepancy'] = 'QER4 conventional no-35h-read conflicts with observed 35h=02; preserve QE/status'
    value['authorized_opcodes'] = [3, 5, 6, 2, 0x20]
    value['device_write_admitted'] = False
    return value
