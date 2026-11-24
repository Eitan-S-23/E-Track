#!/usr/bin/env python3
"""Run actual QSPI restore and installation HAL functions in a command model.

No flash, MCU, USB, or network access. This is not a NOR electrical/timing model
or a replacement for the existing decoder/backup/rollback tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
IO = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
CXX = Path("D:/install/mingw64/bin/g++.exe")
DRIVER = ROOT / "Libraries/W25Q128/qspi_cmd_en25qh128a.cpp"
HEADER = ROOT / "Libraries/W25Q128/qspi_cmd_en25qh128a.h"
HAL = ROOT / "USER/HAL/HAL_OTA_Package.cpp"
VENDOR = ROOT / "vendor/AT32F435_437_DFP/Peripherals/inc/at32f435_437_qspi.h"
OUT: Path
ENV: dict[str, str]
COMMANDS: list[dict] = []
NATIVE: list[dict] = []

PREAMBLE = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "HAL/HAL_OTA_Package.h"
#include "HAL/HAL_OTA_Backup.h"
#include "OTA/ota_staging.h"
#include "OTA/ota_erase_plan.h"
static unsigned long long checks;
static unsigned scenarios;
#define CHECK(x) do { ++checks; if (!(x)) { \
    fprintf(stderr, "MODEL_CHECK_FAILED line=%d: %s\n", __LINE__, #x); exit(7); \
} } while (0)
typedef enum { FALSE = 0, TRUE = 1 } confirm_state;
enum { QSPI1 = 1, RESET = 0, SET = 1, QSPI_CMDSTS_FLAG = 1,
       QSPI_TXFIFORDY_FLAG = 2, QSPI_RXFIFORDY_FLAG = 3 };
#define CoreDebug_DEMCR_TRCENA_Msk (1u << 24)
#define DWT_CTRL_CYCCNTENA_Msk 1u
struct Dwt { uint32_t CTRL, CYCCNT; };
struct Core { uint32_t DEMCR; };
static Dwt dwt;
static Core core;
#define DWT (&dwt)
#define CoreDebug (&core)
static uint32_t SystemCoreClock = 288000000u;
"""

MODEL = r"""
struct Model {
    uint8_t sr1, sr2;
    uint32_t ticks, id;
    qspi_cmd_type command;
    unsigned commands, reads, writes, xip_inits, delays, watchdogs;
    unsigned fail_command, fail_fifo, bytes_written, bytes_read;
    unsigned erases, erase64s, erase_fail_on, programs, library_calls;
    bool xip, completed, delayed, disabled, fail_erase, fail_program;
    int library_result;
};
static Model m;
static uint32_t erase_addresses[256], erase_sizes[256];
static uint32_t millis(void) {
    DWT->CYCCNT += 288000u;
    return m.ticks++;
}
static void delay_us(unsigned us) {
    CHECK(us == 100u);
    CHECK(m.completed && m.command.instruction_code == 0x99u);
    m.delayed = true;
    ++m.delays;
    DWT->CYCCNT += 28800u;
}
static void qspi_xip_enable(int port, confirm_state enabled) {
    CHECK(port == QSPI1);
    m.xip = enabled != FALSE;
}
static void qspi_cmd_operation_kick(int port, qspi_cmd_type *cmd) {
    CHECK(port == QSPI1 && !m.xip && cmd != NULL);
    CHECK(cmd->pe_mode_enable == FALSE && cmd->pe_mode_operate_code == 0);
    CHECK(cmd->instruction_length == QSPI_CMD_INSLEN_1_BYTE);
    CHECK(cmd->address_length == QSPI_CMD_ADRLEN_0_BYTE && cmd->address_code == 0);
    CHECK(cmd->operation_mode == QSPI_OPERATE_MODE_111);
    CHECK(cmd->second_dummy_cycle_num == 0);
    CHECK(cmd->read_status_config == QSPI_RSTSC_HW_AUTO);
    m.command = *cmd;
    ++m.commands;
    m.completed = false;
    m.bytes_written = m.bytes_read = 0;
    switch (cmd->instruction_code) {
    case 0x66: case 0x99:
        CHECK(cmd->data_counter == 0 && cmd->write_data_enable == TRUE);
        CHECK(cmd->read_status_enable == FALSE);
        m.delayed = false;
        break;
    case 0x06:
        CHECK(cmd->data_counter == 0 && cmd->write_data_enable == TRUE);
        CHECK(cmd->read_status_enable == FALSE);
        break;
    case 0x01:
        CHECK(cmd->data_counter == 2 && cmd->write_data_enable == TRUE);
        CHECK(cmd->read_status_enable == FALSE);
        ++m.writes;
        break;
    case 0x05: case 0x35:
        CHECK(cmd->write_data_enable == FALSE);
        if (cmd->read_status_enable) {
            CHECK(cmd->instruction_code == 0x05 && cmd->data_counter == 0);
        } else {
            CHECK(m.delayed && cmd->data_counter == 1);
            ++m.reads;
        }
        break;
    default:
        CHECK(false);
    }
}
static int qspi_flag_get(int port, uint32_t flag) {
    CHECK(port == QSPI1);
    if (flag == QSPI_RXFIFORDY_FLAG) return RESET;
    if (flag == QSPI_TXFIFORDY_FLAG) {
        CHECK(m.command.instruction_code == 0x01 && m.bytes_written < 2);
        return m.fail_fifo == m.bytes_written + 1 ? RESET : SET;
    }
    CHECK(flag == QSPI_CMDSTS_FLAG);
    if (m.command.instruction_code == 0x01) CHECK(m.bytes_written == 2);
    return m.fail_command == m.commands ? RESET : SET;
}
static void qspi_flag_clear(int port, uint32_t flag) {
    CHECK(port == QSPI1 && flag == QSPI_CMDSTS_FLAG);
    CHECK(m.fail_command != m.commands);
    m.completed = true;
    if (m.command.instruction_code == 0x01) {
        CHECK(m.bytes_written == 2);
        m.sr1 = 0;
        m.sr2 = 2;
    }
}
static void qspi_byte_write(int port, uint8_t value) {
    CHECK(port == QSPI1 && m.command.instruction_code == 0x01);
    CHECK(value == (m.bytes_written == 0 ? 0 : 2));
    ++m.bytes_written;
}
static uint8_t qspi_byte_read(int port) {
    CHECK(port == QSPI1 && m.completed && !m.xip);
    CHECK(m.command.read_status_enable == FALSE && m.command.data_counter == 1);
    CHECK(m.bytes_read++ == 0);
    return m.command.instruction_code == 0x05 ? m.sr1 : m.sr2;
}
static void qspi_xip_init(int port, qspi_xip_type *xip) {
    CHECK(port == QSPI1 && !m.xip);
    CHECK(m.sr1 == 0 && m.sr2 == 2);
    CHECK(xip->read_instruction_code == 0x6b);
    CHECK(xip->read_address_length == QSPI_XIP_ADDRLEN_3_BYTE);
    CHECK(xip->read_operation_mode == QSPI_OPERATE_MODE_114);
    CHECK(xip->read_second_dummy_cycle_num == 8);
    CHECK(xip->write_instruction_code == 0x32);
    CHECK(xip->write_address_length == QSPI_XIP_ADDRLEN_3_BYTE);
    CHECK(xip->write_operation_mode == QSPI_OPERATE_MODE_114);
    CHECK(xip->write_second_dummy_cycle_num == 0);
    CHECK(xip->write_select_mode == QSPI_XIPW_SEL_MODED);
    CHECK(xip->read_select_mode == QSPI_XIPR_SEL_MODET);
    CHECK(xip->write_time_counter == 0x7f && xip->write_data_counter == 0x1f);
    CHECK(xip->read_time_counter == 0x7f && xip->read_data_counter == 0x1f);
    ++m.xip_inits;
}
static void reset_model(unsigned sr1 = 0, unsigned sr2 = 2) {
    memset(&m, 0, sizeof(m));
    m.sr1 = (uint8_t)sr1;
    m.sr2 = (uint8_t)sr2;
    m.id = QSPI_JEDEC_W25Q128;
    m.xip = true;
    DWT->CTRL = DWT_CTRL_CYCCNTENA_Msk;
    DWT->CYCCNT = 0;
    CoreDebug->DEMCR = CoreDebug_DEMCR_TRCENA_Msk;
    SystemCoreClock = 288000000u;
}
namespace HAL {
    uint32_t Qspi_GetJedecId(void) { return m.id; }
    bool Qspi_IsOtaDisabled(void) { return m.disabled; }
    const bcb_hal_t *OTA_GetBcbHal(void) { static bcb_hal_t hal = {}; return &hal; }
}
static void service_app_watchdog(void) { ++m.watchdogs; }
static qspi_status_t qspi_erase(uint32_t address) {
    CHECK(!m.xip && address % OTA_STAGING_BLOCK_SIZE == 0);
    CHECK(m.erases < 256);
    erase_addresses[m.erases] = address;
    erase_sizes[m.erases] = OTA_STAGING_BLOCK_SIZE;
    ++m.erases;
    return m.fail_erase || m.erase_fail_on == m.erases ? QSPI_ERR_TIMEOUT : QSPI_OK;
}
#if CONFIG_OTA_INSTALL_BLOCK_ERASE
static qspi_status_t qspi_erase_64k(uint32_t address) {
    CHECK(!m.xip && address % OTA_ERASE_BLOCK_SIZE == 0 && m.erases < 256);
    erase_addresses[m.erases] = address;
    erase_sizes[m.erases] = OTA_ERASE_BLOCK_SIZE;
    ++m.erases;
    ++m.erase64s;
    return m.fail_erase || m.erase_fail_on == m.erases ? QSPI_ERR_TIMEOUT : QSPI_OK;
}
#endif
static qspi_status_t qspi_data_write(uint32_t address, uint32_t len, uint8_t *src) {
    CHECK(!m.xip && src && len && address < OTA_EXT_STAGING);
    ++m.programs;
    return m.fail_program ? QSPI_ERR_TIMEOUT : QSPI_OK;
}
#if CONFIG_OTA_INSTALL_PROFILE || CONFIG_OTA_INSTALL_COST
static int SEGGER_RTT_printf(unsigned channel, const char *format, ...) {
    CHECK(channel == 0);
    va_list args;
    va_start(args, format);
    int result = vprintf(format, args);
    va_end(args);
    return result;
}
#endif
"""

PORT_STUBS = r"""
static int package_read(void *, uint32_t, uint8_t *, uint32_t) { CHECK(false); return -1; }
static int candidate_read(void *, uint32_t, uint8_t *, uint32_t) { CHECK(false); return -1; }
static int base_read(void *, uint32_t, uint8_t *, uint32_t) { CHECK(false); return -1; }
static int backup_flash_read(void *, uint32_t, uint8_t *, uint32_t) { CHECK(false); return -1; }
static int workspace_acquire(void *, uint8_t **, uint32_t *) { CHECK(false); return -1; }
static void workspace_release(void *, uint8_t *, uint32_t) { CHECK(false); }
"""

LIBRARY_STUBS = r"""
/* Only the surrounding HAL is under test here. Portable engines have their
 * existing real-code tests; these stubs exercise the ports and return codes. */
extern "C" ota_package_result_t ota_package_apply_full(const ota_package_io_t *io,
    const ota_package_device_t *device, uint32_t len, ota_package_info_t *) {
    ++m.library_calls;
    CHECK(device->current_vcode == 30219 && len == 4096);
    CHECK(m.writes == 1 && m.reads == 0);
    CHECK(io->package_read == package_read && io->candidate_read == candidate_read);
    CHECK(io->workspace_acquire == workspace_acquire && io->workspace_release == workspace_release);
    uint8_t src[1024] = {};
    if (io->candidate_prepare(io->ctx, sizeof(src)) != 0) return OTA_PACKAGE_ERR_CANDIDATE_PREPARE;
    if (io->candidate_program(io->ctx, 0, src, sizeof(src)) != 0) return OTA_PACKAGE_ERR_CANDIDATE_WRITE;
    return (ota_package_result_t)m.library_result;
}
extern "C" ota_patch_result_t ota_patch_apply(const ota_patch_io_t *io,
    const ota_patch_device_t *device, uint32_t len, ota_patch_info_t *) {
    ++m.library_calls;
    CHECK(device->current_vcode == 30219 && device->base_image_len == 1024 && len == 4096);
    CHECK(m.writes == 1 && m.reads == 0 && io->base_read == base_read);
    CHECK(io->package_read == package_read && io->candidate_read == candidate_read);
    CHECK(io->workspace_acquire == workspace_acquire && io->workspace_release == workspace_release);
    uint8_t src[1024] = {};
    if (io->candidate_prepare(io->ctx, sizeof(src)) != 0) return OTA_PATCH_ERR_CANDIDATE_PREPARE;
    if (io->candidate_program(io->ctx, 0, src, sizeof(src)) != 0) return OTA_PATCH_ERR_CANDIDATE_WRITE;
    return (ota_patch_result_t)m.library_result;
}
extern "C" ota_backup_result_t ota_backup_stage(const ota_backup_io_t *io,
    const bcb_hal_t *hal, ota_backup_info_t *) {
    ++m.library_calls;
    CHECK(hal != NULL && m.writes == 1 && m.reads == 0);
    CHECK(io->app_read == base_read && io->flash_read == backup_flash_read);
    uint8_t src[1024] = {};
    if (io->flash_erase_4k(io->ctx, OTA_EXT_BACKUP) != 0) return OTA_BACKUP_ERR_ERASE;
    if (io->flash_program(io->ctx, OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE, src, sizeof(src)) != 0)
        return OTA_BACKUP_ERR_WRITE;
    return (ota_backup_result_t)m.library_result;
}
#if CONFIG_OTA_INSTALL_BLOCK_ERASE
extern "C" ota_backup_result_t ota_backup_stage_with_block_erase(const ota_backup_io_t *io,
    const bcb_hal_t *hal, ota_backup_info_t *out, ota_backup_erase_64k_fn erase_64k) {
    CHECK(erase_64k == backup_flash_erase_64k);
    return ota_backup_stage(io, hal, out);
}
#endif
"""

CASES = r"""
static void driver_cases(void) {
    bool reused;
    uint8_t byte = 0xaa;
    reset_model();
    CHECK(qspi_read_status_byte(0x9f, &byte) == QSPI_ERR_PARAM && m.commands == 0 && byte == 0xaa);
    CHECK(qspi_read_status_byte(0x05, NULL) == QSPI_ERR_PARAM && m.commands == 0);
    ++scenarios;

#if TEST_FULL_MATRIX
    /* Every pair, not only QE=0/1: no protection, suspend, or reserved bit may
     * accidentally be accepted by a future mask-only optimization. */
    for (unsigned sr1 = 0; sr1 < 256; ++sr1) {
        for (unsigned sr2 = 0; sr2 < 256; ++sr2) {
            reset_model(sr1, sr2);
            reused = true;
            CHECK(qspi_xip_restore_checked(m.id, &reused) == QSPI_OK);
            bool ready = sr1 == 0 && sr2 == 2;
            CHECK(reused == ready && m.commands == (ready ? 4u : 9u));
            CHECK(m.reads == 2 && m.writes == (ready ? 0u : 1u));
            CHECK(m.xip && m.xip_inits == 1 && m.delays == 1);
        }
    }
#else
    reset_model();
    CHECK(qspi_xip_restore_checked(m.id, &reused) == QSPI_OK && reused);
    reset_model(0x80, 0x02);
    CHECK(qspi_xip_restore_checked(m.id, &reused) == QSPI_OK && !reused);
#endif
    ++scenarios;
    const uint32_t ids[] = { QSPI_JEDEC_W25Q64, QSPI_JEDEC_EN25QH128A,
        QSPI_JEDEC_EN25QH64A, 0, UINT32_MAX };
    for (unsigned i = 0; i < sizeof(ids) / sizeof(ids[0]); ++i) {
        reset_model(); reused = true;
        CHECK(qspi_xip_restore_checked(ids[i], &reused) == QSPI_OK && !reused);
        CHECK(m.commands == 5 && m.reads == 0 && m.writes == 1 && m.delays == 0 && m.xip);
        ++scenarios;
    }
    reset_model();
    CHECK(qspi_xip_restore_checked(m.id, NULL) == QSPI_OK && m.writes == 0 && m.xip);
    ++scenarios;
    for (unsigned fallback = 0; fallback < 2; ++fallback) {
        unsigned commands = fallback ? 9 : 4;
        for (unsigned failure = 1; failure <= commands; ++failure) {
            reset_model(0, fallback ? 0 : 2); reused = true; m.fail_command = failure;
            CHECK(qspi_xip_restore_checked(m.id, &reused) == QSPI_ERR_TIMEOUT);
            CHECK(!reused && !m.xip && m.xip_inits == 0 && m.commands == failure);
            ++scenarios;
        }
    }
    for (unsigned failure = 1; failure <= 2; ++failure) {
        reset_model(0, 0); reused = true; m.fail_fifo = failure;
        CHECK(qspi_xip_restore_checked(m.id, &reused) == QSPI_ERR_TIMEOUT);
        CHECK(!reused && !m.xip && m.commands == 8 && m.bytes_written == failure - 1);
        ++scenarios;
    }
}

static void hal_cases(void) {
    uint8_t sha8[8] = {};
    reset_model();
    CHECK(qspi_restore_xip() == 0 && m.watchdogs == 2);
    CHECK(m.reads == (CONFIG_OTA_INSTALL_QE_REUSE ? 2u : 0u));
    CHECK(m.writes == (CONFIG_OTA_INSTALL_QE_REUSE ? 0u : 1u));
    ++scenarios;
    reset_model();
    CHECK(qspi_restore_xip(false) == 0 && m.reads == 0 && m.writes == 1);
    ++scenarios;
    for (unsigned phase = 0; phase < 3; ++phase) {
        reset_model();
        int result = phase == 0 ? (int)HAL::OTA_PackageApplyStaging(4096, 30219, NULL) :
            phase == 1 ? (int)HAL::OTA_PatchApplyStaging(4096, 30219, 1024, sha8, NULL) :
                         (int)HAL::OTA_BackupStage(NULL);
        CHECK(result == 0 && m.library_calls == 1 && m.programs == 1 && m.xip);
        CHECK(m.writes == (CONFIG_OTA_INSTALL_QE_REUSE ? 1u : 3u));
        CHECK(m.reads == (CONFIG_OTA_INSTALL_QE_REUSE ? 4u : 0u));
#if CONFIG_OTA_INSTALL_PROFILE
        CHECK(s_ota_install_restore.calls == 3 && s_ota_install_restore.failures == 0);
        CHECK(s_ota_install_restore.reused == (CONFIG_OTA_INSTALL_QE_REUSE ? 2u : 0u));
        CHECK(s_ota_install_restore.invalid_cycles == 0 && s_ota_install_restore.legacy_cycles > 0);
#endif
        ++scenarios;
        reset_model(); m.disabled = true;
        result = phase == 0 ? (int)HAL::OTA_PackageApplyStaging(4096, 30219, NULL) :
            phase == 1 ? (int)HAL::OTA_PatchApplyStaging(4096, 30219, 1024, sha8, NULL) :
                         (int)HAL::OTA_BackupStage(NULL);
        CHECK(result == (phase == 2 ? (int)OTA_BACKUP_ERR_DISABLED : (int)OTA_PACKAGE_ERR_READ));
        CHECK(m.commands == 0 && m.library_calls == 0 && m.erases == 0 && m.programs == 0);
        ++scenarios;
        reset_model(); m.fail_command = 1;
        result = phase == 0 ? (int)HAL::OTA_PackageApplyStaging(4096, 30219, NULL) :
            phase == 1 ? (int)HAL::OTA_PatchApplyStaging(4096, 30219, 1024, sha8, NULL) :
                         (int)HAL::OTA_BackupStage(NULL);
        CHECK(result == (phase == 2 ? (int)OTA_BACKUP_ERR_DISABLED : (int)OTA_PACKAGE_ERR_READ));
        CHECK(m.commands == 1 && m.library_calls == 0 && !m.xip);
        ++scenarios;
    }
    reset_model();
    CHECK(HAL::OTA_PatchApplyStaging(4096, 30219, 1024, NULL, NULL) == OTA_PATCH_ERR_ARGUMENT);
    CHECK(m.commands == 0 && m.library_calls == 0);
    ++scenarios;
    reset_model(); m.library_result = OTA_BACKUP_ERR_COMMIT_AMBIGUOUS;
    CHECK(HAL::OTA_BackupStage(NULL) == OTA_BACKUP_ERR_COMMIT_AMBIGUOUS && m.library_calls == 1);
    ++scenarios;
    reset_model(); m.fail_erase = true;
    CHECK(HAL::OTA_PackageApplyStaging(4096, 30219, NULL) == OTA_PACKAGE_ERR_CANDIDATE_PREPARE);
    CHECK(m.xip && m.erases == 1 && m.programs == 0);
    ++scenarios;
    reset_model(); m.fail_program = true;
    CHECK(HAL::OTA_BackupStage(NULL) == OTA_BACKUP_ERR_WRITE && m.xip);
    ++scenarios;
    reset_model(); m.fail_command = 1;
    uint8_t src[1] = {};
    CHECK(candidate_program(&g_ota_package_port, 0, src, 1) == -1);
    CHECK(m.programs == 1 && m.commands == 1 && !m.xip);
    ++scenarios;
    reset_model();
    CHECK(candidate_program(&g_ota_package_port, OTA_APP_LENGTH, src, 1) == -1);
    CHECK(backup_flash_erase_4k(NULL, OTA_EXT_STAGING) == -1);
    CHECK(backup_flash_program(NULL, OTA_EXT_STAGING, src, 1) == -1);
    CHECK(m.commands == 0 && m.erases == 0 && m.programs == 0);
    ++scenarios;
}

#if CONFIG_OTA_INSTALL_PROFILE
static void timing_cases(void) {
    reset_model(); install_profile_begin();
    m.ticks = 3; DWT->CYCCNT = 0x10;
    install_profile_record(0xfffffff0u, 0xfffffffeu, SystemCoreClock, true, true, 0);
    CHECK(s_ota_install_restore.calls == 1 && s_ota_install_restore.reused == 1);
    CHECK(s_ota_install_restore.reuse_cycles == 32 && s_ota_install_restore.ticks_ms == 5);
    CHECK(s_ota_install_restore.invalid_cycles == 0);
    ++scenarios;
    s_ota_install_restore.reuse_cycles = UINT32_MAX - 3u;
    DWT->CYCCNT = 16;
    install_profile_record(0, m.ticks, SystemCoreClock, true, true, 0);
    CHECK(s_ota_install_restore.reuse_cycles == (uint64_t)UINT32_MAX + 13u);
    ++scenarios;
    s_ota_install_restore.legacy_cycles = UINT32_MAX - 3u;
    DWT->CYCCNT = 32;
    install_profile_record(0, m.ticks, SystemCoreClock, true, false, 0);
    CHECK(s_ota_install_restore.legacy_cycles == (uint64_t)UINT32_MAX + 29u);
    ++scenarios;
    for (unsigned fault = 0; fault < 9; ++fault) {
        reset_model(); install_profile_begin(); DWT->CYCCNT = 100;
        uint32_t clock_hz = SystemCoreClock;
        bool enabled = true;
        int result = 0;
        if (fault == 0) enabled = false;
        if (fault == 1) DWT->CTRL = 0;
        if (fault == 2) CoreDebug->DEMCR = 0;
        if (fault == 3) clock_hz = 0;
        if (fault == 4) clock_hz /= 2;
        if (fault == 5) s_ota_install_restore.core_hz /= 2;
        if (fault == 6) DWT->CYCCNT = 0;
        if (fault == 7) result = -1;
        if (fault == 8) m.ticks = QSPI_BUSY_TIMEOUT_MS + 1;
        install_profile_record(0, 0, clock_hz, enabled, false, result);
        CHECK(s_ota_install_restore.calls == 1 && s_ota_install_restore.invalid_cycles == 1);
        CHECK(s_ota_install_restore.legacy_cycles == 0 && s_ota_install_restore.reuse_cycles == 0);
        CHECK(s_ota_install_restore.failures == (fault == 7 ? 1u : 0u));
        ++scenarios;
    }
    install_profile_begin();
    CHECK(s_ota_install_restore.calls == 0 && s_ota_install_restore.invalid_cycles == 0);
    ++scenarios;
}
#endif

#if CONFIG_OTA_INSTALL_BLOCK_ERASE
static void block_erase_cases(void) {
    ota_package_port_context_t port = {};
    reset_model();
    install_cost_begin();
    CHECK(candidate_prepare(&port, 616048) == 0);
    CHECK(m.erases == 32 && m.erase64s == 8 && m.xip);
    CHECK(erase_addresses[0] == OTA_EXT_CANDIDATE && erase_sizes[0] == 4096);
    uint32_t cursor = OTA_EXT_CANDIDATE;
    for (unsigned i = 0; i < m.erases; ++i) {
        CHECK(erase_addresses[i] == cursor);
        CHECK(erase_sizes[i] <= 622592u - (cursor - OTA_EXT_CANDIDATE));
        cursor += erase_sizes[i];
    }
    CHECK(cursor == OTA_EXT_CANDIDATE + 622592u);
#if CONFIG_OTA_INSTALL_COST
    CHECK(s_ota_cost.io[OTA_COST_ERASE].calls == 32);
    CHECK(s_ota_cost.io[OTA_COST_ERASE].bytes == 622592u);
#endif
    install_cost_end("full", 0);
    ++scenarios;

    reset_model();
    m.id = QSPI_JEDEC_W25Q64;
    CHECK(candidate_prepare(&port, 616048) == 0);
    CHECK(m.erases == 152 && m.erase64s == 0 && m.xip);
    ++scenarios;

    reset_model();
    m.erase_fail_on = 17;
    CHECK(candidate_prepare(&port, 616048) == -1);
    CHECK(m.erases == 17 && m.erase64s == 1 && m.xip);
    ++scenarios;

    const uint32_t invalid[] = {OTA_EXT_CANDIDATE, OTA_EXT_BACKUP,
        OTA_EXT_BACKUP + 4096, OTA_EXT_RECOVERY, OTA_EXT_STAGING};
    for (unsigned i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
        reset_model();
        CHECK(backup_flash_erase_64k(NULL, invalid[i]) == -1);
        CHECK(m.erases == 0 && m.commands == 0 && m.xip);
        ++scenarios;
    }
    reset_model();
    CHECK(backup_flash_erase_64k(NULL, OTA_EXT_BACKUP + 65536) == 0);
    CHECK(m.erases == 1 && m.erase64s == 1 && m.xip);
    ++scenarios;
    reset_model();
    m.id = QSPI_JEDEC_EN25QH128A;
    CHECK(backup_flash_erase_64k(NULL, OTA_EXT_BACKUP + 65536) == -1 && m.erases == 0);
    ++scenarios;
    reset_model();
    m.fail_erase = true;
    CHECK(backup_flash_erase_64k(NULL, OTA_EXT_BACKUP + 65536) == -1 && m.xip);
    ++scenarios;
    reset_model();
    m.fail_command = 1;
    CHECK(candidate_prepare(&port, 616048) == -1);
    CHECK(m.erases == 32 && m.programs == 0 && !m.xip);
    ++scenarios;
    reset_model();
    m.fail_command = 1;
    CHECK(backup_flash_erase_64k(NULL, OTA_EXT_BACKUP + 65536) == -1);
    CHECK(m.erases == 1 && m.programs == 0 && !m.xip);
    ++scenarios;
}
#endif

int main(void) {
    driver_cases();
    hal_cases();
#if CONFIG_OTA_INSTALL_BLOCK_ERASE
    block_erase_cases();
#endif
#if CONFIG_OTA_INSTALL_PROFILE
    timing_cases();
#endif
    printf("QSPI_INSTALL_RESTORE=PASS scenarios=%u checks=%llu matrix=%u opt=%u profile=%u\n",
        scenarios, checks, TEST_FULL_MATRIX ? 65536u : 2u,
        (unsigned)CONFIG_OTA_INSTALL_QE_REUSE, (unsigned)CONFIG_OTA_INSTALL_PROFILE);
    return 0;
}
"""


def require(value, message):
    if not value:
        raise RuntimeError(message)


def checked(path):
    return IO["checked_output"](ROOT, path)


def record(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def extract(text, pattern):
    matches = re.findall(pattern, text, re.M | re.S)
    require(len(matches) == 1, "expected one source region: " + pattern)
    return matches[0]


def function(text, name):
    return extract(text, r"^(?:static )?[\w:]+ " + re.escape(name) +
                   r"\([^;]*?\)\s*\n\{.*?^\}")


def fixture():
    driver, hal = DRIVER.read_text(encoding="utf-8"), HAL.read_text(encoding="utf-8")
    header, vendor = HEADER.read_text(encoding="utf-8"), VENDOR.read_text(encoding="utf-8")
    enums = re.findall(r"^typedef enum\n\{.*?^\} qspi_\w+;", vendor, re.M | re.S)
    require(bool(enums), "vendor enum declarations missing")
    declarations = "\n".join(enums)
    for name in ("qspi_cmd_type", "qspi_xip_type"):
        declarations += "\n" + extract(vendor, r"^typedef struct\n\{(?:(?!^\} ).)*?^\} " + name + ";")
    declarations += "\n" + extract(header, r"^typedef enum\n\{.*?^\} qspi_status_t;")
    declarations += "\n" + "\n".join(re.findall(r"^#define QSPI_(?:\w+_TIMEOUT_MS|JEDEC_\w+)\s+[^\n]+",
                                               header, re.M))
    defaults = extract(hal, r"^#ifndef CONFIG_OTA_INSTALL_QE_REUSE\n.*?^#endif\n"
                            r"#ifndef CONFIG_OTA_INSTALL_PROFILE\n.*?^#endif")
    defaults += "\n" + extract(hal, r"^#ifndef CONFIG_OTA_INSTALL_BLOCK_ERASE\n.*?^#endif")
    constants = "\n".join(extract(driver, r"^static const qspi_\w+ " + name + r" = \{.*?};")
        for name in ("en25qh128a_wren_para", "en25qh128a_rdsr_para", "w25q128_wrsr_para",
                     "en25qh128a_rsten_para", "en25qh128a_rst_para", "qspi_rdid_para",
                     "en25qh128a_xip_init_para"))
    functions = "\n".join(function(driver, name) for name in (
        "qspi_wait_flag", "qspi_cmd_send_ex", "qspi_cmd_send", "qspi_write_enable",
        "qspi_busy_check", "qspi_set_qe_bit", "qspi_flash_reset",
        "en25qh128a_qspi_xip_init", "qspi_read_status_byte", "qspi_xip_restore_checked"))
    profile = extract(hal, r'^#if CONFIG_OTA_INSTALL_PROFILE\n#include "SEGGER_RTT.h"\n.*?^#endif')
    profile = profile.replace('#include "SEGGER_RTT.h"\n', "")
    cost = extract(hal, r'^#ifndef CONFIG_OTA_INSTALL_COST\n.*?^#endif\n\n'
                        r'#if CONFIG_OTA_INSTALL_COST\n.*?^#endif')
    cost = cost.replace('#include "SEGGER_RTT.h"\n', "")
    context = extract(hal, r"^typedef struct ota_package_port_context_t\n\{.*?^\} ota_package_port_context_t;")
    context += "\nstatic ota_package_port_context_t g_ota_package_port;\n"
    ports = "\n".join(function(hal, name) for name in (
        "qspi_restore_xip", "candidate_range_ok", "backup_slot_range_ok",
        "install_block_erase_enabled", "candidate_prepare", "candidate_program",
        "backup_flash_erase_4k", "backup_flash_program"))
    ports += "\n#if CONFIG_OTA_INSTALL_BLOCK_ERASE\n" + function(hal, "backup_flash_erase_64k") + "\n#endif\n"
    entries = "\n".join(function(hal, name) for name in (
        "HAL::OTA_BackupStage", "HAL::OTA_PackageApplyStaging", "HAL::OTA_PatchApplyStaging"))
    return "\n".join((PREAMBLE, declarations, defaults, MODEL, constants, functions,
                      profile, cost, context, PORT_STUBS, ports, entries, LIBRARY_STUBS, CASES))


def reserve(directory):
    directory = checked(directory)
    require(not directory.exists(), "preserve existing output: " + str(directory))
    return directory


def run(tag, args, cwd):
    paths = [checked(OUT / (tag + suffix)) for suffix in (".stdout", ".stderr", ".json")]
    require(not any(path.exists() for path in paths), "preserve command evidence")
    started = time.monotonic()
    timeout = None
    try:
        result = subprocess.run(list(map(str, args)), cwd=checked(cwd), env=ENV,
            capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, code = error.stdout or b"", error.stderr or b"", None
        timeout = 60
    for path, raw in zip(paths, (stdout, stderr)):
        with path.open("xb") as stream:
            stream.write(raw)
    value = dict(args=list(map(str, args)), cwd=str(cwd), exit=code, timeout=timeout,
                 seconds=time.monotonic() - started, stdout=record(paths[0]), stderr=record(paths[1]))
    IO["write_json"](ROOT, paths[2], value)
    COMMANDS.append(record(paths[2]))
    require(timeout is None, "command timed out: " + tag)
    return code, stdout, stderr


def compile_run(tag, *, optimize=None, profile=None, cost=None, block_erase=None, mutation=None, full_matrix=False):
    body = fixture()
    if mutation is not None:
        old, new = mutation
        require(body.count(old) == 1, "negative mutation is no longer unique")
        body = body.replace(old, new, 1)
    source = checked(OUT / (tag + ".cpp"))
    exe = checked(OUT / ("qspi-" + tag + ".exe"))
    require(not source.exists() and not exe.exists(), "preserve native fixture")
    with source.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(body)
    args = [CXX, "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-DTEST_FULL_MATRIX=" + str(int(full_matrix)), "-I" + str(ROOT / "USER"),
            "-I" + str(ROOT / "Libraries"), source, "-o", exe]
    for name, value in (("CONFIG_OTA_INSTALL_QE_REUSE", optimize), ("CONFIG_OTA_INSTALL_PROFILE", profile),
                        ("CONFIG_OTA_INSTALL_COST", cost), ("CONFIG_OTA_INSTALL_BLOCK_ERASE", block_erase)):
        if value is not None:
            args.insert(1, "-D" + name + "=" + str(value))
    code, stdout, stderr = run(tag + "-compile", args, OUT)
    require(code == 0, "native compile failed: " + tag + "\n" + stderr.decode("utf-8", "replace")[-6000:])
    require(not re.search(rb"\bwarning:", stdout + stderr), "native compile warning: " + tag)
    code, stdout, stderr = run(tag + "-run", [exe], OUT)
    if mutation is not None:
        require(code == 7 and b"MODEL_CHECK_FAILED" in stderr, "mutation did not fail its runtime oracle")
    else:
        require(code == 0, "native model failed: " + tag + "\n" + stderr.decode("utf-8", "replace")[-6000:])
        found = re.findall(rb"QSPI_INSTALL_RESTORE=PASS scenarios=(\d+) checks=(\d+) matrix=(\d+) opt=(\d+) profile=(\d+)",
                           stdout)
        require(len(found) == 1, "native PASS counts absent")
        counts = list(map(int, found[0]))
        require(counts[0] > 0 and counts[1] > 0, "empty native checks")
        NATIVE.append(dict(tag=tag, scenarios=counts[0], checks=counts[1], status_pairs=counts[2],
                           optimize=counts[3], profile=counts[4], fixture=record(source), executable=record(exe)))
        require(counts[3] == (optimize or 0) and counts[4] == (profile or 0), "feature default differs")
        require((b"P34INSTALL:" in stdout) == bool(profile), "diagnostics not compile-time gated")
        require((b"P34COST:" in stdout) == bool(cost), "cost diagnostics not compile-time gated")
        if cost:
            rows = re.findall(rb"P34COST: phase=(full|patch|backup) rc=(-?\d+) clock=millis total=(\d+) rest=(\d+) valid=(\d+)", stdout)
            require(len(rows) >= 10 and all(int(row[4]) == 1 for row in rows), "cost intervals fail to partition")


class RestoreTests(unittest.TestCase):
    def test_block_erase_ports(self):
        compile_run("block-erase", optimize=1, block_erase=1)

    def test_block_erase_cost_accounting(self):
        compile_run("block-cost", optimize=1, block_erase=1, cost=1)

    def test_block_erase_cannot_merge_header(self):
        compile_run("mutant-block-header", optimize=1, block_erase=1,
                    mutation=("offset != 0u && block_erase", "block_erase"))

    def test_block_erase_backup_header_guard(self):
        compile_run("mutant-backup-header", optimize=1, block_erase=1,
                    mutation=("address < OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE ||", "false ||"))

    def test_default_off_and_all_status_pairs(self):
        compile_run("default", full_matrix=True)

    def test_opt_in_without_profile(self):
        compile_run("checked", optimize=1)

    def test_legacy_profile(self):
        compile_run("legacy-profile", profile=1)

    def test_checked_profile(self):
        compile_run("checked-profile", optimize=1, profile=1)

    def test_cost_profile_without_cycle_profile(self):
        compile_run("cost-only", optimize=1, cost=1)

    def test_cost_with_cycle_profile(self):
        compile_run("cost-and-cycle", optimize=1, profile=1, cost=1)

    def test_qe_bit_only_mutant_fails(self):
        compile_run("mutant-qe-only", mutation=(
            "if(sr1 != 0x00u || sr2 != 0x02u)", "if((sr2 & 0x02u) == 0u)"))

    def test_rx_ready_mutant_fails(self):
        compile_run("mutant-rx-ready", mutation=(
            "/* A one-byte read cannot reach RXFIFORDY's FIFO threshold. */\n"
            "  st = qspi_wait_flag(QSPI_CMDSTS_FLAG, QSPI_CMD_TIMEOUT_MS);",
            "st = qspi_wait_flag(QSPI_RXFIFORDY_FLAG, QSPI_CMD_TIMEOUT_MS);"))

    def test_missing_reset_delay_mutant_fails(self):
        # Keep the model delay function referenced, but violate its safe duration.
        compile_run("mutant-reset-delay", mutation=("delay_us(100);", "delay_us(0);"))

    def test_read_error_fallback_mutant_fails(self):
        compile_run("mutant-read-fallback", mutation=(
            "st = qspi_read_status_byte(0x05u, &sr1);\n  if(st != QSPI_OK)\n    return st;",
            "st = qspi_read_status_byte(0x05u, &sr1);\n  if(st != QSPI_OK)\n"
            "    return en25qh128a_qspi_xip_init();"))

    def test_sibling_output_rejected_before_creation(self):
        sibling = ROOT.parent / (ROOT.name + "-n04-not-authorized") / "host"
        with self.assertRaises(IO["OutputBoundaryError"]):
            reserve(sibling)

    def test_existing_output_preserved(self):
        before = record(OUT / "intent.json")
        with self.assertRaisesRegex(RuntimeError, "preserve existing output"):
            reserve(OUT)
        self.assertEqual(before, record(OUT / "intent.json"))


def main():
    global OUT, ENV
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    require(Path(args.root) == ROOT and Path.cwd() == ROOT and sys.flags.isolated and
            sys.flags.no_site and sys.dont_write_bytecode, "explicit isolated authorized project root required")
    OUT = reserve(args.out)
    inputs = [DRIVER, HEADER, HAL, VENDOR, Path(__file__), ROOT / "USER/HAL/ota_install_cost.h",
              ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"]
    inputs += [ROOT / path for path in ("USER/HAL/HAL_OTA_Package.h", "USER/HAL/HAL_OTA_Backup.h",
        "Libraries/OTA/ota_package.h", "Libraries/OTA/ota_patch.h", "Libraries/OTA/ota_backup.h",
        "Libraries/OTA/ota_staging.h", "Libraries/OTA/ota_layout.h", "Libraries/EEPROM/eeprom_bcb.h")]
    inputs.append(ROOT / "Libraries/OTA/ota_erase_plan.h")
    before = [record(path) for path in inputs]
    environment_paths = {name: checked(OUT / "host" / folder) for name, folder in {
        "HOME": "home", "USERPROFILE": "home", "APPDATA": "appdata", "LOCALAPPDATA": "localappdata",
        "TEMP": "tmp", "TMP": "tmp", "TMPDIR": "tmp", "XDG_CACHE_HOME": "cache",
        "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data", "XDG_STATE_HOME": "state",
        "PYTHONUSERBASE": "python", "PYTHONPYCACHEPREFIX": "pycache"}.items()}
    for name in ("intent.json", "result.json", "unittest.log"):
        checked(OUT / name)
    require(CXX.is_file(), "host C++ compiler missing")
    OUT.mkdir(parents=True)
    ENV = dict(os.environ)
    for name, path in environment_paths.items():
        path.mkdir(parents=True, exist_ok=True)
        ENV[name] = str(path)
    ENV.update(PYTHONDONTWRITEBYTECODE="1", CCACHE_DISABLE="1", SCCACHE_DISABLE="1",
               SOURCE_DATE_EPOCH="1786320000")
    IO["write_json"](ROOT, OUT / "intent.json", dict(inputs=before, compiler=record(CXX),
        environment={name: str(path) for name, path in environment_paths.items()},
        hardware=False, independent_acceptance=False))
    with (OUT / "unittest.log").open("x", encoding="utf-8", newline="\n") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(RestoreTests))
    unchanged = before == [record(path) for path in inputs]
    value = dict(result="HOST_MODEL_PASS" if result.wasSuccessful() and unchanged else "HOST_MODEL_FAIL",
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), inputs_unchanged=unchanged, inputs=before, native=NATIVE,
        commands=COMMANDS, log=record(OUT / "unittest.log"), hardware=False,
        independent_acceptance=False, physical_timing=False)
    IO["write_json"](ROOT, OUT / "result.json", value)
    print(json.dumps({key: value[key] for key in ("result", "tests", "failures", "errors", "skipped")}),
          str(OUT / "result.json"))
    if not result.wasSuccessful() or not unchanged:
        print((OUT / "unittest.log").read_text(encoding="utf-8")[-12000:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
