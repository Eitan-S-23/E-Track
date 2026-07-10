#include "RouteSelect.h"

#include <stdio.h>
#include <string.h>

using namespace Page;

#define TXT_EMPTY       "\xE6\x9C\xAA\xE6\x89\xBE\xE5\x88\xB0GPX"
#define TXT_OPEN_FAIL   "\xE6\x97\xA0\xE6\xB3\x95\xE6\x89\x93\xE5\xBC\x80\xE7\x9B\xAE\xE5\xBD\x95"
#define TXT_BACK        "\xE8\xBF\x94\xE5\x9B\x9E"
#define TXT_PATH_LONG   "PATH TOO LONG"
#define ICON_BACK       "\xEE\x94\x81"
#define STATUS_BAR_H    25
#define PATH_LABEL_Y    31
#define LIST_X          8
#define LIST_Y          61
#define LIST_W          (LV_HOR_RES - LIST_X * 2)
#define LIST_H          210
#define ROW_H           38
#define BACK_X          7
#define BACK_Y          (LV_VER_RES - 36)
#define BACK_W          86
#define BACK_H          29
#define FOCUS_ANIM_MS   160
#define FOCUS_PAD_X     2
#define FOCUS_PAD_Y     2

namespace
{
    lv_style_t listStyle;
    lv_style_t btnStyle;
    lv_style_t btnFocusedStyle;
    lv_style_t iconStyle;
    lv_style_transition_dsc_t btnTransition;
    bool stylesReady = false;

    const lv_style_prop_t styleTransProps[] =
    {
        LV_STYLE_BG_COLOR,
        LV_STYLE_BG_OPA,
        LV_STYLE_BORDER_COLOR,
        LV_STYLE_BORDER_OPA,
        LV_STYLE_PROP_INV
    };

    bool EndsWithGpx(const char* name)
    {
        size_t len = strlen(name);
        if (len < 4)
        {
            return false;
        }

        const char* ext = name + len - 4;
        return ext[0] == '.' &&
               (ext[1] == 'g' || ext[1] == 'G') &&
               (ext[2] == 'p' || ext[2] == 'P') &&
               (ext[3] == 'x' || ext[3] == 'X');
    }

    const char* CleanName(const char* name)
    {
        return (name != nullptr && name[0] == '/') ? name + 1 : name;
    }

    bool IsRootPath(const char* path)
    {
        return path == nullptr || strcmp(path, "/") == 0;
    }

    bool IsHiddenEntry(const char* name)
    {
        const char* clean = CleanName(name);
        return clean == nullptr ||
               clean[0] == '\0' ||
               clean[0] == '.' ||
               strcmp(clean, "System Volume Information") == 0;
    }

    void CreateStyles()
    {
        if (stylesReady)
        {
            return;
        }
        stylesReady = true;

        lv_style_init(&listStyle);
        lv_style_set_bg_opa(&listStyle, LV_OPA_0);
        lv_style_set_pad_all(&listStyle, 0);
        lv_style_set_pad_row(&listStyle, 7);
        lv_style_set_layout(&listStyle, LV_LAYOUT_FLEX);
        lv_style_set_flex_flow(&listStyle, LV_FLEX_FLOW_COLUMN);

        lv_style_init(&btnStyle);
        lv_style_set_bg_color(&btnStyle, lv_color_hex(0x020c10));
        lv_style_set_bg_opa(&btnStyle, LV_OPA_50);
        lv_style_set_radius(&btnStyle, 5);
        lv_style_set_border_width(&btnStyle, 1);
        lv_style_set_border_color(&btnStyle, lv_color_hex(0x17333b));
        lv_style_set_border_opa(&btnStyle, LV_OPA_80);
        lv_style_set_pad_top(&btnStyle, 0);
        lv_style_set_pad_bottom(&btnStyle, 0);
        lv_style_set_pad_left(&btnStyle, 15);
        lv_style_set_pad_right(&btnStyle, 10);
        lv_style_set_pad_column(&btnStyle, 12);
        lv_style_set_layout(&btnStyle, LV_LAYOUT_FLEX);
        lv_style_set_flex_flow(&btnStyle, LV_FLEX_FLOW_ROW);
        lv_style_set_flex_main_place(&btnStyle, LV_FLEX_ALIGN_START);
        lv_style_set_flex_cross_place(&btnStyle, LV_FLEX_ALIGN_CENTER);
        lv_style_set_text_color(&btnStyle, lv_color_white());
        lv_style_set_text_font(&btnStyle, ResourcePool::GetFont("cn_16"));

        lv_style_init(&btnFocusedStyle);
        lv_style_set_bg_color(&btnFocusedStyle, lv_color_hex(0x073a40));
        lv_style_set_bg_opa(&btnFocusedStyle, LV_OPA_90);
        lv_style_set_border_color(&btnFocusedStyle, lv_color_hex(0x00f0ff));
        lv_style_set_border_opa(&btnFocusedStyle, LV_OPA_COVER);
        lv_style_set_outline_width(&btnFocusedStyle, 1);
        lv_style_set_outline_pad(&btnFocusedStyle, 1);
        lv_style_set_outline_color(&btnFocusedStyle, lv_color_hex(0x00aab6));
        lv_style_set_outline_opa(&btnFocusedStyle, LV_OPA_70);
        lv_style_transition_dsc_init(&btnTransition, styleTransProps, lv_anim_path_ease_out, 200, 0, nullptr);
        lv_style_set_transition(&btnFocusedStyle, &btnTransition);

        lv_style_init(&iconStyle);
        lv_style_set_text_color(&iconStyle, lv_color_hex(0x20e8f0));
        lv_style_set_text_font(&iconStyle, LV_FONT_DEFAULT);
    }

    bool BuildChildPath(char* out, size_t outSize, const char* parent, const char* name)
    {
        int len = IsRootPath(parent) ?
            snprintf(out, outSize, "/%s", name) :
            snprintf(out, outSize, "%s/%s", parent, name);
        return len >= 0 && len < (int)outSize;
    }

    void ApplyFocusTransition(lv_obj_t* obj)
    {
        lv_obj_set_style_transition(obj, &btnTransition, 0);
        lv_obj_set_style_transition(obj, &btnTransition, LV_STATE_FOCUSED);
    }

    void FocusHaloYAnimCb(void* obj, int32_t y)
    {
        lv_obj_set_y((lv_obj_t*)obj, (lv_coord_t)y);
    }

    void ClearFocusState(lv_obj_t* obj)
    {
        if (obj == nullptr)
        {
            return;
        }

        lv_obj_clear_state(obj, (lv_state_t)(LV_STATE_FOCUSED | LV_STATE_EDITED | LV_STATE_FOCUS_KEY));
    }
}

RouteSelect::RouteSelect()
    : account(nullptr),
      pathLabel(nullptr),
      msgLabel(nullptr),
      backButton(nullptr),
      focusHalo(nullptr),
      list(nullptr),
      pendingGoUp(false),
      pendingAsync(false),
      rowCount(0)
{
    memset(rows, 0, sizeof(rows));
    strcpy(currentPath, "/");
    pendingPath[0] = '\0';
}

RouteSelect::~RouteSelect()
{
}

void RouteSelect::onCustomAttrConfig()
{
    SetCustomLoadAnimType(PageManager::LOAD_ANIM_OVER_LEFT);
}

void RouteSelect::onViewLoad()
{
    account = new Account("RouteSelect", DataProc::Center(), 0, this);
    account->Subscribe("Navigation");
    CreateUI();
    EnterPath("/");
}

void RouteSelect::onViewWillAppear()
{
    RefreshGroup();
}

void RouteSelect::onViewWillDisappear()
{
    ClearGroup();
}

void RouteSelect::onViewUnload()
{
    ClearGroup();
    if (account)
    {
        delete account;
        account = nullptr;
    }
    focusHalo = nullptr;
}

void RouteSelect::CreateUI()
{
    CreateStyles();

    lv_obj_remove_style_all(_root);
    lv_obj_set_size(_root, LV_HOR_RES, LV_VER_RES);
    lv_obj_set_style_bg_color(_root, lv_color_hex(0x02080b), 0);
    lv_obj_set_style_bg_opa(_root, LV_OPA_COVER, 0);
    lv_obj_clear_flag(_root, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_event_cb(_root, onEvent, LV_EVENT_ALL, this);

    lv_obj_t* frame = lv_obj_create(_root);
    lv_obj_remove_style_all(frame);
    lv_obj_set_pos(frame, 2, STATUS_BAR_H);
    lv_obj_set_size(frame, LV_HOR_RES - 4, LV_VER_RES - STATUS_BAR_H - 2);
    lv_obj_set_style_border_width(frame, 1, 0);
    lv_obj_set_style_border_color(frame, lv_color_hex(0x00b7c8), 0);
    lv_obj_set_style_border_opa(frame, LV_OPA_80, 0);
    lv_obj_set_style_bg_opa(frame, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(frame, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(frame, LV_OBJ_FLAG_CLICKABLE);

    for (int i = 0; i < 12; i++)
    {
        lv_obj_t* dot = lv_obj_create(_root);
        lv_obj_remove_style_all(dot);
        lv_obj_set_pos(dot, 12 + (i * 41) % 210, 35 + (i * 31) % 180);
        lv_obj_set_size(dot, 1, 1);
        lv_obj_set_style_bg_color(dot, lv_color_hex(0x1a4a52), 0);
        lv_obj_set_style_bg_opa(dot, LV_OPA_70, 0);
    }

    CreateFocusHalo();

    lv_obj_t* titleLeft = lv_obj_create(_root);
    lv_obj_remove_style_all(titleLeft);
    lv_obj_set_pos(titleLeft, 18, PATH_LABEL_Y + 9);
    lv_obj_set_size(titleLeft, 32, 2);
    lv_obj_set_style_bg_color(titleLeft, lv_color_hex(0x00b7c8), 0);
    lv_obj_set_style_bg_opa(titleLeft, LV_OPA_80, 0);
    lv_obj_clear_flag(titleLeft, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(titleLeft, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t* titleRight = lv_obj_create(_root);
    lv_obj_remove_style_all(titleRight);
    lv_obj_set_pos(titleRight, LV_HOR_RES - 50, PATH_LABEL_Y + 9);
    lv_obj_set_size(titleRight, 32, 2);
    lv_obj_set_style_bg_color(titleRight, lv_color_hex(0x00b7c8), 0);
    lv_obj_set_style_bg_opa(titleRight, LV_OPA_80, 0);
    lv_obj_clear_flag(titleRight, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(titleRight, LV_OBJ_FLAG_CLICKABLE);

    pathLabel = lv_label_create(_root);
    lv_obj_set_style_text_font(pathLabel, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(pathLabel, lv_color_hex(0x20e8f0), 0);
    lv_obj_set_style_text_align(pathLabel, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_long_mode(pathLabel, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_width(pathLabel, LV_HOR_RES - 74);
    lv_label_set_text(pathLabel, "/");
    lv_obj_align(pathLabel, LV_ALIGN_TOP_MID, 0, PATH_LABEL_Y);

    list = lv_list_create(_root);
    lv_obj_add_style(list, &listStyle, 0);
    lv_obj_set_size(list, LIST_W, LIST_H);
    lv_obj_set_pos(list, LIST_X, LIST_Y);
    lv_obj_set_style_bg_opa(list, LV_OPA_0, 0);
    lv_obj_set_style_border_width(list, 0, 0);
    lv_obj_set_scrollbar_mode(list, LV_SCROLLBAR_MODE_AUTO);
    lv_obj_set_scroll_dir(list, LV_DIR_VER);
    lv_obj_set_style_text_font(list, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(list, lv_color_white(), 0);

    msgLabel = lv_label_create(_root);
    lv_obj_set_style_text_font(msgLabel, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(msgLabel, lv_color_hex(0x00eaff), 0);
    lv_label_set_text(msgLabel, "");
    lv_obj_align(msgLabel, LV_ALIGN_BOTTOM_MID, 0, -36);

    backButton = lv_obj_create(_root);
    lv_obj_remove_style_all(backButton);
    lv_obj_set_pos(backButton, BACK_X, BACK_Y);
    lv_obj_set_size(backButton, BACK_W, BACK_H);
    lv_obj_set_style_bg_color(backButton, lv_color_hex(0x031318), 0);
    lv_obj_set_style_bg_opa(backButton, LV_OPA_80, 0);
    lv_obj_set_style_border_width(backButton, 1, 0);
    lv_obj_set_style_border_color(backButton, lv_color_hex(0x00dfff), 0);
    lv_obj_set_style_border_opa(backButton, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(backButton, 5, 0);
    lv_obj_clear_flag(backButton, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(backButton, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(backButton, onEvent, LV_EVENT_ALL, this);

    lv_obj_t* icon = lv_label_create(backButton);
    lv_obj_set_style_text_font(icon, ResourcePool::GetFont("iconfont_20"), 0);
    lv_obj_set_style_text_color(icon, lv_color_hex(0x00eaff), 0);
    lv_label_set_text(icon, ICON_BACK);
    lv_obj_align(icon, LV_ALIGN_LEFT_MID, 7, 0);

    lv_obj_t* label = lv_label_create(backButton);
    lv_obj_set_style_text_font(label, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0x00eaff), 0);
    lv_label_set_text(label, TXT_BACK);
    lv_obj_align(label, LV_ALIGN_LEFT_MID, 31, 0);
}

void RouteSelect::CreateFocusHalo()
{
    focusHalo = lv_obj_create(_root);
    if (focusHalo == nullptr)
    {
        return;
    }

    lv_obj_remove_style_all(focusHalo);
    lv_obj_set_size(focusHalo, 10, 10);
    lv_obj_add_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(focusHalo, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(focusHalo, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_set_style_bg_color(focusHalo, lv_color_hex(0x00eaff), 0);
    lv_obj_set_style_bg_opa(focusHalo, LV_OPA_10, 0);
    lv_obj_set_style_border_width(focusHalo, 2, 0);
    lv_obj_set_style_border_color(focusHalo, lv_color_hex(0x00f2ff), 0);
    lv_obj_set_style_border_opa(focusHalo, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(focusHalo, 6, 0);
}

void RouteSelect::ClearRows()
{
    if (list)
    {
        lv_obj_clean(list);
    }
    for (uint8_t i = 0; i < ROW_MAX; i++)
    {
        rows[i].row = nullptr;
        rows[i].path[0] = '\0';
        rows[i].name[0] = '\0';
        rows[i].isDir = false;
        rows[i].isUp = false;
    }
    rowCount = 0;
}

void RouteSelect::RequestEnterPath(const char* path)
{
    if (path == nullptr || path[0] == '\0' || strlen(path) >= sizeof(pendingPath))
    {
        return;
    }

    strcpy(pendingPath, path);
    pendingGoUp = false;
    if (!pendingAsync)
    {
        pendingAsync = true;
        lv_async_call(onAsyncAction, this);
    }
}

void RouteSelect::RequestGoUp()
{
    pendingPath[0] = '\0';
    pendingGoUp = true;
    if (!pendingAsync)
    {
        pendingAsync = true;
        lv_async_call(onAsyncAction, this);
    }
}

void RouteSelect::RunPendingAction()
{
    pendingAsync = false;
    if (pendingGoUp)
    {
        pendingGoUp = false;
        GoUp();
        return;
    }
    if (pendingPath[0])
    {
        char path[NAV_PATH_MAX];
        strcpy(path, pendingPath);
        pendingPath[0] = '\0';
        EnterPath(path);
    }
}

void RouteSelect::LoadFiles()
{
    ClearRows();
    lv_label_set_text(msgLabel, "");
    lv_label_set_text(pathLabel, currentPath);

    if (!IsRootPath(currentPath))
    {
        AddRow("..", "", true, true);
    }

    lv_fs_dir_t dir;
    if (lv_fs_dir_open(&dir, currentPath) != LV_FS_RES_OK)
    {
        lv_label_set_text(msgLabel, TXT_OPEN_FAIL);
        return;
    }

    bool pathTooLong = false;
    char name[LV_FS_MAX_FN_LENGTH];
    while (rowCount < ROW_MAX)
    {
        if (lv_fs_dir_read(&dir, name) != LV_FS_RES_OK || name[0] == '\0')
        {
            break;
        }

        if (IsHiddenEntry(name))
        {
            continue;
        }

        bool isDir = name[0] == '/';
        const char* clean = CleanName(name);
        if (!isDir && !EndsWithGpx(clean))
        {
            continue;
        }

        char path[NAV_PATH_MAX];
        if (!BuildChildPath(path, sizeof(path), currentPath, clean))
        {
            pathTooLong = true;
            continue;
        }

        AddRow(clean, path, isDir, false);
    }
    lv_fs_dir_close(&dir);

    if (rowCount == 0 || (rowCount == 1 && rows[0].isUp))
    {
        lv_label_set_text(msgLabel, pathTooLong ? TXT_PATH_LONG : TXT_EMPTY);
    }
    else if (pathTooLong)
    {
        lv_label_set_text(msgLabel, TXT_PATH_LONG);
    }
}

void RouteSelect::AddRow(const char* name, const char* path, bool isDir, bool isUp)
{
    if (rowCount >= ROW_MAX || name == nullptr || list == nullptr)
    {
        return;
    }

    uint8_t idx = rowCount;
    Row_t* item = &rows[idx];
    strncpy(item->name, name, sizeof(item->name));
    item->name[sizeof(item->name) - 1] = '\0';
    if (path)
    {
        strncpy(item->path, path, sizeof(item->path));
        item->path[sizeof(item->path) - 1] = '\0';
    }
    item->isDir = isDir;
    item->isUp = isUp;

    const char* iconSrc = isUp ? LV_SYMBOL_UP : (isDir ? LV_SYMBOL_DIRECTORY : LV_SYMBOL_FILE);
    lv_obj_t* row = lv_list_add_btn(list, iconSrc, name);
    lv_obj_add_style(row, &btnStyle, 0);
    lv_obj_add_style(row, &btnFocusedStyle, LV_STATE_FOCUSED);
    lv_obj_add_style(row, &btnFocusedStyle, LV_STATE_PRESSED);
    ApplyFocusTransition(row);
    lv_obj_set_height(row, ROW_H);
    lv_obj_set_style_layout(row, 0, 0);
    lv_obj_set_style_text_color(row, lv_color_white(), 0);
    lv_obj_set_style_text_font(row, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_add_event_cb(row, onEvent, LV_EVENT_ALL, this);

    if (lv_obj_get_child_cnt(row) > 0)
    {
        lv_obj_t* icon = lv_obj_get_child(row, 0);
        lv_obj_add_style(icon, &iconStyle, 0);
        lv_obj_set_style_text_color(icon, lv_color_hex(isDir ? 0x20e8f0 : 0x53f04b), 0);
        lv_obj_align(icon, LV_ALIGN_LEFT_MID, 13, 0);
    }
    if (lv_obj_get_child_cnt(row) > 1)
    {
        lv_obj_t* label = lv_obj_get_child(row, 1);
        lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
        lv_obj_set_width(label, LIST_W - 76);
        lv_obj_set_style_text_color(label, lv_color_white(), 0);
        lv_obj_set_style_text_font(label, ResourcePool::GetFont("cn_16"), 0);
        lv_obj_align(label, LV_ALIGN_LEFT_MID, 42, 0);
    }

    item->row = row;
    rowCount++;
}

void RouteSelect::EnterPath(const char* path)
{
    if (path == nullptr || path[0] == '\0' || strlen(path) >= sizeof(currentPath))
    {
        if (msgLabel)
        {
            lv_label_set_text(msgLabel, TXT_PATH_LONG);
        }
        return;
    }

    strcpy(currentPath, path);
    LoadFiles();
    RefreshGroup();
}

void RouteSelect::GoUp()
{
    if (IsRootPath(currentPath))
    {
        Back();
        return;
    }

    char* slash = strrchr(currentPath, '/');
    if (slash == nullptr || slash == currentPath)
    {
        strcpy(currentPath, "/");
    }
    else
    {
        *slash = '\0';
    }
    LoadFiles();
    RefreshGroup();
}

void RouteSelect::SelectRow(uint8_t index)
{
    if (index >= rowCount || account == nullptr)
    {
        return;
    }

    if (rows[index].isUp)
    {
        RequestGoUp();
        return;
    }
    if (rows[index].isDir)
    {
        RequestEnterPath(rows[index].path);
        return;
    }

    DataProc::Navigation_CmdInfo_t cmd;
    DATA_PROC_INIT_STRUCT(cmd);
    cmd.cmd = DataProc::NAV_CMD_SELECT_ROUTE;
    strncpy(cmd.param.selectRoute.gpxPath, rows[index].path, sizeof(cmd.param.selectRoute.gpxPath));
    cmd.param.selectRoute.gpxPath[sizeof(cmd.param.selectRoute.gpxPath) - 1] = '\0';
    strncpy(cmd.param.selectRoute.routeName, rows[index].name, sizeof(cmd.param.selectRoute.routeName));
    cmd.param.selectRoute.routeName[sizeof(cmd.param.selectRoute.routeName) - 1] = '\0';
    account->Notify("Navigation", &cmd, sizeof(cmd));

    _Manager->Replace("Pages/RouteImport");
}

bool RouteSelect::IsFocusTarget(lv_obj_t* obj)
{
    if (obj == nullptr)
    {
        return false;
    }
    if (obj == backButton)
    {
        return true;
    }
    for (uint8_t i = 0; i < rowCount; i++)
    {
        if (obj == rows[i].row)
        {
            return true;
        }
    }
    return false;
}

void RouteSelect::MoveFocusHaloTo(lv_obj_t* obj, bool anim)
{
    if (focusHalo == nullptr || obj == nullptr)
    {
        return;
    }

    lv_obj_scroll_to_view(obj, LV_ANIM_OFF);
    lv_obj_move_foreground(focusHalo);

    lv_area_t objArea;
    lv_area_t rootArea;
    lv_obj_get_coords(obj, &objArea);
    lv_obj_get_coords(_root, &rootArea);

    lv_coord_t x = objArea.x1 - rootArea.x1 - FOCUS_PAD_X;
    lv_coord_t y = objArea.y1 - rootArea.y1 - FOCUS_PAD_Y;
    lv_coord_t w = lv_obj_get_width(obj) + FOCUS_PAD_X * 2;
    lv_coord_t h = lv_obj_get_height(obj) + FOCUS_PAD_Y * 2;
    bool wasHidden = lv_obj_has_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);

    lv_obj_clear_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);
    lv_obj_set_x(focusHalo, x);
    lv_obj_set_size(focusHalo, w, h);

    lv_anim_del(focusHalo, FocusHaloYAnimCb);
    if (anim && !wasHidden)
    {
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, focusHalo);
        lv_anim_set_exec_cb(&a, FocusHaloYAnimCb);
        lv_anim_set_values(&a, lv_obj_get_y(focusHalo), y);
        lv_anim_set_time(&a, FOCUS_ANIM_MS);
        lv_anim_set_path_cb(&a, lv_anim_path_ease_out);
        lv_anim_start(&a);
    }
    else
    {
        lv_obj_set_y(focusHalo, y);
    }
}

void RouteSelect::Back()
{
    _Manager->Pop();
}

void RouteSelect::RefreshGroup()
{
    lv_group_t* group = lv_group_get_default();
    if (group == nullptr)
    {
        return;
    }
    lv_group_remove_all_objs(group);
    lv_group_set_focus_cb(group, nullptr);
    lv_group_set_wrap(group, true);
    lv_group_set_editing(group, false);
    for (uint8_t i = 0; i < rowCount; i++)
    {
        if (rows[i].row)
        {
            lv_group_add_obj(group, rows[i].row);
        }
    }
    if (backButton)
    {
        lv_group_add_obj(group, backButton);
    }
    if (rowCount > 0 && rows[0].row)
    {
        MoveFocusHaloTo(rows[0].row, false);
        lv_group_focus_obj(rows[0].row);
    }
    else if (backButton)
    {
        MoveFocusHaloTo(backButton, false);
        lv_group_focus_obj(backButton);
    }
}

void RouteSelect::ClearGroup()
{
    lv_group_t* group = lv_group_get_default();
    if (group)
    {
        for (uint8_t i = 0; i < rowCount; i++)
        {
            if (rows[i].row != nullptr)
            {
                if (lv_obj_get_group(rows[i].row) == group)
                {
                    lv_group_remove_obj(rows[i].row);
                }
                ClearFocusState(rows[i].row);
            }
        }

        if (backButton != nullptr)
        {
            if (lv_obj_get_group(backButton) == group)
            {
                lv_group_remove_obj(backButton);
            }
            ClearFocusState(backButton);
        }
    }
    if (focusHalo)
    {
        lv_anim_del(focusHalo, FocusHaloYAnimCb);
        lv_obj_add_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);
    }
}

void RouteSelect::onEvent(lv_event_t* event)
{
    RouteSelect* instance = (RouteSelect*)lv_event_get_user_data(event);
    if (instance == nullptr)
    {
        return;
    }

    lv_obj_t* obj = lv_event_get_current_target(event);
    lv_event_code_t code = lv_event_get_code(event);

    if (code == LV_EVENT_FOCUSED)
    {
        if (instance->IsFocusTarget(obj))
        {
            instance->MoveFocusHaloTo(obj, true);
        }
        return;
    }

    if (obj == instance->_root && (code == LV_EVENT_LEAVE || code == LV_EVENT_GESTURE))
    {
        instance->RequestGoUp();
        return;
    }
    if (code != LV_EVENT_SHORT_CLICKED)
    {
        return;
    }

    if (obj == instance->backButton)
    {
        instance->Back();
        return;
    }
    for (uint8_t i = 0; i < instance->rowCount; i++)
    {
        if (obj == instance->rows[i].row)
        {
            instance->SelectRow(i);
            return;
        }
    }
}

void RouteSelect::onAsyncAction(void* userData)
{
    RouteSelect* instance = (RouteSelect*)userData;
    if (instance)
    {
        instance->RunPendingAction();
    }
}
