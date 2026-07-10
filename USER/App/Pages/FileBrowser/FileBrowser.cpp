#include "FileBrowser.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

static FileBrowser browser;
static lv_obj_t *path_label;

// ================== 样式定义 ==================
static lv_style_t list_style;        // 列表样式
static lv_style_t btn_style;         // 按钮基础样式
static lv_style_t btn_focused_style; // 焦点样式
static lv_style_t icon_style;        // 图标样式

lv_obj_t *file_browser_get_screen(void)
{
    return browser.list;
}

lv_obj_t *file_browser_get_path_label(void)
{
    return path_label;
}

// 过渡属性
static const lv_style_prop_t style_trans_props[] = {
    LV_STYLE_BG_COLOR,
    LV_STYLE_BG_OPA,
    LV_STYLE_PROP_INV};

static void create_styles(void)
{
    // 列表样式
    lv_style_init(&list_style);
    lv_style_set_bg_opa(&list_style, LV_OPA_0);
    lv_style_set_pad_all(&list_style, 5);
    lv_style_set_layout(&list_style, LV_LAYOUT_FLEX);
    lv_style_set_flex_flow(&list_style, LV_FLEX_FLOW_COLUMN);

    // 按钮基础样式
    lv_style_init(&btn_style);
    lv_style_set_bg_opa(&btn_style, LV_OPA_0);
    lv_style_set_pad_all(&btn_style, 8);
    lv_style_set_layout(&btn_style, LV_LAYOUT_FLEX);
    lv_style_set_flex_flow(&btn_style, LV_FLEX_FLOW_ROW);
    lv_style_set_flex_main_place(&btn_style, LV_FLEX_ALIGN_START);

    // 焦点/按下样式
    lv_style_init(&btn_focused_style);
    lv_color_t custom_color = LV_COLOR_MAKE(240, 240, 240);
    lv_style_set_bg_color(&btn_focused_style, custom_color);
    lv_style_set_bg_opa(&btn_focused_style, LV_OPA_50);
    lv_style_set_transition(&btn_focused_style, &(lv_style_transition_dsc_t){
                                                    .props = style_trans_props,
                                                    .time = 200,
                                                    .delay = 0});

    // 图标样式
    lv_style_init(&icon_style);
    lv_style_set_text_color(&icon_style, lv_palette_main(LV_PALETTE_BLUE));
    lv_style_set_text_font(&icon_style, LV_FONT_DEFAULT);
}

static uint16_t count_files(void)
{
    DIR dir;
    uint16_t count = 0;

    FRESULT res = f_opendir(&dir, browser.current_path);
    if (res != FR_OK)
    {
        printf("[SCAN] Open dir failed: %d\r\n", res);
        return 0;
    }

    FILINFO fno;
    while (1)
    {
        res = f_readdir(&dir, &fno);
        if (res != FR_OK || fno.fname[0] == 0)
            break;

        // 跳过隐藏文件
        if (fno.fname[0] == '.' || strcmp(fno.fname, "System Volume Information") == 0)
            continue;

        count++;
    }
    f_closedir(&dir);
    return count;
}

static void get_parent_dir(void)
{
    char *last_slash = strrchr(browser.current_path, '/');
    if (!last_slash)
        return;

    // 根目录处理（0:/）
    if (last_slash == browser.current_path + 2)
    {
        last_slash[1] = '\0'; // 保持0:/
    }
    else
    {
        *last_slash = '\0';
    }
    printf("[PATH] Up to: %s\r\n", browser.current_path);
}

static void enter_child_dir(const char *dir_name)
{
    size_t len = strlen(browser.current_path);

    // 确保路径格式正确
    if (len > 0 && browser.current_path[len - 1] != '/')
    {
        strcat(browser.current_path, "/");
    }
    strncat(browser.current_path, dir_name, MAX_PATH_LEN - len - 1);
    printf("[PATH] Enter: %s\r\n", browser.current_path);
}

// 根据一个文件的完整路径获取同一目录下另一个文件的完整路径
void get_same_dir_file_path(const char *original_path, const char *new_file_name, char *result_path, size_t result_path_size)
{
    char dir_path[256];
    // 查找路径中最后一个斜杠的位置
    const char *last_slash = strrchr(original_path, '/');
    if (last_slash == NULL)
    {
        // 如果没有斜杠，说明路径只有文件名，目录默认为当前目录
        strcpy(dir_path, "./");
    }
    else
    {
        // 复制目录部分到dir_path
        strncpy(dir_path, original_path, last_slash - original_path + 1);
        dir_path[last_slash - original_path + 1] = '\0';
    }
    // 拼接新文件的完整路径
    snprintf(result_path, result_path_size, "%s%s", dir_path, new_file_name);
}

void overwrite_file(const char *full_path)
{
    FIL file;
    FRESULT res;
    UINT bytes_written;
    char iar_path[64] = "0:/IAP"; // Adjust length as needed

    // Make sure IAP directory exists
    DIR dir;
    res = f_opendir(&dir, iar_path);
    if (res == FR_OK)
    {
        f_closedir(&dir);
    }
    else
    {
        // Try to create directory if it doesn't exist
        res = f_mkdir(iar_path);
        if (res != FR_OK)
        {
            printf("[ERROR] Failed to access or create IAP directory, error: %d\r\n", res);
            return;
        }
    }

    // Complete the file path
    strcat(iar_path, "/IAP.TXT");

    // Prepare content to write
    char write_content[256];
    snprintf(write_content, sizeof(write_content), "1 1 %s", full_path);

    // First try to open existing file
    res = f_open(&file, iar_path, FA_WRITE);
    if (res != FR_OK)
    {
        // If that fails, try to create a new file
        res = f_open(&file, iar_path, FA_CREATE_ALWAYS | FA_WRITE);
        if (res != FR_OK)
        {
            printf("[ERROR] Failed to open or create IAP.TXT, error: %d\r\n", res);
            return;
        }
    }
    else
    {
        // File exists, truncate it by setting file size to 0
        res = f_lseek(&file, 0);
        if (res != FR_OK)
        {
            printf("[ERROR] Failed to seek in file, error: %d\r\n", res);
            f_close(&file);
            return;
        }

        res = f_truncate(&file);
        if (res != FR_OK)
        {
            printf("[ERROR] Failed to truncate file, error: %d\r\n", res);
            f_close(&file);
            return;
        }
    }

    // Write content to file
    res = f_write(&file, write_content, strlen(write_content), &bytes_written);
    if (res != FR_OK || bytes_written != strlen(write_content))
    {
        printf("[ERROR] Failed to write to IAP.TXT, error: %d\r\n", res);
        f_close(&file);
        return;
    }

    // Ensure data is physically written to the media
    res = f_sync(&file);
    if (res != FR_OK)
    {
        printf("[ERROR] Failed to sync file, error: %d\r\n", res);
    }

    // Close the file
    f_close(&file);

    printf("[SUCCESS] Wrote to IAP.TXT: %s\r\n", write_content);
}

void restart_to_bootloader(void)
{
    // 恢复中断向量表到默认位置
    SCB->VTOR = 0x08000000;
    // 触发系统复位
    HAL_NVIC_SystemReset();
}

void close_lvgl_and_clear_screen(void)
{
    // 销毁所有 LVGL 对象
    lv_obj_clean(lv_scr_act());
    // 清屏操作，这里假设使用的是 HAL 库的 LCD 驱动
    HAL_GPIO_WritePin(GPIOA, LCD_BLK_Pin, GPIO_PIN_RESET);
    // 停止 LVGL 任务
    lv_deinit();
}

static lv_obj_t *upgrade_win;

static void btn_event_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    lv_obj_t *btn = lv_event_get_target(e);
    const char *txt = lv_label_get_text(lv_obj_get_child(btn, 0));
    char *filename = (char *)lv_event_get_user_data(e);

    printf("Button event triggered. Code: %d, Button text: %s\r\n", code, txt);

    if (code == LV_EVENT_CLICKED)
    {
        if (strcmp(txt, "Yes") == 0)
        {
            overwrite_file(filename);
            if (filename != NULL)
            {
                printf("Current file name: %s\r\n", filename);
            }
            vTaskDelay(pdMS_TO_TICKS(300));
            close_lvgl_and_clear_screen();
            restart_to_bootloader();
        }
        // 释放分配的内存
        if (filename != NULL)
        {
            free(filename);
        }
        // 关闭窗口
        lv_obj_del(upgrade_win);
        upgrade_win = NULL;
    }
}

void show_upgrade_popup(const char *path)
{
    if (upgrade_win)
        return;

    // 创建窗口
    upgrade_win = lv_obj_create(lv_scr_act());
    lv_obj_set_size(upgrade_win, 180, 150);
    lv_obj_align(upgrade_win, LV_ALIGN_CENTER, 0, 0);

    // 分配堆内存，确保字符串不会被后续操作修改
    char *full_path = (char *)malloc(256);
    if (full_path == NULL)
    {
        printf("Memory allocation failed\r\n");
        return;
    }

    // 复制路径
    strncpy(full_path, path, 255);
    full_path[255] = '\0'; // 确保字符串结束

    // 顶部标题
    lv_obj_t *title_label = lv_label_create(upgrade_win);
    lv_label_set_text(title_label, "Upgrade?");
    lv_obj_align(title_label, LV_ALIGN_TOP_MID, 0, 10);
    printf("file name: %s\r\n", full_path);

    // 底部按钮
    const char *btns[] = {"Yes", "No"};
    for (uint8_t i = 0; i < 2; i++)
    {
        lv_obj_t *btn = lv_btn_create(upgrade_win);
        lv_obj_align(btn, LV_ALIGN_BOTTOM_MID, (i * 100) - 50, -10);
        lv_obj_t *label = lv_label_create(btn);
        lv_label_set_text(label, btns[i]);
        lv_obj_add_event_cb(btn, btn_event_cb, LV_EVENT_CLICKED, full_path);
    }
}

// ================== 事件处理 ==================
static void event_handler(lv_event_t *e)
{
    lv_obj_t *btn = lv_event_get_target(e);
    lv_obj_t *label = lv_obj_get_child(btn, 1); // 获取文件名标签

    const char *fname = lv_label_get_text(label);
    printf("[EVENT] Clicked: %s\r\n", fname);

    // 处理导航
    if (strcmp(fname, "..") == 0)
    {
        get_parent_dir();
    }
    else
    {
        DIR dir;
        FRESULT res = f_opendir(&dir, browser.current_path);
        if (res != FR_OK)
        {
            printf("[OPEN] Open dir failed: %d\r\n", res);
            return;
        }

        FILINFO fno;
        while (1)
        {
            res = f_readdir(&dir, &fno);
            if (res != FR_OK || fno.fname[0] == 0)
                break;

            if (strcmp(fno.fname, fname) == 0)
            {
                if (fno.fattrib & AM_DIR)
                {
                    enter_child_dir(fname);
                }
                else
                {
                    char full_path[MAX_PATH_LEN + 64];
                    snprintf(full_path, sizeof(full_path), "%s/%s", browser.current_path, fname);
                    printf("[OPEN] %s\r\n", full_path);

                    // 根据扩展名处理文件
                    if (strstr(fname, ".jpg") || strstr(fname, ".png") || strstr(fname, ".bmp"))
                    {
                        // 示例路径：browser.current_path = "0:/Pictures", fname = "photo1.jpg"
                        // 打开查看器（传递当前目录和文件名）
                        image_viewer_open(browser.current_path, fname);
                    }
                    else if (strstr(fname, ".bin"))
                    {
                        show_upgrade_popup(full_path);
                    }
                    else if (strstr(fname, ".mp4"))
                    {
                        media_player_open(full_path);
                    }
                }
                break;
            }
        }
        f_closedir(&dir);
    }

    file_browser_refresh();
}

// ================== 界面相关 ==================
void file_browser_init(void)
{
    create_styles();
    memset(&browser, 0, sizeof(FileBrowser));
    snprintf(browser.current_path, MAX_PATH_LEN, "0:/");
}

void file_browser_create(void)
{
    // 路径显示标签
    path_label = lv_label_create(lv_scr_act());
    lv_label_set_long_mode(path_label, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_width(path_label, DISP_HOR_RES - 20);
    lv_obj_align(path_label, LV_ALIGN_TOP_MID, 0, 5);
    lv_obj_set_style_text_align(path_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_font(path_label, &lv_font_montserrat_14, 0); // Set font for path label

    // 文件列表
    browser.list = lv_list_create(lv_scr_act());
    lv_obj_add_style(browser.list, &list_style, 0);
    lv_obj_set_size(browser.list, DISP_HOR_RES, DISP_VER_RES - 30);
    lv_obj_align(browser.list, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_text_font(browser.list, &my_font_20, 0); // Set font for file list

    file_browser_refresh();
}

void file_browser_refresh(void)
{
    lv_label_set_text(path_label, browser.current_path);
    lv_obj_clean(browser.list);
    browser.file_count = count_files();

    // 添加返回按钮
    if (strcmp(browser.current_path, "0:/") != 0)
    {
        lv_obj_t *btn = lv_list_add_btn(browser.list, LV_SYMBOL_DIRECTORY, "..");
        lv_obj_add_style(btn, &btn_style, 0);
        lv_obj_add_style(btn, &btn_focused_style, LV_STATE_PRESSED);
        lv_obj_add_style(btn, &icon_style, LV_PART_MAIN);
        lv_obj_add_event_cb(btn, event_handler, LV_EVENT_CLICKED, NULL);
    }

    DIR dir;
    FRESULT res = f_opendir(&dir, browser.current_path);
    if (res != FR_OK)
    {
        printf("[SCAN] Open dir failed: %d\r\n", res);
        return;
    }

    FILINFO fno;
    uint16_t index = 0;
    while (1)
    {
        res = f_readdir(&dir, &fno);
        if (res != FR_OK || fno.fname[0] == 0)
            break;

        // 跳过隐藏文件
        if (fno.fname[0] == '.' || strcmp(fno.fname, "System Volume Information") == 0)
            continue;

        const char *icon;
        uint8_t is_dir = fno.fattrib & AM_DIR;

        if (is_dir)
        {
            // Use standard directory icon for all folders
            icon = LV_SYMBOL_DIRECTORY;
        }
        else if (strstr(fno.fname, ".jpg") ||
                 strstr(fno.fname, ".png") ||
                 strstr(fno.fname, ".bmp"))
        {
            // Keep existing image file icon
            icon = LV_SYMBOL_IMAGE;
        }
        else if (strstr(fno.fname, ".mp4"))
        {
            // Keep existing video file icon
            icon = LV_SYMBOL_VIDEO;
        }
        else if (strstr(fno.fname, ".bin"))
        {
            // Keep existing binary/upload file icon
            icon = LV_SYMBOL_UPLOAD;
        }
        else
        {
            // Use standard file icon for all other files
            icon = LV_SYMBOL_FILE;
        }

        lv_obj_t *btn = lv_list_add_btn(browser.list, icon, fno.fname);
        lv_obj_add_style(btn, &btn_style, 0);
        lv_obj_add_style(btn, &btn_focused_style, LV_STATE_PRESSED);
        lv_obj_add_style(btn, &icon_style, LV_PART_MAIN);
        lv_obj_add_event_cb(btn, event_handler, LV_EVENT_CLICKED, NULL);

        // 设置文件名样式
        lv_obj_t *label = lv_obj_get_child(btn, 1);
        lv_obj_set_style_text_color(label, lv_color_black(), 0);
        lv_obj_set_style_text_font(label, &lv_font_montserrat_14, 0);

        index++;
    }
    f_closedir(&dir);
}
