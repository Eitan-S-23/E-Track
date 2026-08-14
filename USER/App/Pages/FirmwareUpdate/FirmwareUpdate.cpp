#include "FirmwareUpdate.h"

#include <stdio.h>
#include <string.h>
#if !defined(_WIN32)
#include "wdg.h"
#endif

using namespace Page;

#define TXT_FILE_MANAGER "\xE6\x96\x87\xE4\xBB\xB6\xE7\xAE\xA1\xE7\x90\x86"
#define TXT_EMPTY        "\xE6\x9C\xAA\xE6\x89\xBE\xE5\x88\xB0 ETU"
#define TXT_OPEN_FAIL    "\xE6\x97\xA0\xE6\xB3\x95\xE6\x89\x93\xE5\xBC\x80\xE7\x9B\xAE\xE5\xBD\x95"
#define TXT_FILE_INVALID "\xE6\x96\x87\xE4\xBB\xB6\xE6\x97\xA0\xE6\x95\x88"
#define TXT_CURRENT_VER  "\xE5\xBD\x93\xE5\x89\x8D\xE7\x89\x88\xE6\x9C\xAC"
#define TXT_FILE_VER     "\xE6\x96\x87\xE4\xBB\xB6\xE7\x89\x88\xE6\x9C\xAC"
#define TXT_START_IMPORT "\xE5\xBC\x80\xE5\xA7\x8B\xE5\xAF\xBC\xE5\x85\xA5"
#define TXT_IMPORTING    "\xE5\xAF\xBC\xE5\x85\xA5\xE4\xB8\xAD"
#define TXT_READY        "\xE5\xB7\xB2\xE5\xB0\xB1\xE7\xBB\xAA"
#define TXT_STAGED_READY "\xE5\xB7\xB2\xE5\xB0\xB1\xE7\xBB\xAA\xEF\xBC\x8C\xE5\x85\xB3\xE6\x9C\xBA\xE5\x90\x8E\xE5\xBC\x80\xE6\x9C\xBA"
#define TXT_FAILED       "\xE5\xAF\xBC\xE5\x85\xA5\xE5\xA4\xB1\xE8\xB4\xA5"
#define TXT_BACK         "\xE8\xBF\x94\xE5\x9B\x9E"
#define TXT_PATH_LONG    "PATH TOO LONG"
#define TXT_SCAN_LIMIT "MORE FILES EXIST\nNOT ALL SHOWN"
#define ICON_BACK        "\xEE\x94\x81"

#define STATUS_BAR_H     25
#define TITLE_Y          29
#define PATH_Y           50
#define PANEL_Y          56
#define LIST_X           8
#define LIST_Y           72
#define LIST_W           (LV_HOR_RES - LIST_X * 2)
#define LIST_H           204
#define LIST_H_MESSAGE   174
#define ROW_H            38
#define BACK_X           7
#define BACK_Y           (LV_VER_RES - 36)
#define BACK_W           86
#define BACK_H           29
#define FOCUS_ANIM_MS    160
#define FOCUS_PAD_X      2
#define FOCUS_PAD_Y      2
#define WORK_STEP_BYTES  4096u

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

    const char* CleanName(const char* name)
    {
        return name != nullptr && name[0] == '/' ? name + 1 : name;
    }

    bool IsRootPath(const char* path)
    {
        return path == nullptr || strcmp(path, "/") == 0;
    }

    bool IsHiddenEntry(const char* name)
    {
        const char* clean = CleanName(name);
        return clean == nullptr || clean[0] == '\0' || clean[0] == '.' ||
               strcmp(clean, "System Volume Information") == 0;
    }

    bool BuildChildPath(char* out, size_t outSize,
                        const char* parent, const char* name)
    {
        int len = IsRootPath(parent)
                      ? snprintf(out, outSize, "/%s", name)
                      : snprintf(out, outSize, "%s/%s", parent, name);
        return len >= 0 && len < (int)outSize;
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
        lv_style_set_bg_opa(&btnStyle, LV_OPA_70);
        lv_style_set_radius(&btnStyle, 5);
        lv_style_set_border_width(&btnStyle, 1);
        lv_style_set_border_color(&btnStyle, lv_color_hex(0x17333b));
        lv_style_set_border_opa(&btnStyle, LV_OPA_90);
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
        lv_style_transition_dsc_init(&btnTransition, styleTransProps,
                                     lv_anim_path_ease_out, 200, 0, nullptr);
        lv_style_set_transition(&btnFocusedStyle, &btnTransition);

        lv_style_init(&iconStyle);
        lv_style_set_text_color(&iconStyle, lv_color_hex(0x20e8f0));
        lv_style_set_text_font(&iconStyle, LV_FONT_DEFAULT);
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
        if (obj != nullptr)
        {
            lv_obj_clear_state(
                obj,
                (lv_state_t)(LV_STATE_FOCUSED | LV_STATE_EDITED |
                             LV_STATE_FOCUS_KEY));
        }
    }

    void ConfigurePlainButton(lv_obj_t* button,
                              const char* text, lv_coord_t x,
                              lv_coord_t y, lv_coord_t width)
    {
        lv_obj_remove_style_all(button);
        lv_obj_set_pos(button, x, y);
        lv_obj_set_size(button, width, 34);
        lv_obj_add_style(button, &btnStyle, 0);
        lv_obj_add_style(button, &btnFocusedStyle, LV_STATE_FOCUSED);
        lv_obj_add_style(button, &btnFocusedStyle, LV_STATE_PRESSED);
        lv_obj_set_style_layout(button, 0, 0);
        lv_obj_set_style_pad_all(button, 0, 0);
        ApplyFocusTransition(button);
        lv_obj_clear_flag(button, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_add_flag(button, LV_OBJ_FLAG_CLICKABLE);

        lv_obj_t* label = lv_label_create(button);
        lv_obj_set_style_text_font(label, ResourcePool::GetFont("cn_16"), 0);
        lv_obj_set_style_text_color(label, lv_color_white(), 0);
        lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(label, LV_PCT(100));
        lv_obj_add_flag(label, LV_OBJ_FLAG_IGNORE_LAYOUT);
        lv_label_set_text(label, text);
        lv_obj_align(label, LV_ALIGN_CENTER, 0, 1);
    }
}

FirmwareUpdate::FirmwareUpdate()
    : titleLabel(nullptr),
      pathLabel(nullptr),
      msgLabel(nullptr),
      detailLabel(nullptr),
      backButton(nullptr),
      focusHalo(nullptr),
      list(nullptr),
      confirmPanel(nullptr),
      confirmNameLabel(nullptr),
      confirmKindLabel(nullptr),
      currentVersionLabel(nullptr),
      targetVersionLabel(nullptr),
      cancelButton(nullptr),
      startButton(nullptr),
      workPanel(nullptr),
      workStatusLabel(nullptr),
      workNameLabel(nullptr),
      workKindLabel(nullptr),
      progressBar(nullptr),
      progressLabel(nullptr),
      workDetailLabel(nullptr),
      resultButton(nullptr),
      workTimer(nullptr),
      pendingGoUp(false),
      pendingBack(false),
      pendingAsync(false),
      deviceReady(false),
      applyPending(false),
      stagePending(false),
      resultSuccess(false),
      rowCount(0),
      mode(MODE_BROWSER)
{
    memset(rows, 0, sizeof(rows));
    memset(&selectedInfo, 0, sizeof(selectedInfo));
    strcpy(currentPath, "/");
    pendingPath[0] = '\0';
    selectedPath[0] = '\0';
    selectedName[0] = '\0';
}

FirmwareUpdate::~FirmwareUpdate()
{
}

void FirmwareUpdate::onCustomAttrConfig()
{
    SetCustomLoadAnimType(PageManager::LOAD_ANIM_OVER_LEFT);
}

void FirmwareUpdate::onViewLoad()
{
    deviceReady = updater.InitializeDevice();
    CreateUI();
    EnterPath("/");
    if (!deviceReady)
    {
        SetBrowserMessage(TXT_FILE_INVALID, updater.LastError());
    }
}

void FirmwareUpdate::onViewWillAppear()
{
    RefreshGroup();
}

void FirmwareUpdate::onViewWillDisappear()
{
    ClearGroup();
}

void FirmwareUpdate::onViewUnload()
{
    ReleaseUI();
    updater.Close();
}

void FirmwareUpdate::CreateUI()
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

    for (int i = 0; i < 12; ++i)
    {
        lv_obj_t* dot = lv_obj_create(_root);
        lv_obj_remove_style_all(dot);
        lv_obj_set_pos(dot, 12 + (i * 41) % 210,
                       35 + (i * 31) % 180);
        lv_obj_set_size(dot, 1, 1);
        lv_obj_set_style_bg_color(dot, lv_color_hex(0x1a4a52), 0);
        lv_obj_set_style_bg_opa(dot, LV_OPA_70, 0);
    }

    CreateFocusHalo();
    CreateBrowserUI();
}

void FirmwareUpdate::CreateBrowserUI()
{
    titleLabel = lv_label_create(_root);
    lv_obj_set_style_text_font(titleLabel, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(titleLabel, lv_color_hex(0x20e8f0), 0);
    lv_label_set_text(titleLabel, TXT_FILE_MANAGER);
    lv_obj_align(titleLabel, LV_ALIGN_TOP_MID, 0, TITLE_Y);

    pathLabel = lv_label_create(_root);
    lv_obj_set_style_text_font(pathLabel, ResourcePool::GetFont("bahnschrift_13"), 0);
    lv_obj_set_style_text_color(pathLabel, lv_color_hex(0x62aeb8), 0);
    lv_obj_set_style_text_align(pathLabel, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_long_mode(pathLabel, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_width(pathLabel, LV_HOR_RES - 34);
    lv_label_set_text(pathLabel, "/");
    lv_obj_align(pathLabel, LV_ALIGN_TOP_MID, 0, PATH_Y);

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
    lv_obj_set_style_text_align(msgLabel, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_long_mode(msgLabel, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(msgLabel, LV_HOR_RES - 24);
    lv_label_set_text(msgLabel, "");
    lv_obj_align(msgLabel, LV_ALIGN_BOTTOM_MID, 0, -37);

    detailLabel = lv_label_create(_root);
    lv_obj_set_style_text_font(detailLabel, ResourcePool::GetFont("bahnschrift_13"), 0);
    lv_obj_set_style_text_color(detailLabel, lv_color_hex(0x70a5ad), 0);
    lv_label_set_long_mode(detailLabel, LV_LABEL_LONG_DOT);
    lv_obj_set_width(detailLabel, LV_HOR_RES - 104);
    lv_obj_set_style_text_align(detailLabel, LV_TEXT_ALIGN_RIGHT, 0);
    lv_label_set_text(detailLabel, "");
    lv_obj_align(detailLabel, LV_ALIGN_BOTTOM_RIGHT, -8, -10);

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

void FirmwareUpdate::CreateConfirmUI()
{
    confirmPanel = lv_obj_create(_root);
    lv_obj_remove_style_all(confirmPanel);
    lv_obj_set_pos(confirmPanel, 10, PANEL_Y);
    lv_obj_set_size(confirmPanel, LV_HOR_RES - 20, 234);
    lv_obj_set_style_bg_color(confirmPanel, lv_color_hex(0x031116), 0);
    lv_obj_set_style_bg_opa(confirmPanel, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(confirmPanel, 1, 0);
    lv_obj_set_style_border_color(confirmPanel, lv_color_hex(0x00d8e8), 0);
    lv_obj_set_style_border_opa(confirmPanel, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(confirmPanel, 7, 0);
    lv_obj_clear_flag(confirmPanel, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);

    lv_obj_t* heading = lv_label_create(confirmPanel);
    lv_obj_set_style_text_font(heading, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(heading, lv_color_hex(0x20e8f0), 0);
    lv_label_set_text(heading, TXT_FILE_VER);
    lv_obj_align(heading, LV_ALIGN_TOP_LEFT, 12, 10);

    confirmKindLabel = lv_label_create(confirmPanel);
    lv_obj_set_style_text_font(confirmKindLabel, ResourcePool::GetFont("bahnschrift_17"), 0);
    lv_obj_set_style_text_color(confirmKindLabel, lv_color_hex(0x52f58a), 0);
    lv_label_set_text(confirmKindLabel, "FULL");
    lv_obj_align(confirmKindLabel, LV_ALIGN_TOP_RIGHT, -12, 9);

    confirmNameLabel = lv_label_create(confirmPanel);
    lv_obj_set_style_text_font(confirmNameLabel, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(confirmNameLabel, lv_color_white(), 0);
    lv_label_set_long_mode(confirmNameLabel, LV_LABEL_LONG_DOT);
    lv_obj_set_width(confirmNameLabel, LV_HOR_RES - 54);
    lv_label_set_text(confirmNameLabel, "");
    lv_obj_align(confirmNameLabel, LV_ALIGN_TOP_LEFT, 12, 43);

    lv_obj_t* currentCaption = lv_label_create(confirmPanel);
    lv_obj_set_style_text_font(currentCaption, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(currentCaption, lv_color_hex(0x70a5ad), 0);
    lv_label_set_text(currentCaption, TXT_CURRENT_VER);
    lv_obj_align(currentCaption, LV_ALIGN_TOP_LEFT, 12, 79);

    currentVersionLabel = lv_label_create(confirmPanel);
    lv_obj_set_style_text_font(currentVersionLabel, ResourcePool::GetFont("bahnschrift_24"), 0);
    lv_obj_set_style_text_color(currentVersionLabel, lv_color_white(), 0);
    lv_label_set_text(currentVersionLabel, "v0.0.0");
    lv_obj_align(currentVersionLabel, LV_ALIGN_TOP_RIGHT, -12, 75);

    lv_obj_t* targetCaption = lv_label_create(confirmPanel);
    lv_obj_set_style_text_font(targetCaption, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(targetCaption, lv_color_hex(0x70a5ad), 0);
    lv_label_set_text(targetCaption, TXT_FILE_VER);
    lv_obj_align(targetCaption, LV_ALIGN_TOP_LEFT, 12, 119);

    targetVersionLabel = lv_label_create(confirmPanel);
    lv_obj_set_style_text_font(targetVersionLabel, ResourcePool::GetFont("bahnschrift_24"), 0);
    lv_obj_set_style_text_color(targetVersionLabel, lv_color_hex(0x52f58a), 0);
    lv_label_set_text(targetVersionLabel, "v0.0.0");
    lv_obj_align(targetVersionLabel, LV_ALIGN_TOP_RIGHT, -12, 115);

    cancelButton = lv_obj_create(confirmPanel);
    ConfigurePlainButton(cancelButton, TXT_BACK, 12, 181, 82);
    lv_obj_add_event_cb(cancelButton, onEvent, LV_EVENT_ALL, this);

    startButton = lv_obj_create(confirmPanel);
    ConfigurePlainButton(startButton, TXT_START_IMPORT,
                         LV_HOR_RES - 20 - 12 - 108, 181, 108);
    lv_obj_add_event_cb(startButton, onEvent, LV_EVENT_ALL, this);
}

void FirmwareUpdate::CreateWorkUI()
{
    workPanel = lv_obj_create(_root);
    lv_obj_remove_style_all(workPanel);
    lv_obj_set_pos(workPanel, 10, PANEL_Y);
    lv_obj_set_size(workPanel, LV_HOR_RES - 20, 234);
    lv_obj_set_style_bg_color(workPanel, lv_color_hex(0x031116), 0);
    lv_obj_set_style_bg_opa(workPanel, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(workPanel, 1, 0);
    lv_obj_set_style_border_color(workPanel, lv_color_hex(0x00d8e8), 0);
    lv_obj_set_style_border_opa(workPanel, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(workPanel, 7, 0);
    lv_obj_clear_flag(workPanel, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(workPanel, LV_OBJ_FLAG_HIDDEN);

    workStatusLabel = lv_label_create(workPanel);
    lv_obj_set_style_text_font(workStatusLabel, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(workStatusLabel, lv_color_hex(0x20e8f0), 0);
    lv_label_set_text(workStatusLabel, TXT_IMPORTING);
    lv_obj_align(workStatusLabel, LV_ALIGN_TOP_LEFT, 12, 11);

    workKindLabel = lv_label_create(workPanel);
    lv_obj_set_style_text_font(workKindLabel, ResourcePool::GetFont("bahnschrift_17"), 0);
    lv_obj_set_style_text_color(workKindLabel, lv_color_hex(0x52f58a), 0);
    lv_label_set_text(workKindLabel, "FULL");
    lv_obj_align(workKindLabel, LV_ALIGN_TOP_RIGHT, -12, 10);

    workNameLabel = lv_label_create(workPanel);
    lv_obj_set_style_text_font(workNameLabel, ResourcePool::GetFont("cn_16"), 0);
    lv_obj_set_style_text_color(workNameLabel, lv_color_white(), 0);
    lv_label_set_long_mode(workNameLabel, LV_LABEL_LONG_DOT);
    lv_obj_set_width(workNameLabel, LV_HOR_RES - 54);
    lv_label_set_text(workNameLabel, "");
    lv_obj_align(workNameLabel, LV_ALIGN_TOP_LEFT, 12, 49);

    progressBar = lv_bar_create(workPanel);
    lv_obj_set_size(progressBar, LV_HOR_RES - 58, 16);
    lv_obj_align(progressBar, LV_ALIGN_TOP_MID, 0, 91);
    lv_obj_set_style_bg_color(progressBar, lv_color_hex(0x102a31), 0);
    lv_obj_set_style_bg_opa(progressBar, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(progressBar, 3, 0);
    lv_obj_set_style_bg_color(progressBar, lv_color_hex(0x20e8f0),
                              LV_PART_INDICATOR);
    lv_obj_set_style_bg_opa(progressBar, LV_OPA_COVER,
                            LV_PART_INDICATOR);
    lv_obj_set_style_radius(progressBar, 3, LV_PART_INDICATOR);
    lv_bar_set_range(progressBar, 0, 100);
    lv_bar_set_value(progressBar, 0, LV_ANIM_OFF);

    progressLabel = lv_label_create(workPanel);
    lv_obj_set_style_text_font(progressLabel, ResourcePool::GetFont("bahnschrift_24"), 0);
    lv_obj_set_style_text_color(progressLabel, lv_color_white(), 0);
    lv_label_set_text(progressLabel, "0");
    lv_obj_align(progressLabel, LV_ALIGN_TOP_MID, 0, 119);

    workDetailLabel = lv_label_create(workPanel);
    lv_obj_set_style_text_font(workDetailLabel, ResourcePool::GetFont("bahnschrift_13"), 0);
    lv_obj_set_style_text_color(workDetailLabel, lv_color_hex(0x70a5ad), 0);
    lv_label_set_long_mode(workDetailLabel, LV_LABEL_LONG_DOT);
    lv_obj_set_width(workDetailLabel, LV_HOR_RES - 54);
    lv_obj_set_style_text_align(workDetailLabel, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_text(workDetailLabel, "VERIFY + STAGING");
    lv_obj_align(workDetailLabel, LV_ALIGN_TOP_MID, 0, 155);

    resultButton = lv_obj_create(workPanel);
    ConfigurePlainButton(resultButton, TXT_BACK,
                         (LV_HOR_RES - 20 - 88) / 2, 181, 88);
    lv_obj_add_event_cb(resultButton, onEvent, LV_EVENT_ALL, this);
    lv_obj_add_flag(resultButton, LV_OBJ_FLAG_HIDDEN);
}

void FirmwareUpdate::CreateFocusHalo()
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

void FirmwareUpdate::ClearRows()
{
    if (list != nullptr)
    {
        lv_obj_clean(list);
    }
    for (uint8_t i = 0u; i < ROW_MAX; ++i)
    {
        rows[i].row = nullptr;
        rows[i].path[0] = '\0';
        rows[i].name[0] = '\0';
        rows[i].isDir = false;
        rows[i].isUp = false;
    }
    rowCount = 0u;
}

void FirmwareUpdate::LoadFiles()
{
    ClearRows();
    SetBrowserMessage("", "");
    lv_label_set_text(pathLabel, currentPath);
    if (!IsRootPath(currentPath))
    {
        AddRow("..", "", true, true);
    }

    lv_fs_dir_t dir;
    if (lv_fs_dir_open(&dir, currentPath) != LV_FS_RES_OK)
    {
        SetBrowserMessage(TXT_OPEN_FAIL, "LV_FS_DIR");
        return;
    }

    bool pathTooLong = false;
    uint16_t scanCount = 0u;
    char name[LV_FS_MAX_FN_LENGTH];

    /* Every returned entry consumes the scan bound, including hidden and
     * non-ETU files. Feed the watchdog periodically without re-entering LVGL. */
    while (rowCount < ROW_MAX && scanCount < SCAN_MAX)
    {
        if (lv_fs_dir_read(&dir, name) != LV_FS_RES_OK || name[0] == '\0')
        {
            break;
        }
        ++scanCount;
#if !defined(_WIN32)
        if ((scanCount & 0x1Fu) == 0u)
        {
            WDG_ReloadCounter();
        }
#endif
        if (IsHiddenEntry(name))
        {
            continue;
        }
        bool isDir = name[0] == '/';
        const char* clean = CleanName(name);
        if (!isDir && !ota_sd_has_etu_extension(clean))
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

    /* Hitting a bound is not sufficient to claim truncation. Probe once so
     * an exactly full directory does not show a false warning. */
    bool moreEntries = false;
    if (rowCount >= ROW_MAX || scanCount >= SCAN_MAX)
    {
        char probe[LV_FS_MAX_FN_LENGTH];
        if (lv_fs_dir_read(&dir, probe) == LV_FS_RES_OK &&
            probe[0] != '\0')
        {
            moreEntries = true;
        }
    }
    lv_fs_dir_close(&dir);

    /* SetBrowserMessage is last-write-wins. Truncation must beat TXT_EMPTY,
     * while an unavailable device remains the highest-priority message. */
    if (moreEntries)
    {
        SetBrowserMessage(TXT_SCAN_LIMIT, "");
    }
    else if (rowCount == 0u || (rowCount == 1u && rows[0].isUp))
    {
        SetBrowserMessage(pathTooLong ? TXT_PATH_LONG : TXT_EMPTY, "");
    }
    else if (pathTooLong)
    {
        SetBrowserMessage(TXT_PATH_LONG, "");
    }

    if (!deviceReady)
    {
        SetBrowserMessage(TXT_FILE_INVALID, updater.LastError());
    }
}

void FirmwareUpdate::AddRow(const char* name, const char* path,
                            bool isDir, bool isUp)
{
    if (rowCount >= ROW_MAX || name == nullptr || list == nullptr)
    {
        return;
    }
    Row_t* item = &rows[rowCount];
    strncpy(item->name, name, sizeof(item->name));
    item->name[sizeof(item->name) - 1u] = '\0';
    if (path != nullptr)
    {
        strncpy(item->path, path, sizeof(item->path));
        item->path[sizeof(item->path) - 1u] = '\0';
    }
    item->isDir = isDir;
    item->isUp = isUp;

    const char* iconSrc = isUp ? LV_SYMBOL_UP
                               : (isDir ? LV_SYMBOL_DIRECTORY
                                        : LV_SYMBOL_FILE);
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

    if (lv_obj_get_child_cnt(row) > 0u)
    {
        lv_obj_t* icon = lv_obj_get_child(row, 0);
        lv_obj_add_style(icon, &iconStyle, 0);
        lv_obj_set_style_text_color(
            icon, lv_color_hex(isDir ? 0x20e8f0 : 0x53f04b), 0);
        lv_obj_align(icon, LV_ALIGN_LEFT_MID, 13, 0);
    }
    if (lv_obj_get_child_cnt(row) > 1u)
    {
        lv_obj_t* label = lv_obj_get_child(row, 1);
        lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
        lv_obj_set_width(label, LIST_W - 76);
        lv_obj_set_style_text_color(label, lv_color_white(), 0);
        lv_obj_set_style_text_font(label, ResourcePool::GetFont("cn_16"), 0);
        lv_obj_align(label, LV_ALIGN_LEFT_MID, 42, 0);
    }
    item->row = row;
    ++rowCount;
}

void FirmwareUpdate::RequestEnterPath(const char* path)
{
    if (path == nullptr || path[0] == '\0' ||
        strlen(path) >= sizeof(pendingPath))
    {
        return;
    }
    strcpy(pendingPath, path);
    pendingGoUp = false;
    pendingBack = false;
    if (!pendingAsync)
    {
        pendingAsync = true;
        lv_async_call(onAsyncAction, this);
    }
}

void FirmwareUpdate::RequestGoUp()
{
    pendingPath[0] = '\0';
    pendingGoUp = true;
    pendingBack = false;
    if (!pendingAsync)
    {
        pendingAsync = true;
        lv_async_call(onAsyncAction, this);
    }
}

void FirmwareUpdate::RequestBack()
{
    pendingPath[0] = '\0';
    pendingGoUp = false;
    pendingBack = true;
    if (!pendingAsync)
    {
        pendingAsync = true;
        lv_async_call(onAsyncAction, this);
    }
}

void FirmwareUpdate::RunPendingAction()
{
    pendingAsync = false;
    if (pendingBack)
    {
        pendingBack = false;
        ReleaseUI();
        _Manager->Pop();
        return;
    }
    if (pendingGoUp)
    {
        pendingGoUp = false;
        GoUp();
        return;
    }
    if (pendingPath[0] != '\0')
    {
        char path[NAV_PATH_MAX];
        strcpy(path, pendingPath);
        pendingPath[0] = '\0';
        EnterPath(path);
    }
}

void FirmwareUpdate::EnterPath(const char* path)
{
    if (path == nullptr || path[0] == '\0' ||
        strlen(path) >= sizeof(currentPath))
    {
        SetBrowserMessage(TXT_PATH_LONG, "");
        return;
    }
    strcpy(currentPath, path);
    LoadFiles();
    RefreshGroup();
}

void FirmwareUpdate::GoUp()
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

void FirmwareUpdate::SelectRow(uint8_t index)
{
    if (index >= rowCount || mode != MODE_BROWSER)
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
    if (!deviceReady ||
        updater.Inspect(rows[index].path, &selectedInfo) != OTA_SD_OK)
    {
        SetBrowserMessage(TXT_FILE_INVALID, updater.LastError());
        return;
    }
    ShowConfirm(rows[index]);
}

void FirmwareUpdate::ShowConfirm(const Row_t& row)
{
    if (confirmPanel == nullptr)
    {
        CreateConfirmUI();
    }

    char currentVersion[20];
    char targetVersion[20];

    strncpy(selectedPath, row.path, sizeof(selectedPath));
    selectedPath[sizeof(selectedPath) - 1u] = '\0';
    strncpy(selectedName, row.name, sizeof(selectedName));
    selectedName[sizeof(selectedName) - 1u] = '\0';
    OtaUpdate::Session::FormatVersion(updater.CurrentVersionCode(),
                                      currentVersion,
                                      sizeof(currentVersion));
    OtaUpdate::Session::FormatVersion(selectedInfo.target_vcode,
                                      targetVersion,
                                      sizeof(targetVersion));
    lv_label_set_text(confirmNameLabel, selectedName);
    lv_label_set_text(confirmKindLabel,
                      selectedInfo.kind == OTA_SD_KIND_PATCH
                          ? "PATCH" : "FULL");
    lv_label_set_text(currentVersionLabel, currentVersion);
    lv_label_set_text(targetVersionLabel, targetVersion);
    lv_obj_add_flag(pathLabel, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(backButton, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(confirmPanel);
    mode = MODE_CONFIRM;
    RefreshGroup();
}

void FirmwareUpdate::HideConfirm()
{
    lv_obj_add_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(pathLabel, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(backButton, LV_OBJ_FLAG_HIDDEN);
    mode = MODE_BROWSER;
    RefreshGroup();
}

void FirmwareUpdate::StartImport()
{
    if (updater.Begin(selectedPath) != OTA_SD_OK)
    {
        lv_obj_add_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(pathLabel, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(backButton, LV_OBJ_FLAG_HIDDEN);
        mode = MODE_BROWSER;
        SetBrowserMessage(TXT_FILE_INVALID, updater.LastError());
        RefreshGroup();
        return;
    }

    if (workPanel == nullptr)
    {
        CreateWorkUI();
    }

    applyPending = false;
    stagePending = false;
    resultSuccess = false;
    lv_obj_add_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(backButton, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(workPanel, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(resultButton, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(workStatusLabel, TXT_IMPORTING);
    lv_label_set_text(workNameLabel, selectedName);
    lv_label_set_text(workKindLabel,
                      selectedInfo.kind == OTA_SD_KIND_PATCH
                          ? "PATCH" : "FULL");
    lv_label_set_text(workDetailLabel, "VERIFY + STAGING");
    lv_label_set_text(progressLabel, "0");
    lv_bar_set_value(progressBar, 0, LV_ANIM_OFF);
    lv_obj_move_foreground(workPanel);
    mode = MODE_WORKING;
    RefreshGroup();
    if (workTimer != nullptr)
    {
        lv_timer_del(workTimer);
    }
    workTimer = lv_timer_create(onWorkTimer, 12, this);
}

void FirmwareUpdate::RunWorkStep()
{
    if (mode != MODE_WORKING)
    {
        return;
    }
    if (applyPending)
    {
        applyPending = false;
        /* P2-5：candidate 合成校验成功后进入 backup 自拷 + STAGED 提交，
         * 不再把 “candidate ready” 当作整项成功。 */
        if (updater.Apply())
        {
            lv_bar_set_value(progressBar, 96, LV_ANIM_OFF);
            lv_label_set_text(progressLabel, "96");
            lv_label_set_text(workDetailLabel, "BACKUP + STAGED");
            stagePending = true;
        }
        else
        {
            FinishImport(false);
        }
        return;
    }
    if (stagePending)
    {
        stagePending = false;
        FinishImport(updater.Stage() == OTA_SD_OK);
        return;
    }

    ota_sd_result_t result = updater.Step(WORK_STEP_BYTES);
    uint8_t progress = updater.ProgressPercent();
    char text[12];
    lv_bar_set_value(progressBar, progress, LV_ANIM_OFF);
    snprintf(text, sizeof(text), "%u", (unsigned)progress);
    lv_label_set_text(progressLabel, text);

    if (result == OTA_SD_STAGED)
    {
        lv_bar_set_value(progressBar, 95, LV_ANIM_OFF);
        lv_label_set_text(progressLabel, "95");
        lv_label_set_text(workDetailLabel, "CANDIDATE VERIFY");
        applyPending = true;
    }
    else if (result < 0)
    {
        FinishImport(false);
    }
}

void FirmwareUpdate::FinishImport(bool success)
{
    resultSuccess = success;
    mode = MODE_RESULT;
    if (workTimer != nullptr)
    {
        lv_timer_del(workTimer);
        workTimer = nullptr;
    }
    if (success)
    {
        /* STAGED 已原子提交且读回通过，才允许显示成功并提示重启 */
        lv_label_set_text(workStatusLabel, TXT_STAGED_READY);
        lv_obj_set_style_text_color(workStatusLabel,
                                    lv_color_hex(0x52f58a), 0);
        lv_bar_set_value(progressBar, 100, LV_ANIM_OFF);
        lv_label_set_text(progressLabel, "100");
        lv_label_set_text(workDetailLabel, "STAGED COMMIT OK");
    }
    else
    {
        lv_label_set_text(workStatusLabel, TXT_FAILED);
        lv_obj_set_style_text_color(workStatusLabel,
                                    lv_color_hex(0xff6b57), 0);
        lv_label_set_text(workDetailLabel, updater.LastError());
    }
    lv_obj_clear_flag(resultButton, LV_OBJ_FLAG_HIDDEN);
    RefreshGroup();
}

bool FirmwareUpdate::IsFocusTarget(lv_obj_t* obj)
{
    if (obj == nullptr)
    {
        return false;
    }
    if (obj == backButton || obj == cancelButton || obj == startButton ||
        obj == resultButton)
    {
        return true;
    }
    for (uint8_t i = 0u; i < rowCount; ++i)
    {
        if (obj == rows[i].row)
        {
            return true;
        }
    }
    return false;
}

void FirmwareUpdate::MoveFocusHaloTo(lv_obj_t* obj, bool anim)
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

void FirmwareUpdate::Back()
{
    if (mode == MODE_CONFIRM)
    {
        HideConfirm();
        return;
    }
    if (mode == MODE_WORKING)
    {
        return;
    }
    RequestBack();
}

void FirmwareUpdate::ReleaseUI()
{
    ClearGroup();
    if (workTimer != nullptr)
    {
        lv_timer_del(workTimer);
        workTimer = nullptr;
    }
    pendingGoUp = false;
    pendingBack = false;
    pendingAsync = false;
    pendingPath[0] = '\0';
    if (_root != nullptr)
    {
        lv_obj_clean(_root);
    }
    titleLabel = nullptr;
    pathLabel = nullptr;
    msgLabel = nullptr;
    detailLabel = nullptr;
    backButton = nullptr;
    focusHalo = nullptr;
    list = nullptr;
    confirmPanel = nullptr;
    confirmNameLabel = nullptr;
    confirmKindLabel = nullptr;
    currentVersionLabel = nullptr;
    targetVersionLabel = nullptr;
    cancelButton = nullptr;
    startButton = nullptr;
    workPanel = nullptr;
    workStatusLabel = nullptr;
    workNameLabel = nullptr;
    workKindLabel = nullptr;
    progressBar = nullptr;
    progressLabel = nullptr;
    workDetailLabel = nullptr;
    resultButton = nullptr;
    rowCount = 0u;
    memset(rows, 0, sizeof(rows));
    mode = MODE_BROWSER;
}

void FirmwareUpdate::RefreshGroup()
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

    lv_obj_t* first = nullptr;
    if (mode == MODE_BROWSER)
    {
        for (uint8_t i = 0u; i < rowCount; ++i)
        {
            if (rows[i].row != nullptr)
            {
                lv_group_add_obj(group, rows[i].row);
                if (first == nullptr)
                {
                    first = rows[i].row;
                }
            }
        }
        lv_group_add_obj(group, backButton);
        if (first == nullptr)
        {
            first = backButton;
        }
    }
    else if (mode == MODE_CONFIRM)
    {
        lv_group_add_obj(group, cancelButton);
        lv_group_add_obj(group, startButton);
        first = cancelButton;
    }
    else if (mode == MODE_RESULT)
    {
        lv_group_add_obj(group, resultButton);
        first = resultButton;
    }

    if (first != nullptr)
    {
        MoveFocusHaloTo(first, false);
        lv_group_focus_obj(first);
    }
    else if (focusHalo != nullptr)
    {
        lv_obj_add_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);
    }
}

void FirmwareUpdate::ClearGroup()
{
    lv_group_t* group = lv_group_get_default();
    if (group != nullptr)
    {
        for (uint8_t i = 0u; i < rowCount; ++i)
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
        lv_obj_t* owned[] = {
            backButton, cancelButton, startButton, resultButton
        };
        for (uint8_t i = 0u;
             i < sizeof(owned) / sizeof(owned[0]); ++i)
        {
            if (owned[i] != nullptr)
            {
                if (lv_obj_get_group(owned[i]) == group)
                {
                    lv_group_remove_obj(owned[i]);
                }
                ClearFocusState(owned[i]);
            }
        }
    }
    if (focusHalo != nullptr)
    {
        lv_anim_del(focusHalo, FocusHaloYAnimCb);
        lv_obj_add_flag(focusHalo, LV_OBJ_FLAG_HIDDEN);
    }
}

void FirmwareUpdate::SetBrowserMessage(const char* message,
                                       const char* detail)
{
    if (list != nullptr)
    {
        lv_obj_set_height(
            list,
            message != nullptr && message[0] != '\0'
                ? LIST_H_MESSAGE : LIST_H);
    }
    if (msgLabel != nullptr)
    {
        lv_label_set_text(msgLabel, message != nullptr ? message : "");
    }
    if (detailLabel != nullptr)
    {
        lv_label_set_text(detailLabel, detail != nullptr ? detail : "");
    }
}

void FirmwareUpdate::onEvent(lv_event_t* event)
{
    FirmwareUpdate* instance =
        (FirmwareUpdate*)lv_event_get_user_data(event);
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
    if (obj == instance->_root &&
        (code == LV_EVENT_LEAVE || code == LV_EVENT_GESTURE))
    {
        if (instance->mode == MODE_BROWSER)
        {
            instance->RequestGoUp();
        }
        else
        {
            instance->Back();
        }
        return;
    }
    if (code != LV_EVENT_SHORT_CLICKED)
    {
        return;
    }
    if (obj == instance->backButton || obj == instance->cancelButton ||
        obj == instance->resultButton)
    {
        instance->Back();
        return;
    }
    if (obj == instance->startButton)
    {
        instance->StartImport();
        return;
    }
    for (uint8_t i = 0u; i < instance->rowCount; ++i)
    {
        if (obj == instance->rows[i].row)
        {
            instance->SelectRow(i);
            return;
        }
    }
}

void FirmwareUpdate::onAsyncAction(void* userData)
{
    FirmwareUpdate* instance = (FirmwareUpdate*)userData;
    if (instance != nullptr)
    {
        instance->RunPendingAction();
    }
}

void FirmwareUpdate::onWorkTimer(lv_timer_t* timer)
{
    FirmwareUpdate* instance =
        timer != nullptr ? (FirmwareUpdate*)timer->user_data : nullptr;
    if (instance != nullptr)
    {
        instance->RunWorkStep();
    }
}
