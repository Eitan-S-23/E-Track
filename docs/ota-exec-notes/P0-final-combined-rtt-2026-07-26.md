# P0-4/P0-5 combined RTT regression (2026-07-26)

This is implementation-session regression evidence. It does not replace the
independent acceptance required by `PLAN-OTA-EXEC.md` section 0.3.

## Build And Probe Context

- Build switches: `CONFIG_EEPROM_BCB_STRESS=1`, `CONFIG_QSPI_SELFTEST_ENABLE=1`.
- AC5 result: `Code=267084 RO-data=288316 RW-data=1248 ZI-data=462604`, zero errors and zero warnings.
- Probe: `AT32F435RGT7`, SWD 1000 kHz, SW-DP `0x2BA01477`.
- RTT control block: `_SEGGER_RTT=0x2004cf68`; `mem8` signature was `SEGGER RTT`.
- Runtime state: `mem8 0x20005a6c 8 = 00 00 00 00 18 40 EF 00`, meaning OTA enabled and JEDEC `0xEF4018`.

## Logger Output

```text
Reset: NRST SW
BCBSTRESS: start 1000 iters
BCBSTRESS: done ok=1000 fail=0 / 1000
QSPISELF: inject timeout rc=1 (PASS)
QSPISELF: start 1000 iters @0x7F0000 (reserved)
QSPISELF: done ok=1000 fail=0 / 1000
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
```

After capture, both test switches were restored to `0`. The default firmware
was rebuilt and flashed with `Code=263496 RO-data=288312 RW-data=1244
ZI-data=453392`; flash verify passed and no `JLinkRTTLogger` process remained.
