#ifndef E_TRACK_TEST_LVGL_H
#define E_TRACK_TEST_LVGL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LVGL_VERSION_MAJOR 8
#define LVGL_VERSION_MINOR 3
#define LVGL_VERSION_PATCH 11
#define LVGL_VERSION_INFO "test"

typedef enum lv_fs_res_t
{
    LV_FS_RES_OK = 0,
    LV_FS_RES_HW_ERR,
    LV_FS_RES_FS_ERR,
    LV_FS_RES_NOT_EX,
    LV_FS_RES_FULL,
    LV_FS_RES_LOCKED,
    LV_FS_RES_DENIED,
    LV_FS_RES_BUSY,
    LV_FS_RES_TOUT,
    LV_FS_RES_NOT_IMP,
    LV_FS_RES_OUT_OF_MEM,
    LV_FS_RES_INV_PARAM,
    LV_FS_RES_UNKNOWN
} lv_fs_res_t;

typedef enum lv_fs_mode_t
{
    LV_FS_MODE_WR = 0x01,
    LV_FS_MODE_RD = 0x02
} lv_fs_mode_t;

typedef enum lv_fs_whence_t
{
    LV_FS_SEEK_SET = 0,
    LV_FS_SEEK_CUR,
    LV_FS_SEEK_END
} lv_fs_whence_t;

typedef struct lv_fs_file_t
{
    void* file_d;
} lv_fs_file_t;

lv_fs_res_t lv_fs_open(lv_fs_file_t* file, const char* path,
                       lv_fs_mode_t mode);
lv_fs_res_t lv_fs_close(lv_fs_file_t* file);
lv_fs_res_t lv_fs_read(lv_fs_file_t* file, void* buf, uint32_t btr,
                       uint32_t* br);
lv_fs_res_t lv_fs_seek(lv_fs_file_t* file, uint32_t pos,
                       lv_fs_whence_t whence);
lv_fs_res_t lv_fs_tell(lv_fs_file_t* file, uint32_t* pos);

#ifdef __cplusplus
}
#endif

#endif
