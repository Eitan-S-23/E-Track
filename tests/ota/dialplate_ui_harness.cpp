#include "Pages/Dialplate/DialplateView.h"
#include "lv_port/lv_port.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#ifndef DIALPLATE_HW_EFFECTS
#if defined(ARDUINO) && defined(AT32F435RGT7)
#define DIALPLATE_HW_EFFECTS 1
#else
#define DIALPLATE_HW_EFFECTS 0
#endif
#endif

extern "C"
{
LV_FONT_DECLARE(font_bahnschrift_13);
LV_FONT_DECLARE(font_bahnschrift_17);
LV_FONT_DECLARE(font_bahnschrift_24);
LV_FONT_DECLARE(font_bahnschrift_32);
LV_FONT_DECLARE(font_bahnschrift_48);
LV_FONT_DECLARE(font_agencyb_12);
LV_FONT_DECLARE(font_iconfont_16);
LV_FONT_DECLARE(font_iconfont_20);
LV_FONT_DECLARE(font_cn_16);
LV_IMG_DECLARE(img_src_dialplate_skin);
LV_IMG_DECLARE(img_src_gps_arrow_light);
LV_IMG_DECLARE(img_src_battery);
LV_IMG_DECLARE(img_src_bluetooth);
LV_IMG_DECLARE(img_src_satellite);
}

static const int width = 240;
static const int height = 320;
static std::vector<lv_color_t> framebuffer(width * height);
static unsigned rawTransfers = 0;
static unsigned normalCallbacks = 0;

namespace StatusBarProbe
{
struct { lv_obj_t* cont; } ui;
#define STATUS_BAR_HEIGHT 25
static void SetY(void* object, int32_t value)
{
    lv_obj_set_y(static_cast<lv_obj_t*>(object), static_cast<lv_coord_t>(value));
}
#define LV_ANIM_EXEC(property) SetY
#include "statusbar_ui.inc"
#undef LV_ANIM_EXEC

static lv_obj_t* Create()
{
    ui.cont = lv_obj_create(lv_layer_top());
    lv_obj_remove_style_all(ui.cont);
    lv_obj_set_size(ui.cont, width, STATUS_BAR_HEIGHT);
    lv_obj_set_y(ui.cont, -STATUS_BAR_HEIGHT);
    StatusBar_StyleInit(ui.cont);
    StatusBar_Appear(false);
    return ui.cont;
}
}

static void Require(bool condition, const char* message)
{
    if(!condition)
    {
        std::fprintf(stderr, "FAIL: %s\n", message);
        std::exit(1);
    }
}

namespace ResourcePool
{
lv_font_t* GetFont(const char* name)
{
#define FONT_ENTRY(key, value) if(std::strcmp(name, key) == 0) return const_cast<lv_font_t*>(&value)
    FONT_ENTRY("bahnschrift_13", font_bahnschrift_13);
    FONT_ENTRY("bahnschrift_17", font_bahnschrift_17);
    FONT_ENTRY("bahnschrift_24", font_bahnschrift_24);
    FONT_ENTRY("bahnschrift_32", font_bahnschrift_32);
    FONT_ENTRY("bahnschrift_48", font_bahnschrift_48);
    FONT_ENTRY("agencyb_12", font_agencyb_12);
    FONT_ENTRY("iconfont_16", font_iconfont_16);
    FONT_ENTRY("iconfont_20", font_iconfont_20);
    FONT_ENTRY("cn_16", font_cn_16);
    FONT_ENTRY("montserrat_8", lv_font_montserrat_8);
#undef FONT_ENTRY
    return nullptr;
}

const void* GetImage(const char* name)
{
#define IMAGE_ENTRY(key, value) if(std::strcmp(name, key) == 0) return &value
    IMAGE_ENTRY("dialplate_skin", img_src_dialplate_skin);
    IMAGE_ENTRY("gps_arrow_light", img_src_gps_arrow_light);
    IMAGE_ENTRY("battery", img_src_battery);
    IMAGE_ENTRY("bluetooth", img_src_bluetooth);
    IMAGE_ENTRY("satellite", img_src_satellite);
#undef IMAGE_ENTRY
    return nullptr;
}
}

// These helpers are extracted from the selected repository's real Presenter.
#include "dialplate_presenter_ui.inc"

static void SetMetricText(Page::DialplateView& view, uint8_t index, const char* text)
{
    if(index >= Page::DialplateView::METRIC_NUM) return;
    static const char* numberFonts[] = {"bahnschrift_17", "agencyb_12", "montserrat_8"};
    static const char* timeFonts[] = {"bahnschrift_17", "bahnschrift_13", "agencyb_12", "montserrat_8"};
    static const char* calorieFonts[] = {"bahnschrift_24", "bahnschrift_17", "agencyb_12", "montserrat_8"};
    const int slots[][4] = {{181, 94, 25, 16}, {180, 137, 54, 20},
                           {181, 184, 26, 16}, {180, 225, 54, 22}};
    const char* const* fonts = index == 1 ? timeFonts : index == 3 ? calorieFonts : numberFonts;
    const size_t count = index == 1 || index == 3 ? 4 : 3;
    SetAdaptiveMetricLabel(view.ui.metrics.item[index].labelValue, text, fonts, count,
        slots[index][0], slots[index][1], slots[index][2], slots[index][3],
        index == 0 || index == 2 ? LV_TEXT_ALIGN_RIGHT : LV_TEXT_ALIGN_CENTER);
}

static void CopyPixels(const lv_area_t& area, const uint16_t* pixels, uint32_t count)
{
    Require(area.x1 >= 0 && area.y1 >= 0 && area.x2 < width && area.y2 < height,
            "display transfer stays inside the physical screen");
    const uint32_t expected = (area.x2 - area.x1 + 1) * (area.y2 - area.y1 + 1);
    Require(count == expected, "DMA byte count matches its window");
    uint32_t index = 0;
    for(int y = area.y1; y <= area.y2; y++)
        for(int x = area.x1; x <= area.x2; x++)
            framebuffer[y * width + x].full = pixels[index++];
}

#if DIALPLATE_HW_EFFECTS
#include "HAL/HAL.h"
static uint8_t* Disp_DMA_TragetPoint = nullptr;
static uint8_t* Disp_DMA_CurrentPoint = nullptr;
static HAL::Display_CallbackFunc_t Disp_Callback = nullptr;
static volatile bool Disp_DMA_Busy = false;
static volatile bool Disp_DMA_Notify = true;
static bool pendingDma = false;
static bool dmaCompleteFlag = false;
static lv_area_t dmaWindow = { 0, 0, 0, 0 };
static unsigned addressWindows = 0;
static HAL::Display_CallbackFunc_t lvglFinish = nullptr;

static int dma_flag_get(int) { return dmaCompleteFlag ? 1 : RESET; }
static void dma_flag_clear(int) { dmaCompleteFlag = false; }
static void digitalWrite_HIGH(int) {}
static void digitalWrite_LOW(int) {}

static void Display_SPI_DMA_Send(const void* data, uint32_t bytes)
{
    Require(!pendingDma, "a transfer cannot overwrite an outstanding DMA");
    Require(Disp_DMA_Busy, "busy is published before starting DMA");
    if(!Disp_DMA_Notify) rawTransfers++;
    CopyPixels(dmaWindow, static_cast<const uint16_t*>(data), bytes / sizeof(uint16_t));
    pendingDma = true;
}

extern "C" void DMA1_Channel3_IRQHandler(void);
void mock_wait_for_interrupt()
{
    Require(pendingDma, "bounded mock wait has an actual DMA to complete");
    pendingDma = false;
    dmaCompleteFlag = true;
    DMA1_Channel3_IRQHandler();
}

void HAL::Display_SetAddrWindow(int16_t x0, int16_t y0, int16_t x1, int16_t y1)
{
    Require(!pendingDma, "address window cannot change before DMA completion");
    dmaWindow = { x0, y0, x1, y1 };
    addressWindows++;
}

// The test runner inserts the exact current IRQ and HAL transfer methods.
#include "hal_display_methods.inc"

static void TrackLvglFinish()
{
    normalCallbacks++;
    lvglFinish();
}

static void CountFinish() { normalCallbacks++; }

static void SetupDisplay()
{
    lv_port_disp_init();
    lvglFinish = Disp_Callback;
    HAL::Display_SetSendFinishCallback(TrackLvglFinish);
}
#else
static void Flush(lv_disp_drv_t* driver, const lv_area_t* area, lv_color_t* colors)
{
    CopyPixels(*area, reinterpret_cast<const uint16_t*>(colors),
               (area->x2 - area->x1 + 1) * (area->y2 - area->y1 + 1));
    normalCallbacks++;
    lv_disp_flush_ready(driver);
}

static void SetupDisplay()
{
    static lv_color_t colors[width * 40];
    static lv_disp_draw_buf_t draw;
    static lv_disp_drv_t driver;
    lv_disp_draw_buf_init(&draw, colors, nullptr, width * 40);
    lv_disp_drv_init(&driver);
    driver.hor_res = width;
    driver.ver_res = height;
    driver.draw_buf = &draw;
    driver.flush_cb = Flush;
    lv_disp_drv_register(&driver);
}
#endif

static void Render()
{
    lv_obj_invalidate(lv_scr_act());
    lv_refr_now(nullptr);
#if DIALPLATE_HW_EFFECTS
    HAL::Display_WaitForSendFinish();
#endif
}

static lv_obj_t* CreateRoot(Page::DialplateView& view)
{
    lv_obj_t* root = lv_obj_create(lv_scr_act());
    lv_obj_remove_style_all(root);
    lv_obj_set_size(root, width, height);
    lv_obj_clear_flag(root, LV_OBJ_FLAG_SCROLLABLE);
    view.Create(root);
    lv_obj_update_layout(root);
    return root;
}

static void Animate(Page::DialplateView& view)
{
    view.ui.maxBar.spectrumTimer->timer_cb(view.ui.maxBar.spectrumTimer);
}

static void Save(const std::string& directory, const std::string& name)
{
    const std::string path = directory + "/" + name + ".ppm";
    FILE* file = std::fopen(path.c_str(), "wb");
    Require(file != nullptr, "project-local render output opens");
    std::fprintf(file, "P6\n%d %d\n255\n", width, height);
    std::vector<uint8_t> rgb(framebuffer.size() * 3);
    for(size_t i = 0; i < framebuffer.size(); i++)
    {
        lv_color32_t color;
        color.full = lv_color_to32(framebuffer[i]);
        rgb[i * 3] = color.ch.red;
        rgb[i * 3 + 1] = color.ch.green;
        rgb[i * 3 + 2] = color.ch.blue;
    }
    Require(std::fwrite(rgb.data(), 1, rgb.size(), file) == rgb.size(), "render output is complete");
    Require(std::fclose(file) == 0, "render output closes");
}

static void CheckMetrics(Page::DialplateView& view)
{
    const int positions[][4] = {{181, 94, 25, 16}, {180, 137, 54, 20},
                               {181, 184, 26, 16}, {180, 225, 54, 22}};
    for(int i = 0; i < 4; i++)
    {
        lv_obj_t* label = view.ui.metrics.item[i].labelValue;
        lv_obj_update_layout(label);
        lv_area_t area;
        lv_obj_get_coords(label, &area);
        Require(area.x1 == positions[i][0] && area.y1 == positions[i][1] &&
                lv_area_get_width(&area) == positions[i][2] &&
                lv_area_get_height(&area) == positions[i][3], "metric updates retain their fixed slots");
        Require(area.y2 < 286 && area.x2 < 240, "metrics do not cross the footer or screen");
        Require(lv_label_get_long_mode(label) == LV_LABEL_LONG_CLIP,
                "metric clipping follows the reference UI, not a new scrolling design");
    }
}

static void CheckControls(Page::DialplateView& view)
{
    lv_obj_t* buttons[] = {view.ui.btnCont.btnMap, view.ui.btnCont.btnRec, view.ui.btnCont.btnMenu};
    lv_group_t* group = lv_group_create();
    for(lv_obj_t* button : buttons)
    {
        lv_area_t area;
        lv_obj_get_coords(button, &area);
        Require(area.x1 >= 0 && area.x2 < 240 && area.y1 == 286 && area.y2 < 320,
                "primary controls stay on screen");
        lv_point_t point = {(lv_coord_t)(area.x2 - 6), (lv_coord_t)(area.y1 + 15)};
        Require(lv_indev_search_obj(lv_scr_act(), &point) == button, "button whitespace remains tappable");
        lv_group_add_obj(group, button);
        lv_group_focus_obj(button);
        Require(lv_obj_has_state(button, LV_STATE_FOCUSED), "each primary control is focusable");
    }
    lv_group_del(group);
    view.SetRecRecording(true);
    Require(lv_color_to32(lv_obj_get_style_bg_color(view.ui.btnCont.recDot, 0)) ==
            lv_color_to32(lv_color_hex(0xff2a2a)), "recording indicator retains its red state");
    view.SetRecRecording(false);
}

static void CheckDma()
{
#if DIALPLATE_HW_EFFECTS
    uint16_t pixels[] = {0, 0};
    normalCallbacks = 0;
    HAL::Display_SetSendFinishCallback(CountFinish);
    HAL::Display_SetAddrWindow(0, 0, 1, 0);
    HAL::Display_SendPixels(pixels, 2);
    Require(Disp_DMA_Busy && pendingDma, "normal flush remains asynchronous");
    HAL::Display_SendPixelsBlocking(pixels, 2);
    Require(normalCallbacks == 1 && !Disp_DMA_Busy && Disp_DMA_Notify,
            "blocking transfer drains the prior flush without a second LVGL acknowledgement");
    HAL::Display_SendPixels(pixels, 2);
    HAL::Display_WaitForSendFinish();
    Require(normalCallbacks == 2, "normal completion notifications resume after raw transfer");
    unsigned before = addressWindows;
    const lv_area_t invalid[] = {{-1, 0, 0, 0}, {0, -1, 0, 0}, {0, 0, 240, 0},
                                 {0, 0, 0, 320}, {1, 0, 0, 0}, {0, 1, 0, 0}};
    for(const lv_area_t& area : invalid) lv_port_disp_blit_blocking(&area, reinterpret_cast<lv_color_t*>(pixels));
    lv_port_disp_blit_blocking(nullptr, reinterpret_cast<lv_color_t*>(pixels));
    const lv_area_t valid = {0, 0, 1, 0};
    lv_port_disp_blit_blocking(&valid, nullptr);
    HAL::Display_SendPixelsBlocking(nullptr, 1);
    HAL::Display_SendPixelsBlocking(pixels, 0);
    Require(addressWindows == before && !pendingDma, "invalid or empty transfers never start DMA");
    unsigned callbacks = normalCallbacks;
    lv_port_disp_blit_blocking(&valid, reinterpret_cast<lv_color_t*>(pixels));
    Require(normalCallbacks == callbacks && addressWindows == before + 1,
            "valid direct writes do not acknowledge LVGL");
    HAL::Display_SetSendFinishCallback(TrackLvglFinish);
#endif
}

int main(int argc, char** argv)
{
    Require(argc == 3 || argc == 4, "test case and checked output directory are required");
    if(argc == 4) Require(std::strcmp(argv[3], "--without-arrow") == 0, "known reference-only adjustment");
    const std::string test = argv[1];
#if DIALPLATE_HW_EFFECTS
    const std::string variant = "hardware";
#elif defined(ARDUINO)
    const std::string variant = "fallback";
#else
    const std::string variant = "desktop";
#endif
    lv_init();
    SetupDisplay();
    Page::DialplateView view;
    lv_obj_t* root = CreateRoot(view);
    if(argc == 4)
    {
        // Compare the original UI minus the single owner-requested overlay.
        Require(view.ui.arrow.img != nullptr, "unmodified reference creates the white arrow");
        lv_obj_del(view.ui.arrow.img);
        view.ui.arrow.img = nullptr;
    }
#if DIALPLATE_HW_EFFECTS
    Require(rawTransfers > 0, "the original hardware View initializes its direct frame during creation");
#else
    Require(rawTransfers == 0, "desktop rendering uses LVGL objects only");
#endif

    if(test == "layout") CheckMetrics(view);
    else if(test == "long_values")
    {
        const char* values[] = {"999.9", "1234:59:59", "9999.9", "2147483647"};
        for(uint8_t i = 0; i < 4; i++) SetMetricText(view, i, values[i]);
        CheckMetrics(view);
        const std::string extreme(100, '9');
        SetMetricText(view, 0, extreme.c_str());
        Require(lv_label_get_long_mode(view.ui.metrics.item[0].labelValue) == LV_LABEL_LONG_CLIP,
                "long values retain the reference clipping policy");
        Require(std::strcmp(lv_label_get_text(view.ui.metrics.item[0].labelValue), extreme.c_str()) == 0,
                "long values are not silently truncated");
        SetMetricText(view, 4, "ignored");
        SetMetricText(view, 0, nullptr);
        CheckMetrics(view);
    }
    else if(test == "populated")
    {
        SetSpeedLabel(view.ui.speed.labelValue, 28.6f);
        SetMaxSpeedLabel(view.ui.maxBar.labelMax, 68.4f);
        const char* values[] = {"24.5", "1:23:45", "34.5", "678"};
        for(uint8_t i = 0; i < 4; i++) SetMetricText(view, i, values[i]);
        SetCalorieLabel(view.ui.metrics.item[3].labelValue, 678);
        SetNavDistanceLabel(view.ui.nav.labelDist, view.ui.nav.labelDistUnit, 1200);
        view.SetBattery(52, false);
        view.SetAltitude(678);
        view.SetBluetoothConnected(true);
        view.SetRecRecording(true);
        view.SetArrowAngle(123.0f);
        view.SetSpectrumSpeed(28.6f);
        view.SetSpectrumActive(true);
        Animate(view);
        CheckMetrics(view);
    }
    else if(test == "arrow")
    {
        Require(view.ui.arrow.img == nullptr, "Dialplate does not create the white arrow overlay");
        Require(ResourcePool::GetImage("gps_arrow_light") != nullptr, "shared map arrow resource remains available");
        view.SetArrowAngle(90.0f);
        view.SetArrowAngle(-1.0f);
        view.SetArrowAngle(359.8f);
        view.SetArrowAngle(720.0f);
        Require(view.ui.arrow.img == nullptr, "heading updates cannot recreate the removed overlay");
    }
    else if(test == "controls") CheckControls(view);
    else if(test == "spectrum")
    {
        Require(view.ui.maxBar.spectrumTimer->period == 50 && view.ui.maxBar.spectrumTimer->paused,
                "50 ms spectrum starts paused");
        view.SetSpectrumActive(true);
        unsigned before = normalCallbacks;
        Animate(view);
        Require(normalCallbacks == before, "animation does not acknowledge a pending LVGL flush");
#if DIALPLATE_HW_EFFECTS
        Require(rawTransfers > 0 && view.ui.borderGlowPhase == 1, "hardware uses sparse direct updates");
#else
        Require(view.ui.maxBar.spectrumLit[0] == 1 && view.ui.maxBar.spectrumLit[1] == 2 &&
                view.ui.maxBar.spectrumLit[2] == 1, "fallback retains stacked segment geometry");
#endif
        view.SetSpectrumSpeed(50.0f);
        Animate(view);
        Require(view.ui.maxBar.spectrumLevelPct == 100, "full speed retains the full spectrum range");
        view.SetSpectrumSpeed(0.0f);
        Require(view.ui.maxBar.spectrumLevelPct == 10, "zero speed retains the reference minimum level");
        Require(lv_obj_get_style_text_opa(view.ui.nav.labelTurnIcon, 0) == LV_OPA_90,
                "turn indicator follows the pulse frames");
        uint8_t phase = view.ui.maxBar.spectrumPhase;
        view.SetSpectrumActive(false);
        lv_tick_inc(100);
        lv_timer_handler();
        Require(view.ui.maxBar.spectrumTimer->paused && view.ui.maxBar.spectrumPhase == phase,
                "paused timers cannot continue the animation");
    }
    else if(test == "spectrum_frames")
    {
        view.SetSpectrumActive(true);
        for(unsigned frame = 0; frame < 16; frame++)
        {
            view.SetSpectrumSpeed((frame % 5) * 12.5f);
#if DIALPLATE_HW_EFFECTS
            Render();
            Animate(view);
#else
            Animate(view);
            Render();
#endif
            Save(argv[2], variant + "-spectrum_frames-" + std::to_string(frame));
        }
    }
    else if(test == "timer_frames" || test == "statusbar_frames" || test == "transparent_top_frames")
    {
        lv_obj_t* top = nullptr;
        if(test == "statusbar_frames") top = StatusBarProbe::Create();
        else if(test == "transparent_top_frames")
        {
            top = lv_obj_create(lv_layer_top());
            lv_obj_remove_style_all(top);
            lv_obj_set_size(top, width, height);
            lv_obj_set_style_opa(top, LV_OPA_TRANSP, 0);
        }
        view.AppearAnimStart();
        Render();
        for(unsigned frame = 0; frame < 12; frame++)
        {
            lv_tick_inc(50);
            lv_timer_handler();
#if DIALPLATE_HW_EFFECTS
            HAL::Display_WaitForSendFinish();
#endif
        }
        view.SetSpectrumActive(true);
        Render();
        lv_obj_update_layout(root);
        if(top != nullptr)
        {
            lv_obj_update_layout(top);
            Require(lv_obj_is_visible(top), "regression scene retains the geometrically visible top object");
        }
        for(unsigned frame = 0; frame < 32; frame++)
        {
            const unsigned before = rawTransfers;
            lv_tick_inc(50);
            lv_timer_handler();
#if DIALPLATE_HW_EFFECTS
            HAL::Display_WaitForSendFinish();
            Require(rawTransfers > before, "top objects cannot suppress the original direct animation");
            Require(view.ui.borderGlowPhase == (frame + 1) % 16, "real timers advance every original glow phase");
#else
            Require(rawTransfers == before, "desktop timers remain on the LVGL rendering path");
#endif
            Save(argv[2], variant + "-" + test + "-" + std::to_string(frame));
        }
        if(top != nullptr) lv_obj_del(top);
    }
    else if(test == "lifecycle")
    {
        view.SetSpectrumActive(false);
        lv_mem_monitor_t initial = {};
        for(int i = 0; i < 13; i++)
        {
            Page::DialplateView temporary;
            lv_obj_t* temporaryRoot = CreateRoot(temporary);
            temporary.SetSpectrumActive(true);
            Animate(temporary);
            temporary.Delete();
            Require(temporary.ui.maxBar.spectrumTimer == nullptr, "unload releases the timer");
            lv_obj_del(temporaryRoot);
            Render();
            if(i == 0) lv_mem_monitor(&initial);
        }
        lv_mem_monitor_t final = {};
        lv_mem_monitor(&final);
        Require(final.free_size + 1024 >= initial.free_size, "repeated creation/deletion has bounded retained memory");
    }
    else if(test == "dma") CheckDma();
    else Require(false, "known test case");

    Render();
    Save(argv[2], variant + "-" + test);
    view.Delete();
    lv_obj_del(root);
    Render();
    lv_mem_monitor_t memory = {};
    lv_mem_monitor(&memory);
    Require(memory.max_used < memory.total_size && lv_mem_test() == LV_RES_OK,
            "the production-sized LVGL pool remains valid through the complete lifecycle");
    std::printf("PASS real-LVGL %s %s; raw=%u normal-completions=%u; lvgl-peak=%u pool=%u "
                "(host self-test, not device evidence)\n",
                variant.c_str(), test.c_str(), rawTransfers, normalCallbacks,
                memory.max_used, memory.total_size);
    return 0;
}
