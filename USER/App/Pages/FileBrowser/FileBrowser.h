#ifndef FILE_BROWSER_H
#define FILE_BROWSER_H

#include "../Page.h"
#include "ff.h"

#define MAX_PATH_LEN 256
#define DISP_HOR_RES 240
#define DISP_VER_RES 280

typedef struct {
    lv_obj_t* list;
    char current_path[MAX_PATH_LEN];
    uint16_t file_count;
} FileBrowser;

void file_browser_init(void);
void file_browser_create(void);
void file_browser_refresh(void);
lv_obj_t* file_browser_get_screen(void);
lv_obj_t* file_browser_get_path_label(void);

#endif
