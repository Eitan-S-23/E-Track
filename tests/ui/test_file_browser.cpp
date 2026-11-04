#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "Pages/Page.h"
#include "Common/DataProc/DataProc.h"
#include "Utils/OtaUpdate/OtaUpdate.h"
#define private public
#include "Pages/FirmwareUpdate/FirmwareUpdate.h"
#include "Pages/RouteSelect/RouteSelect.h"
#undef private

LV_FONT_DECLARE(font_cn_16);
LV_FONT_DECLARE(font_bahnschrift_13);
LV_FONT_DECLARE(font_bahnschrift_17);
LV_FONT_DECLARE(font_bahnschrift_24);
LV_FONT_DECLARE(font_iconfont_20);

static uint32_t ticks;
extern "C" uint32_t custom_tick_get(void) { return ticks; }
static std::string inspected;
static std::string begun;
static int begins;
static uint32_t currentVcode = 30313;
static int pops;
static std::string routeSelected;
static std::vector<std::string> entries;
static size_t entryIndex;
static lv_indev_state_t encoderState = LV_INDEV_STATE_RELEASED;
static int16_t encoderDiff;
static void readEncoder(lv_indev_drv_t*, lv_indev_data_t* data)
{
    data->state = encoderState;
    data->enc_diff = encoderDiff;
    data->key = LV_KEY_ENTER;
    encoderDiff = 0;
}

/* UI-only service doubles: record identity and never read/write a package. */
namespace OtaUpdate {
Session::Session() {}
Session::~Session() {}
bool Session::InitializeDevice() { return true; }
ota_sd_result_t Session::Inspect(const char* path, ota_sd_package_info_t* out)
{
    inspected = path;
    memset(out, 0, sizeof(*out));
    out->kind = strstr(path, "patch") ? OTA_SD_KIND_PATCH : OTA_SD_KIND_FULL;
    out->target_vcode = 30316;
    return OTA_SD_OK;
}
ota_sd_result_t Session::Begin(const char* path) { begun = path; ++begins; return OTA_SD_OK; }
ota_sd_result_t Session::Step(uint32_t) { abort(); }
bool Session::Apply() { abort(); }
ota_sd_result_t Session::Stage() { abort(); }
void Session::Close() {}
uint32_t Session::CurrentVersionCode() const { return currentVcode; }
uint8_t Session::ProgressPercent() const { return 0; }
const char* Session::LastError() const { return "UI double"; }
}
extern "C" int ota_sd_has_etu_extension(const char* name)
{ size_t n = strlen(name); return n >= 4 && strcmp(name + n - 4, ".etu") == 0; }
namespace ResourcePool {
lv_font_t* GetFont(const char* name)
{
    if (!strcmp(name, "bahnschrift_13")) return const_cast<lv_font_t*>(&font_bahnschrift_13);
    if (!strcmp(name, "bahnschrift_17")) return const_cast<lv_font_t*>(&font_bahnschrift_17);
    if (!strcmp(name, "bahnschrift_24")) return const_cast<lv_font_t*>(&font_bahnschrift_24);
    if (!strcmp(name, "iconfont_20")) return const_cast<lv_font_t*>(&font_iconfont_20);
    return const_cast<lv_font_t*>(&font_cn_16);
}
}
PageManager::PageManager(PageFactory*) {}
PageManager::~PageManager() {}
bool PageManager::Pop() { ++pops; return true; }
bool PageManager::Replace(const char*, const PageBase::Stash_t*) { return true; }
namespace DataProc { DataCenter* Center() { return nullptr; } }
Account::Account(const char*, DataCenter*, uint32_t, void*) {}
Account::~Account() {}
Account* Account::Subscribe(const char*) { return nullptr; }
int Account::Notify(const char*, const void* data, uint32_t size)
{
    if (size == sizeof(DataProc::Navigation_CmdInfo_t))
        routeSelected = static_cast<const DataProc::Navigation_CmdInfo_t*>(data)->param.selectRoute.gpxPath;
    return 0;
}

static void* dirOpen(lv_fs_drv_t*, const char*) { entryIndex = 0; return &entryIndex; }
static lv_fs_res_t dirRead(lv_fs_drv_t*, void*, char* name)
{
    strcpy(name, entryIndex < entries.size() ? entries[entryIndex++].c_str() : "");
    return LV_FS_RES_OK;
}
static lv_fs_res_t dirClose(lv_fs_drv_t*, void*) { return LV_FS_RES_OK; }
static lv_color_t drawBuffer[240 * 20];
static unsigned char pixels[240 * 320 * 3];
static void flush(lv_disp_drv_t* drv, const lv_area_t* area, lv_color_t* colors)
{
    for (int y = area->y1; y <= area->y2; ++y)
        for (int x = area->x1; x <= area->x2; ++x) {
            lv_color32_t c; c.full = lv_color_to32(*colors++);
            unsigned char* p = pixels + (y * 240 + x) * 3;
            p[0] = c.ch.blue; p[1] = c.ch.green; p[2] = c.ch.red;
        }
    lv_disp_flush_ready(drv);
}
static void step(unsigned ms)
{
    for (unsigned i = 0; i < ms; i += 20) { ticks += 20; lv_timer_handler(); }
    lv_obj_update_layout(lv_scr_act());
}
static void clickEncoder()
{
    encoderState = LV_INDEV_STATE_PRESSED; step(40);
    encoderState = LV_INDEV_STATE_RELEASED; step(40);
}
static void shot(const std::string& dir, const char* name)
{
    lv_refr_now(nullptr);
    unsigned char header[54] = { 'B', 'M' };
    uint32_t size = 54 + sizeof(pixels), offset = 54, dib = 40, w = 240, h = 320;
    memcpy(header + 2, &size, 4); memcpy(header + 10, &offset, 4);
    memcpy(header + 14, &dib, 4); memcpy(header + 18, &w, 4); memcpy(header + 22, &h, 4);
    header[26] = 1; header[28] = 24;
    FILE* f = fopen((dir + "/" + name + ".bmp").c_str(), "wb");
    if (!f) abort();
    fwrite(header, 1, sizeof(header), f);
    for (int y = 319; y >= 0; --y) fwrite(pixels + y * 240 * 3, 1, 240 * 3, f);
    fclose(f);
}
static int checks;
#define CHECK(expr) do { ++checks; if (!(expr)) { fprintf(stderr, "FAIL line=%d %s\n", __LINE__, #expr); exit(1); } } while (0)
static lv_obj_t* nameLabel(lv_obj_t* row) { return lv_obj_get_child(row, 1); }
static void geometry(lv_obj_t* row)
{
    lv_obj_t* label = nameLabel(row);
    lv_area_t r, l, icon;
    lv_obj_get_coords(row, &r); lv_obj_get_coords(label, &l);
    lv_obj_get_coords(lv_obj_get_child(row, 0), &icon);
    CHECK(lv_obj_get_height(row) == 38);
    CHECK(lv_obj_get_height(label) == lv_font_get_line_height(&font_cn_16));
    CHECK(l.y1 >= r.y1 && l.y2 <= r.y2);
    CHECK(l.x1 > icon.x2 && l.x2 <= r.x2);
}

static const char* full = "e-track-at32f435-v3.3.16-full.etu";
static const char* patch = "e-track-at32f435-v3.3.13-to-v3.3.16-patch.etu";
static std::string probeName()
{ return "aaaaaaaaaaaaaaa-aaaaaaaaaaaaaaa-aaaaaaaaaaaaaaa-aaaaaaafull.etu"; }
static std::vector<std::string> names()
{
    return {"..", "P51", full, patch, "a.etu",
            std::string(55, 'a') + "full.etu", std::string(55, 'a') + "diff.etu",
            "\xE6\x96\x87\xE4\xBB\xB6\xE7\x89\x88\xE6\x9C\xAC\xE6\x96\x87\xE4\xBB\xB6\xE7\x89\x88\xE6\x9C\xAC\xE6\x96\x87\xE4\xBB\xB6\xE7\x89\x88\xE6\x9C\xAC\xE6\x96\x87\xE4\xBB\xB6\xE7\x89\x88\xE6\x9C\xAC" "-full.etu",
            std::string(60, 'D')};
}
template<typename T> static void addNames(T& page)
{
    auto ns = names();
    for (size_t i = 0; i < ns.size(); ++i) {
        CHECK(ns[i].size() < LV_FS_MAX_FN_LENGTH);
        std::string path = "/P51/" + ns[i];
        page.AddRow(ns[i].c_str(), path.c_str(), i < 2 || i == 8, i == 0);
    }
    step(300);
}
template<typename T> static void listChecks(T& page, const std::string& output, const char* shotName)
{
    auto ns = names();
    page.RefreshGroup(); step(300);
    for (int cycle = 0; cycle < 3; ++cycle)
        for (size_t i = 0; i < ns.size(); ++i) {
            lv_obj_t* row = page.rows[i].row;
            lv_group_focus_obj(row); step(40);
            for (size_t other = 0; other < ns.size(); ++other)
                if (other != i) {
                    CHECK(lv_label_get_long_mode(nameLabel(page.rows[other].row)) == LV_LABEL_LONG_DOT);
                    CHECK(lv_anim_get(nameLabel(page.rows[other].row), nullptr) == nullptr);
                }
            geometry(row);
            lv_obj_t* label = nameLabel(row);
            CHECK(!strcmp(lv_label_get_text(label), ns[i].c_str()));
            CHECK(!strcmp(page.rows[i].path, ("/P51/" + ns[i]).c_str()));
            lv_point_t textSize;
            lv_txt_get_size(&textSize, ns[i].c_str(), &font_cn_16, 0, 0, LV_COORD_MAX, LV_TEXT_FLAG_EXPAND);
            int minOffset = 0;
            if (cycle == 0 && i == 3) shot(output, (std::string(shotName) + "-start").c_str());
            bool suffixShot = false;
            for (unsigned t = 0; t < 24000; t += 100) {
                step(100);
                minOffset = LV_MIN(minOffset, ((lv_label_t*)label)->offset.x);
                CHECK(((lv_label_t*)label)->offset.y == 0);
                if (cycle == 0 && i == 3 && !suffixShot &&
                    ((lv_label_t*)label)->offset.x <= lv_obj_get_content_width(label) - textSize.x + 1) {
                    shot(output, (std::string(shotName) + "-suffix").c_str()); suffixShot = true;
                }
            }
            if (textSize.x > lv_obj_get_content_width(label)) {
                CHECK(minOffset <= lv_obj_get_content_width(label) - textSize.x + 1);
                CHECK(lv_anim_get(label, nullptr) != nullptr);
            } else {
                CHECK(minOffset == 0);
                CHECK(lv_anim_get(label, nullptr) == nullptr);
            }
            if (cycle == 0 && i == 3) shot(output, shotName);
            lv_group_focus_obj(page.backButton); step(300);
            geometry(row);
            CHECK(lv_label_get_long_mode(label) == LV_LABEL_LONG_DOT);
            CHECK(lv_anim_get(label, nullptr) == nullptr);
            CHECK(((lv_label_t*)label)->offset.x == 0);
            if (cycle == 0)
                printf("LIST page=%s case=%u bytes=%u label_h=%d row_h=%d min_x=%d text_w=%d viewport_w=%d path=%s\n",
                       shotName, unsigned(i), unsigned(ns[i].size()), lv_obj_get_height(label),
                       lv_obj_get_height(row), minOffset, textSize.x, lv_obj_get_content_width(label), page.rows[i].path);
        }
    page.onViewWillDisappear(); step(300);
    for (unsigned i = 0; i < page.rowCount; ++i)
        CHECK(lv_anim_get(nameLabel(page.rows[i].row), nullptr) == nullptr);
    page.onViewWillAppear(); step(300);
    std::vector<lv_obj_t*> oldLabels;
    for (unsigned i = 0; i < page.rowCount; ++i) oldLabels.push_back(nameLabel(page.rows[i].row));
    page.ClearRows(); step(300);
    CHECK(page.rowCount == 0);
    for (auto label : oldLabels) CHECK(lv_anim_get(label, nullptr) == nullptr);
    addNames(page);
    page.RefreshGroup(); step(300);
}

static void versionGeometry(lv_obj_t* label, lv_obj_t* caption)
{
    lv_area_t v, c, p;
    lv_obj_get_coords(label, &v); lv_obj_get_coords(caption, &c);
    lv_obj_get_content_coords(lv_obj_get_parent(label), &p);
    CHECK(v.x1 > c.x2 && v.x2 <= p.x2 && v.y2 <= p.y2);
    const lv_font_t* font = lv_obj_get_style_text_font(label, 0);
    const char* text = lv_label_get_text(label);
    lv_point_t size;
    lv_txt_get_size(&size, text, font, 0, 0, LV_COORD_MAX, LV_TEXT_FLAG_EXPAND);
    CHECK(size.x <= lv_obj_get_content_width(label));
    CHECK(lv_obj_get_height(label) == lv_font_get_line_height(font));
    for (const char* ch = text; *ch; ++ch) {
        lv_font_glyph_dsc_t glyph;
        CHECK(lv_font_get_glyph_dsc(font, &glyph, *ch, ch[1]));
        CHECK(!glyph.is_placeholder);
    }
}

static void workGeometry(Page::FirmwareUpdate& page, bool result)
{
    lv_area_t name, bar, percent, status, kind, detail, button, panel;
    lv_obj_get_coords(page.workNameLabel, &name); lv_obj_get_coords(page.progressBar, &bar);
    lv_obj_get_coords(page.progressLabel, &percent); lv_obj_get_coords(page.workStatusLabel, &status);
    lv_obj_get_coords(page.workKindLabel, &kind); lv_obj_get_coords(page.workDetailLabel, &detail);
    lv_obj_get_coords(page.resultButton, &button); lv_obj_get_content_coords(page.workPanel, &panel);
    CHECK(status.y2 < name.y1 && name.y2 < bar.y1 && bar.y2 < percent.y1);
    CHECK(percent.y2 < detail.y1 && detail.y2 < button.y1);
    CHECK(status.x2 < kind.x1);
    CHECK(name.x1 >= panel.x1 && name.x2 <= panel.x2 && button.y2 <= panel.y2);
    CHECK(lv_obj_get_height(page.workNameLabel) == lv_font_get_line_height(&font_cn_16));
    CHECK(lv_label_get_long_mode(page.workNameLabel) == LV_LABEL_LONG_SCROLL);
    CHECK(lv_obj_has_flag(page.resultButton, LV_OBJ_FLAG_HIDDEN) != result);
    CHECK(!lv_obj_has_flag(page.workPanel, LV_OBJ_FLAG_HIDDEN));
}

static void followupChecks(PageManager& manager, const std::string& output)
{
    Page::FirmwareUpdate page; page._Manager = &manager;
    page._root = lv_obj_create(lv_scr_act()); page.CreateUI(); page.deviceReady = true;
    addNames(page);
    const std::string probe = probeName();
    page.AddRow(probe.c_str(), ("/P51/" + probe).c_str(), false, false);
    const uint32_t versions[] = {0u, 30313u, 30316u, 9999999u, 4294959999u, UINT32_MAX};
    for (uint32_t version : versions) {
        currentVcode = version; page.selectedInfo.target_vcode = version;
        page.ShowConfirm(page.rows[2]); step(300);
        char expected[20] = "v";
        OtaUpdate::Session::FormatVersion(version, expected + 1, sizeof(expected) - 1);
        CHECK(!strcmp(lv_label_get_text(page.currentVersionLabel), expected));
        CHECK(!strcmp(lv_label_get_text(page.targetVersionLabel), expected));
        versionGeometry(page.currentVersionLabel, lv_obj_get_child(page.confirmPanel, 3));
        versionGeometry(page.targetVersionLabel, lv_obj_get_child(page.confirmPanel, 5));
        printf("VERSION code=%u text=%s font_line_h=%d width=%d\n", unsigned(version), expected,
               lv_obj_get_height(page.currentVersionLabel), lv_obj_get_width(page.currentVersionLabel));
        if (version == 30316u) shot(output, "version-normal");
        if (version == UINT32_MAX) shot(output, "version-max");
        page.HideConfirm();
    }
    currentVcode = 30313;
    const unsigned indices[] = {2, 3, 4, 5, 6, 7, 9};
    for (unsigned index : indices) {
        page.mode = Page::FirmwareUpdate::MODE_BROWSER;
        page.SelectRow(index);
        const std::string name = page.rows[index].name, path = page.rows[index].path;
        const int before = begins;
        page.StartImport();
        // Never advance LVGL with the service work timer alive.
        lv_timer_del(page.workTimer); page.workTimer = nullptr;
        lv_obj_update_layout(page.workPanel);
        CHECK(begins == before + 1 && begun == path && inspected == path);
        CHECK(!strcmp(lv_label_get_text(page.workNameLabel), name.c_str()));
        CHECK(((lv_label_t*)page.workNameLabel)->offset.x == 0);
        CHECK(lv_label_get_long_mode(page.workNameLabel) == LV_LABEL_LONG_SCROLL);
        step(300); workGeometry(page, false);
        CHECK(!strcmp(lv_label_get_text(page.workKindLabel), index == 3 ? "PATCH" : "FULL"));
        CHECK(!strcmp(lv_label_get_text(page.progressLabel), "0"));
        CHECK(lv_bar_get_value(page.progressBar) == 0);
        CHECK(lv_obj_get_style_text_color(page.workStatusLabel, 0).full == lv_color_hex(0x20e8f0).full);
        if (index == 9) {
            lv_obj_t* label = page.workNameLabel;
            lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
            lv_label_set_long_mode(label, LV_LABEL_LONG_SCROLL);
            CHECK(((lv_label_t*)label)->offset.x == 0);
            shot(output, "work-probe-start");
        }
        if (index == 4) shot(output, "work-short");
        lv_point_t size;
        lv_txt_get_size(&size, name.c_str(), &font_cn_16, 0, 0, LV_COORD_MAX, LV_TEXT_FLAG_EXPAND);
        int minX = 0;
        bool captured = false;
        for (unsigned t = 0; t < 24000; t += 100) {
            step(100); workGeometry(page, false);
            lv_label_t* label = (lv_label_t*)page.workNameLabel;
            minX = LV_MIN(minX, label->offset.x);
            CHECK(label->offset.y == 0);
            if (!captured && size.x > lv_obj_get_content_width(page.workNameLabel) &&
                label->offset.x <= lv_obj_get_content_width(page.workNameLabel) - size.x + 1) {
                if (index == 9) shot(output, "work-probe-suffix");
                if (index == 3) shot(output, "work-patch-suffix");
                if (index == 7) shot(output, "work-cjk-suffix");
                captured = true;
            }
        }
        if (size.x > lv_obj_get_content_width(page.workNameLabel)) {
            CHECK(minX <= lv_obj_get_content_width(page.workNameLabel) - size.x + 1);
            CHECK(lv_anim_get(page.workNameLabel, nullptr) != nullptr);
        } else {
            CHECK(minX == 0 && lv_anim_get(page.workNameLabel, nullptr) == nullptr);
        }
        printf("WORK case=%u bytes=%u name_h=%d min_x=%d text_w=%d path=%s\n", index,
               unsigned(name.size()), lv_obj_get_height(page.workNameLabel), minX, size.x, begun.c_str());
        page.FinishImport(true); step(300); workGeometry(page, true);
        CHECK(!strcmp(lv_label_get_text(page.progressLabel), "100"));
        CHECK(lv_bar_get_value(page.progressBar) == 100);
        if (index == 3) shot(output, "result-patch-success");
        // Project a representative two-digit failure progress without a work Step.
        lv_label_set_text(page.progressLabel, "95"); lv_bar_set_value(page.progressBar, 95, LV_ANIM_OFF);
        page.FinishImport(false); step(300); workGeometry(page, true);
        CHECK(!strcmp(lv_label_get_text(page.progressLabel), "95"));
        CHECK(lv_bar_get_value(page.progressBar) == 95);
        CHECK(!strcmp(lv_label_get_text(page.workDetailLabel), "UI double"));
        if (index == 9) shot(output, "result-probe-failure");
        page.onViewWillDisappear(); step(300);
        CHECK(lv_anim_get(page.workNameLabel, nullptr) == nullptr);
        CHECK(lv_anim_get(page.workStatusLabel, nullptr) == nullptr);
        page.onViewWillAppear(); step(300);
        CHECK(!strcmp(lv_label_get_text(page.workNameLabel), name.c_str()));
        CHECK(lv_label_get_long_mode(page.workNameLabel) == LV_LABEL_LONG_SCROLL);
    }
    lv_obj_t* oldName = page.workNameLabel;
    page.ReleaseUI(); step(300);
    CHECK(lv_anim_get(oldName, nullptr) == nullptr);
    page.CreateUI(); page.deviceReady = true; addNames(page);
    page.SelectRow(4); page.StartImport(); lv_timer_del(page.workTimer); page.workTimer = nullptr;
    step(300); workGeometry(page, false);
    CHECK(!strcmp(lv_label_get_text(page.workNameLabel), "a.etu"));
    CHECK(lv_anim_get(page.workNameLabel, nullptr) == nullptr);
    page.onViewUnload(); lv_obj_del(page._root); step(300);
    CHECK(lv_anim_count_running() == 0);
}

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    std::string output = argv[1];
    lv_init();
    lv_disp_draw_buf_t db; lv_disp_draw_buf_init(&db, drawBuffer, nullptr, 240 * 20);
    lv_disp_drv_t drv; lv_disp_drv_init(&drv); drv.hor_res = 240; drv.ver_res = 320;
    drv.draw_buf = &db; drv.flush_cb = flush; lv_disp_drv_register(&drv);
    lv_group_t* group = lv_group_create(); lv_group_set_default(group);
    lv_indev_drv_t encoder; lv_indev_drv_init(&encoder);
    encoder.type = LV_INDEV_TYPE_ENCODER; encoder.read_cb = readEncoder;
    lv_indev_t* input = lv_indev_drv_register(&encoder); lv_indev_set_group(input, group);
    lv_fs_drv_t fs; lv_fs_drv_init(&fs); fs.letter = '/';
    fs.dir_open_cb = dirOpen; fs.dir_read_cb = dirRead; fs.dir_close_cb = dirClose; lv_fs_drv_register(&fs);
    PageManager manager;
    Page::FirmwareUpdate page; page._root = lv_obj_create(lv_scr_act()); page._Manager = &manager;
    page.CreateUI(); page.deviceReady = true; addNames(page);
#if P51_FOLLOWUP_BASELINE
    page.SelectRow(2); step(300);
    printf("PRODUCT_FORMATTER current=%s target=%s\n", lv_label_get_text(page.currentVersionLabel),
           lv_label_get_text(page.targetVersionLabel));
    lv_font_glyph_dsc_t glyph;
    bool found = lv_font_get_glyph_dsc(&font_bahnschrift_24, &glyph, 'v', 0);
    CHECK(!found || glyph.is_placeholder);
    lv_label_set_text(page.currentVersionLabel, "v3.3.13");
    lv_label_set_text(page.targetVersionLabel, "v3.3.16");
    step(300); shot(output, "baseline-version-prefix-control");
    page.HideConfirm();
    const std::string name = probeName(); CHECK(name.size() == 63);
    page.AddRow(name.c_str(), ("/P51/" + name).c_str(), false, false);
    page.SelectRow(page.rowCount - 1); page.StartImport();
    lv_timer_del(page.workTimer); page.workTimer = nullptr;
    CHECK(begun == "/P51/" + name); step(300);
    lv_area_t n, b, s, k;
    lv_obj_get_coords(page.workNameLabel, &n); lv_obj_get_coords(page.progressBar, &b);
    CHECK(n.y1 <= b.y2 && n.y2 >= b.y1);
    printf("BASELINE_WORK name_y=%d..%d bar_y=%d..%d\n", n.y1, n.y2, b.y1, b.y2);
    shot(output, "baseline-work-full-name");
    page.FinishImport(true); step(300);
    lv_obj_get_coords(page.workStatusLabel, &s); lv_obj_get_coords(page.workKindLabel, &k);
    printf("BASELINE_RESULT status_x=%d..%d kind_x=%d..%d\n", s.x1, s.x2, k.x1, k.x2);
    shot(output, "baseline-work-result");
    page.ReleaseUI(); lv_obj_del(page._root); lv_group_del(group);
    printf("P51_FOLLOWUP_BASELINE=PASS checks=%d no_device_operations=1\n", checks);
    return 0;
#endif
#if !P51_FIXED
    for (unsigned i = 2; i < page.rowCount; ++i)
        printf("OLD row=%u row_h=%d label_h=%d font_h=%d name=%s\n", i,
               lv_obj_get_height(page.rows[i].row), lv_obj_get_height(nameLabel(page.rows[i].row)),
               lv_font_get_line_height(&font_cn_16), names()[i].c_str());
    CHECK(lv_obj_get_height(nameLabel(page.rows[2].row)) > lv_font_get_line_height(&font_cn_16));
    CHECK(lv_obj_get_height(nameLabel(page.rows[3].row)) > lv_font_get_line_height(&font_cn_16));
    shot(output, "old-list");
    page.selectedInfo.kind = OTA_SD_KIND_PATCH; page.selectedInfo.target_vcode = 30316;
    page.ShowConfirm(page.rows[3]); step(300); shot(output, "old-confirm-patch");
    page.ReleaseUI();
#else
    listChecks(page, output, "fixed-list-patch-focused");
    lv_group_focus_obj(page.backButton); step(300); shot(output, "fixed-list-unfocused");
    for (unsigned i = 2; i < page.rowCount; ++i) {
        if (page.rows[i].isDir) continue;
        std::string expected = page.rows[i].path;
        int before = begins;
        page.SelectRow(i); step(300);
        CHECK(page.mode == Page::FirmwareUpdate::MODE_CONFIRM);
        CHECK(inspected == expected && expected == page.selectedPath);
        CHECK(!strcmp(page.selectedName, names()[i].c_str()));
        CHECK(!strcmp(lv_label_get_text(page.confirmNameLabel), names()[i].c_str()));
        CHECK(lv_label_get_long_mode(page.confirmNameLabel) == LV_LABEL_LONG_WRAP);
        CHECK(!strcmp(lv_label_get_text(page.confirmKindLabel), i == 3 ? "PATCH" : "FULL"));
        CHECK(!strcmp(lv_label_get_text(page.currentVersionLabel), "v3.3.13"));
        CHECK(!strcmp(lv_label_get_text(page.targetVersionLabel), "v3.3.16"));
        lv_area_t a, b, c, d;
        lv_obj_get_coords(page.confirmNameArea, &a); lv_obj_get_coords(page.currentVersionLabel, &b);
        lv_obj_get_coords(page.targetVersionLabel, &c); lv_obj_get_coords(page.cancelButton, &d);
        CHECK(a.y2 < b.y1 && b.y2 < c.y1 && c.y2 < d.y1);
        CHECK(lv_obj_get_height(page.confirmNameArea) == 56);
        CHECK(!lv_obj_has_flag(page.startButton, LV_OBJ_FLAG_HIDDEN));
        CHECK(lv_group_get_focused(group) == page.cancelButton);
        if (i == 3) shot(output, "fixed-confirm-patch-top");
        if (lv_obj_get_scroll_bottom(page.confirmNameArea) > 0) {
            encoderDiff = 2; step(40);
            CHECK(lv_group_get_focused(group) == page.confirmNameArea);
            clickEncoder();
            CHECK(lv_group_get_editing(group));
            encoderDiff = 25; step(40);
            step(300);
            CHECK(lv_obj_get_scroll_bottom(page.confirmNameArea) == 0);
            CHECK(lv_obj_get_scroll_y(page.confirmNameArea) > 0);
            encoderState = LV_INDEV_STATE_PRESSED; step(600);
            encoderState = LV_INDEV_STATE_RELEASED; step(40);
            CHECK(!lv_group_get_editing(group));
            page.onViewWillDisappear(); page.onViewWillAppear(); step(300);
            CHECK(lv_obj_get_group(page.confirmNameArea) == group);
        }
        if (i == 2) shot(output, "fixed-confirm-full");
        if (i == 3) shot(output, "fixed-confirm-patch");
        if (i == 7) shot(output, "fixed-confirm-cjk-bottom");
        lv_group_focus_obj(page.cancelButton); clickEncoder(); step(300);
        CHECK(page.mode == Page::FirmwareUpdate::MODE_BROWSER && begins == before);
        printf("CONFIRM case=%u bytes=%u path=%s cancel_begin_delta=%d\n", i,
               unsigned(names()[i].size()), expected.c_str(), begins - before);
    }
    page.SelectRow(3); step(300);
    CHECK(lv_obj_get_scroll_y(page.confirmNameArea) == 0);
    lv_event_send(page.startButton, LV_EVENT_SHORT_CLICKED, nullptr);
    CHECK(begins == 1 && begun == std::string("/P51/") + patch);
    page.ReleaseUI(); step(300);
    page.CreateUI(); page.mode = Page::FirmwareUpdate::MODE_BROWSER;
    entries = {full, patch, "/folder"}; page.EnterPath("/P51"); step(300);
    CHECK(page.rowCount == 4 && page.rows[0].isUp);
    geometry(page.rows[1].row); page.GoUp(); step(300);
    CHECK(!strcmp(page.currentPath, "/"));
    page.EnterPath("/P51"); step(300); page.onViewUnload(); step(300);
    CHECK(page.list == nullptr && page.rowCount == 0);
    page.CreateUI(); page.EnterPath("/P51"); step(300);
    page.SelectRow(3); step(300);
    CHECK(!strcmp(page.currentPath, "/P51/folder"));
    page.SelectRow(0); step(300);
    CHECK(!strcmp(page.currentPath, "/P51"));
    page.Back(); step(300);
    CHECK(pops == 1 && page.list == nullptr);
    lv_obj_del(page._root); step(300);
    CHECK(lv_anim_count_running() == 0);
    Page::RouteSelect route; route._root = lv_obj_create(lv_scr_act()); route._Manager = &manager;
    route.CreateUI(); addNames(route);
    listChecks(route, output, "fixed-route-list");
    route.ClearRows();
    route.account = new Account("UI", nullptr);
    route.AddRow("long-route-name-identity.gpx", "/GPX/long-route-name-identity.gpx", false, false);
    route.SelectRow(0);
    CHECK(routeSelected == "/GPX/long-route-name-identity.gpx");
    route.Back(); CHECK(pops == 2);
    route.onViewUnload(); lv_obj_del(route._root); step(300);
    CHECK(lv_anim_count_running() == 0);
    followupChecks(manager, output);
#endif
    printf("P51_UI_%s_SELFTEST=PASS checks=%d begins=%d pops=%d\n", P51_FIXED ? "FIXED" : "OLD_REPRO", checks, begins, pops);
    lv_group_del(group);
    return 0;
}
