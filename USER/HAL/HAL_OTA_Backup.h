#ifndef E_TRACK_HAL_OTA_BACKUP_H
#define E_TRACK_HAL_OTA_BACKUP_H

/*
 * P2-5 App 侧：backup 自拷/STAGED 提交与独立看门狗服务的 HAL 端口。
 * 生产实现位于 HAL_EEPROM.cpp（BCB HAL 注入 + 独立看门狗）与
 * HAL_OTA_Package.cpp（QSPI 槽擦写 + XIP 读）；OtaUpdate::Session 与
 * USER/main.cpp 只依赖本头。
 */

#include "EEPROM/eeprom_bcb.h"
#include "OTA/ota_backup.h"

namespace HAL
{

/* BCB 事务 HAL 端口（EEPROM 逐页安全写 + 读回，契约 §3.3）。 */
const bcb_hal_t *OTA_GetBcbHal(void);

/* 当前活动 BCB state 快照（1..5）；仲裁失败/双坏返回 0xFF。 */
uint8_t OTA_GetBcbState(void);

/* 独立看门狗服务：TEST_BOOT 期间由主循环每圈调用（boot 已起动 WDT）。 */
void OTA_WatchdogFeed(void);

/* boot 是否以 TEST_BOOT 参数起动了独立看门狗（WDT->div==DIV_256 且
 * WDT->rld==boot 起动重载值）。 */
int OTA_WatchdogIsConfigured(void);

/* 执行 backup 自拷 + candidate/backup 槽头 + BCB=STAGED 原子提交
 * （Libraries/OTA/ota_backup.c 的 QSPI/XIP 实现）。返回 OTA_BACKUP_OK
 * 或错误码；任何失败不提交 STAGED，活动 BCB 保持 CONFIRMED。 */
ota_backup_result_t OTA_BackupStage(ota_backup_info_t *out);

}

#endif /* E_TRACK_HAL_OTA_BACKUP_H */
