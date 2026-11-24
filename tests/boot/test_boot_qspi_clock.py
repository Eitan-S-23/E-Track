#!/usr/bin/env python3
"""Compile the actual Boot QSPI entry points against a recording host HAL."""
from pathlib import Path
import re
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "boot/platform/at32/boot_platform_at32.c"

HAL = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "failed line %d\n", __LINE__); exit(1); } } while (0)
typedef struct { int gpio_drive_strength, gpio_out_type, gpio_mode, gpio_pull, gpio_pins; } gpio_init_type;
#define crm_periph_clock_enable(...) ((void)0)
#define gpio_pin_mux_config(...) ((void)0)
#define gpio_init(port, p) ((void)(p))
#define gpio_default_para_init(p) memset((p), 0, sizeof(*(p)))
#define qspi_sck_mode_set(...) ((void)0)
#define qspi_busy_config(...) ((void)0)
#define qspi_auto_ispc_enable(...) ((void)0)
#define boot_platform_delay_ms(...) ((void)0)
enum { QSPI1, GPIO_DRIVE_STRENGTH_STRONGER, GPIO_OUTPUT_PUSH_PULL, GPIO_MODE_MUX,
       GPIO_PULL_NONE, GPIO_PINS_9, GPIO_PINS_10, GPIO_PINS_8, GPIO_PINS_3,
       GPIO_PINS_1, GPIO_PINS_11, FALSE, QSPI_CMD_ADRLEN_0_BYTE,
       QSPI_CMD_ADRLEN_3_BYTE };
#define QSPI_CLK_DIV_2 0
#define QSPI_CLK_DIV_8 3
#define OTA_EXT_WINDOW_LENGTH 0x800000u
static int divider, commands, reads, fail_command, fail_read;
static uint32_t jedec;
static void qspi_xip_enable(int port, int value) { (void)port; CHECK(value == FALSE); }
static void qspi_clk_division_set(int port, int value) { (void)port; divider = value; }
static int qspi_send(unsigned opcode) {
    CHECK(divider == QSPI_CLK_DIV_8);
    CHECK(opcode == (commands == 0 ? 0x66u : 0x99u));
    ++commands;
    return commands == fail_command ? -1 : 0;
}
static int qspi_read_command(unsigned opcode, uint32_t address, int address_len,
                             uint8_t *dst, size_t length) {
    CHECK(divider == QSPI_CLK_DIV_8);
    ++reads;
    if (reads == fail_read) return -1;
    if (opcode == 0x9fu) {
        CHECK(address == 0 && address_len == QSPI_CMD_ADRLEN_0_BYTE && length == 3);
        dst[0] = (uint8_t)(jedec >> 16); dst[1] = (uint8_t)(jedec >> 8); dst[2] = (uint8_t)jedec;
    } else {
        CHECK(opcode == 0x03u && address_len == QSPI_CMD_ADRLEN_3_BYTE);
        CHECK(length <= BOOT_QSPI_READ_CHUNK);
        for (size_t i = 0; i < length; ++i) dst[i] = (uint8_t)(address + i);
    }
    return 0;
}
"""

CASES = r"""
static void reset(uint32_t id) {
    divider = -1; commands = 0; reads = 0; fail_command = 0; fail_read = 0; jedec = id;
}
int main(void) {
    const uint32_t ids[] = {0xef4018u, 0xef4017u, 0x1c4018u, 0x1c4017u};
    uint8_t data[101];
    for (size_t i = 0; i < sizeof(ids)/sizeof(ids[0]); ++i) {
        reset(ids[i]); CHECK(boot_platform_qspi_init() == 0);
        CHECK(divider == 3 && commands == 2 && reads == 1);
    }
    reset(0); CHECK(boot_platform_qspi_init() == -1);
    for (int i = 1; i <= 2; ++i) {
        reset(ids[0]); fail_command = i; CHECK(boot_platform_qspi_init() == -1);
        CHECK(commands == i && reads == 0);
    }
    reset(ids[0]); fail_read = 1; CHECK(boot_platform_qspi_init() == -1);
    reset(ids[0]); CHECK(boot_platform_qspi_init() == 0); reads = 0;
    CHECK(boot_platform_qspi_read(17, data, sizeof(data)) == 0);
    CHECK(reads == (int)((sizeof(data) + BOOT_QSPI_READ_CHUNK - 1) / BOOT_QSPI_READ_CHUNK));
    for (size_t i = 0; i < sizeof(data); ++i) CHECK(data[i] == (uint8_t)(17 + i));
    reads = 0; CHECK(boot_platform_qspi_read(OTA_EXT_WINDOW_LENGTH, NULL, 0) == 0 && reads == 0);
    CHECK(boot_platform_qspi_read(0, NULL, 1) == -1 && reads == 0);
    CHECK(boot_platform_qspi_read(OTA_EXT_WINDOW_LENGTH, data, 1) == -1 && reads == 0);
    CHECK(boot_platform_qspi_read(OTA_EXT_WINDOW_LENGTH + 1, data, 0) == -1 && reads == 0);
    fail_read = 2; CHECK(boot_platform_qspi_read(17, data, sizeof(data)) == -1 && reads == 2);
    puts("BOOT_QSPI_CLOCK=PASS cases=14");
    return 0;
}
"""


def compile_test(output: Path, *, old_divider=False) -> None:
    checked = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))["checked_output"]
    output = checked(ROOT, output)
    fixture = checked(ROOT, output.with_suffix(".c"))
    source = SOURCE.read_text(encoding="utf-8")
    chunk = re.search(r"^\s*BOOT_QSPI_READ_CHUNK\s*=\s*([0-9]+),", source, re.M)
    if chunk is None:
        raise RuntimeError("Boot read chunk definition missing")
    functions = []
    for name in ("qspi_jedec_allowed", "boot_platform_qspi_init", "boot_platform_qspi_read"):
        match = re.search(r"^(?:static )?int " + name + r"\([^)]*\)\s*\n\{.*?^\}", source, re.M | re.S)
        if match is None:
            raise RuntimeError("Boot QSPI entry point missing: " + name)
        functions.append(match.group())
    body = "\n".join(functions)
    if old_divider:
        if body.count("qspi_clk_division_set(QSPI1, QSPI_CLK_DIV_8);") != 1:
            raise RuntimeError("negative clock mutation no longer applies")
        body = body.replace("qspi_clk_division_set(QSPI1, QSPI_CLK_DIV_8);",
                            "qspi_clk_division_set(QSPI1, QSPI_CLK_DIV_2);", 1)
    fixture.parent.mkdir(parents=True, exist_ok=True)
    with fixture.open("x", encoding="ascii") as stream:
        stream.write("#define BOOT_QSPI_READ_CHUNK " + chunk.group(1) + "\n" + HAL + "\n" + body + "\n" + CASES)
    subprocess.run([r"D:\install\mingw64\bin\gcc.exe", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(fixture), "-o", str(output)], cwd=ROOT, check=True, timeout=60)
