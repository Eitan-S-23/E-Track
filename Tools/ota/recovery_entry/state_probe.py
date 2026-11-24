"""Fixed passive recovery-prerequisite observations, not ownership qualification."""
import struct
import zlib

from .probe import require

REGISTERS = {
    "crm_ctrl": 0x40023800, "crm_pllcfg": 0x40023804, "crm_cfg": 0x40023808,
    "crm_ahben1": 0x40023830, "crm_ctrlsts": 0x40023874,
    "crm_misc1": 0x400238a0, "crm_misc2": 0x400238a4,
    "debug_ctrl": 0xe0042004, "debug_apb1_frz": 0xe0042008, "debug_apb2_frz": 0xe004200c,
    "wdt_div": 0x40003004, "wdt_rld": 0x40003008, "wdt_sts": 0x4000300c, "wdt_win": 0x40003010,
    "qspi_ctrl": 0xa0001010, "qspi_fifo": 0xa0001018, "qspi_ctrl2": 0xa0001020,
    "qspi_cmdsts": 0xa0001024, "sdio_dtctrl": 0x4002c42c, "sdio_sts": 0x4002c434,
    "flash_usd": 0x40023c1c, "usd_fap_ssb": 0x1fffc000, "usd_eopb0": 0x1fffc010,
    "ble_state_word": 0x20052a54, "ble_isr_word": 0x20052b34, "ble_epoch": 0x20052bc8,
    "overlay_owner_word": 0x20053acc, "confirm_mirror_word": 0x20053a98,
    "display_dma_count": 0x40026434, "display_dma_peripheral": 0x40026438,
    "display_dma_memory": 0x4002643c, "sd_dma_count": 0x40026648,
    "sd_dma_peripheral": 0x4002664c, "sd_dma_memory": 0x40026650,
    "fp_ctrl": 0xe0002000,
    "sdio2_cmd": 0x5006100c, "sdio2_rspcmd": 0x50061010, "sdio2_rsp1": 0x50061014,
    "sdio2_dtctrl": 0x5006102c, "sdio2_dtcnt": 0x50061030, "sdio2_sts": 0x50061034,
    "sd_ready_mirror": 0x20052ddc, "gpioc_input": 0x40020810,
    "sd_error_word": 0x200041fc,
    "recorder_file": 0x20051c78, "recorder_driver": 0x20051c7c,
    "recorder_cache": 0x20051c80, "recorder_active_word": 0x20051c84,
    "sd_data_cache_status": 0x20052e04, "sd_data_cache_owner": 0x20052e08,
    "sd_data_cache_lbn": 0x20052e0c, "sd_fat_cache_status": 0x20053010,
    "sd_fat_cache_owner": 0x20053014, "sd_fat_cache_lbn": 0x20053018,
}
for index in range(6): REGISTERS[f"fp_comp{index}"] = 0xe0002008 + index * 4
for pin, base in (("b", 0x40020400), ("d", 0x40020c00)):
    for name, offset in (("mode", 0), ("type", 4), ("drive", 8), ("pull", 12), ("input", 16), ("output", 20)):
        REGISTERS["gpio" + pin + "_" + name] = base + offset
for unit, base in ((1, 0x40026400), (2, 0x40026600)):
    for channel in range(7): REGISTERS[f"dma{unit}_{channel+1}"] = base + 8 + 20 * channel
for channel in range(8): REGISTERS[f"edma_{channel+1}"] = 0x40026010 + 24 * channel
HEADER_WORDS = tuple(range(0x08010400, 0x08010460, 4))
STATE_WORDS = frozenset((*REGISTERS.values(), *HEADER_WORDS))


def decode(values, header):
    require(set(values) == set(REGISTERS) and all(type(v) is int and 0 <= v <= 0xffffffff for v in values.values()),
            "exact state register set required")
    require(isinstance(header, bytes) and len(header) == 96, "exact header bytes required")
    crc_ok = zlib.crc32(header[:92]) == struct.unpack_from("<I", header, 92)[0]
    header_shape = header[:4] == b"ETFW" and struct.unpack_from("<I", header, 4)[0] == 1 and crc_ok
    ssb = (values["usd_fap_ssb"] >> 16) & 0xff
    ssb_inverse = values["usd_fap_ssb"] >> 24
    # RM v2.07 p89 explicitly permits an erased FF/FF option pair.
    ssb_valid = ((ssb ^ ssb_inverse) == 0xff or ssb == ssb_inverse == 0xff) and not values["flash_usd"] & 1
    watchdog_option_agrees = bool(ssb & 1) == bool(values["flash_usd"] & 4)
    return dict(raw=values, header_hex=header.hex(), header_crc_valid=crc_ok,
        header_version_code=struct.unpack_from("<I", header, 8)[0] if header_shape else None,
        full_app_verified=False, wdt_pause_on_halt=bool(values["debug_apb1_frz"] & 0x1000),
        wdt_running_proven=False,
        wdt_software_start_option=(bool(ssb & 1) if ssb_valid and watchdog_option_agrees else None),
        option_complement_valid=ssb_valid, watchdog_option_latch_agrees=watchdog_option_agrees,
        ble_state=values["ble_state_word"] & 0xff, ble_isr_active=values["ble_isr_word"] & 0xff,
        overlay_owner=values["overlay_owner_word"] & 0xff,
        bcb_ram_mirror=values["confirm_mirror_word"] & 0xff,
        confirm_done_mirror=(values["confirm_mirror_word"] >> 16) & 0xff,
        sd_ready_mirror=values["sd_ready_mirror"] & 0xff,
        sd_data0_sampled_high=bool(values["gpioc_input"] & 1),
        sd_last_error=values["sd_error_word"] & 0xff,
        sd_transfer_end=(values["sd_error_word"] >> 8) & 0xff,
        sd_transfer_error=(values["sd_error_word"] >> 16) & 0xff,
        sd_stop_flag=(values["sd_error_word"] >> 24) & 0xff,
        recorder_active=values["recorder_active_word"] & 0xff,
        recorder_file_pointer=values["recorder_file"], recorder_driver_pointer=values["recorder_driver"],
        recorder_cache_pointer=values["recorder_cache"],
        recorder_file_handle_present=bool(values["recorder_file"] or values["recorder_driver"] or values["recorder_cache"]),
        sd_data_cache_dirty=bool(values["sd_data_cache_status"] & 1),
        sd_fat_cache_dirty=bool(values["sd_fat_cache_status"] & 1),
        sd_cache_owners_match=values["sd_data_cache_owner"] == values["sd_fat_cache_owner"] == 0x20052de0,
        sd_card_ready_proven=False, sd_filesystem_flushed_proven=False,
        media_safe_reset_proven=False,
        dma_enabled=[n for n, v in values.items() if (n.startswith("dma") or n.startswith("edma")) and v & 1],
        qspi_dma_enabled=bool(values["qspi_ctrl2"] & 1),
        eeprom_config_matches=bool(values["crm_ahben1"] & 2) and
            values["gpiob_mode"] & 0xf000 == 0x5000 and values["gpiob_type"] & 0xc0 == 0xc0 and
            values["gpiob_pull"] & 0xf000 == 0x5000 and values["gpiob_drive"] & 0xf000 == 0xa000,
        eeprom_pins_sampled_released=values["gpiob_output"] & 0xc0 == 0xc0 and values["gpiob_input"] & 0xc0 == 0xc0,
        atomic_snapshot=False, dma_quiescence_proven=False, eeprom_ownership_proven=False,
        device_execute_ready=False)


def sample(observation):
    def word(address):
        require(address in STATE_WORDS, "unlisted passive state address")
        data = observation._call("read", address, 4)
        require(isinstance(data, bytes) and len(data) == 4, "short passive state read")
        observation.emit("state-word", address=address, data_hex=data.hex())
        return data
    values = {name: int.from_bytes(word(address), "little") for name, address in REGISTERS.items()}
    header = b"".join(word(address) for address in HEADER_WORDS)
    return decode(values, header)
