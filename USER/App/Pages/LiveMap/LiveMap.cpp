#include "LiveMap.h"
#include "Config/Config.h"
#include "lvgl/lvgl.h"
#include "HAL/HAL.h"
#include <string.h>

#ifdef ARDUINO
extern "C" void xtrack_img_line_cache_invalidate(void);
extern "C" void xtrack_img_line_cache_reset_stats(void);
extern "C" void xtrack_img_line_cache_get_stats(uint32_t* hits, uint32_t* misses, uint32_t* readBytes, uint32_t* sdCycles);
extern "C" uint32_t system_core_clock;
/* lv_port_disp.cpp 导出的 LVGL 刷新周期耗时统计（C++ 链接） */
void lv_port_disp_get_refr_stats(uint32_t* timeMs, uint32_t* cnt, uint32_t* px);
void lv_port_disp_reset_refr_stats(void);
#endif

using namespace Page;

#if CONFIG_LIVE_MAP_SNAPSHOT_ENABLE

/* ================= 视口快照渲染 =================
 * 地图可见窗口(240x320)像素整帧常驻 RAM,LVGL 走内存图直拷路径渲染;
 * 滚动时 memmove 平移内容、仅从 SD 读新露出的边条(经瓦片行缓存,顺序
 * 访问几乎全命中)。容器坐标系/线条/箭头逻辑与瓦片模式完全一致,
 * 差别仅是容器内的像素来源由 6 张瓦片 img 换成 1 张快照 img。 */

/* 快照高与屏幕一致（CONFIG_LIVE_MAP_VIEW_* 展开为运行时函数，
 * 不能用于静态数组，此处用字面常量） */
/* 快照比屏幕宽 16px 作水平 margin:瓦片为行主序位图,水平边条读取存在
 * "窄列跨 band 全读"的放大(逐行 320 次调用、band 8KB 只用几十字节),
 * 故快照原点按 16px 网格对齐、水平滚动一次推进 16px,margin 吸收视口与
 * 网格化原点之间的偏差,视觉无损,水平方向 SD 读与调用次数降约一个量级。
 * 垂直滚动读整行无放大,保持逐像素平滑。 */
#define SNAPSHOT_W 256
#define SNAPSHOT_VIEW_W 240
#define SNAPSHOT_GRID_X 16
#define SNAPSHOT_H 320
#define SNAPSHOT_TILE_SIZE 256

#ifdef ARDUINO
/* 150KB 大缓冲,置于分散加载 RW_IRAM2(.sram_ext, UNINIT)——
 * 由低 384K 尾部 + EOPB0 扩展出的高 128K 拼成的连续区,内容不被
 * __main 清零,依 snapValid 控制首次填充 */
__attribute__((section(".sram_ext"), zero_init))
#endif
static lv_color_t snapshotBuf[SNAPSHOT_W * SNAPSHOT_H];

static lv_img_dsc_t snapshotDsc;
static int32_t snapshotOriginX;   /* 快照左上角对应的地图全局像素坐标 */
static int32_t snapshotOriginY;
static bool snapshotValid = false;

/* 打开失败瓦片的短期负缓存：缺瓦片区域（地图边缘/未下载）若每行重试
 * open，每次失败都是一趟 FAT 目录遍历，实测把 LVGL 主循环拖到 1/4 速。
 * 失败瓦片 2 秒内直接填白跳过，行为与瓦片模式"src 设置失败即空白"对齐。 */
#define SNAP_FAIL_CACHE_CNT 4
#define SNAP_FAIL_HOLD_MS   2000
static uint32_t snapFailKey[SNAP_FAIL_CACHE_CNT];
static uint32_t snapFailTick[SNAP_FAIL_CACHE_CNT];
static uint8_t snapFailUsed[SNAP_FAIL_CACHE_CNT];

static bool Snapshot_TileRecentlyFailed(uint32_t key)
{
    for (uint32_t i = 0; i < SNAP_FAIL_CACHE_CNT; i++)
    {
        if (snapFailUsed[i] && snapFailKey[i] == key &&
            lv_tick_elaps(snapFailTick[i]) < SNAP_FAIL_HOLD_MS)
        {
            return true;
        }
    }
    return false;
}

static void Snapshot_TileMarkFailed(uint32_t key)
{
    uint32_t victim = 0;
    uint32_t victimAge = 0;
    for (uint32_t i = 0; i < SNAP_FAIL_CACHE_CNT; i++)
    {
        if (!snapFailUsed[i] || snapFailKey[i] == key)
        {
            victim = i;
            break;
        }
        uint32_t age = lv_tick_elaps(snapFailTick[i]);
        if (age >= victimAge)
        {
            victimAge = age;
            victim = i;
        }
    }
    snapFailKey[victim] = key;
    snapFailTick[victim] = lv_tick_get();
    snapFailUsed[victim] = 1;
}

/* 读取一行像素段到 dst:全局像素坐标 (gx,gy) 起、长 len。
 * 跨瓦片自动分段;越界或读取失败的部分填白(与页面底色一致)。
 * 经 LVGL img cache + decoder 行缓存,顺序滚动时 SD 读近乎全命中。 */
#define SNAP_FILL_FAIL lv_color_white()
static void Snapshot_ReadLineData(MapConv& conv, int dataLevel,
                                  int32_t gx, int32_t gy, int32_t len, lv_color_t* dst);

static void Snapshot_ReadLine(MapConv& conv, int32_t gx, int32_t gy, int32_t len, lv_color_t* dst)
{
    if (gy < 0 || gx + len <= 0)
    {
        for (int32_t i = 0; i < len; i++) dst[i] = SNAP_FILL_FAIL;
        return;
    }

#if CONFIG_LIVE_MAP_ZOOM_EXTRA_LEVELS > 0
    /* 高等级放大显示(√2 阶梯):显示级别超出 SD 卡数据级别 extra 级时,
     * 显示坐标系相对数据级放大 √2^extra(17 级面积减半、18 级面积 1/4),
     * 与坐标生成(ConvertMapCoordinate)一致。读取:显示坐标按定点因子
     * 65536/√2^extra 映射到数据坐标,读一段数据行再按显示像素相位展开。
     * 纵向相邻显示行常映射到同一数据行,重复读取由瓦片行缓存吸收。 */
    int extra = conv.GetLevel() - MapConv::GetDataLevelMax();
    if (extra > 0)
    {
        /* 定点 16.16:√2^0 / √2^-1 / √2^-2 */
        static const uint32_t dispToData[] = { 65536u, 46341u, 32768u };
        uint32_t f = dispToData[extra <= 2 ? extra : 2];
        int dataLevel = MapConv::GetDataLevelMax();

        int32_t dgxStart = (int32_t)(((int64_t)gx * f) >> 16);
        int32_t dgxEnd = (int32_t)(((int64_t)(gx + len - 1) * f) >> 16);
        int32_t dgy = (int32_t)(((int64_t)gy * f) >> 16);
        int32_t dlen = dgxEnd - dgxStart + 1;
        lv_color_t tmp[SNAPSHOT_W];   /* extra>=1 时 dlen <= W/√2+1 */

        Snapshot_ReadLineData(conv, dataLevel, dgxStart, dgy, dlen, tmp);

        for (int32_t i = 0; i < len; i++)
        {
            dst[i] = tmp[(int32_t)(((int64_t)(gx + i) * f) >> 16) - dgxStart];
        }
        return;
    }
#endif

    Snapshot_ReadLineData(conv, conv.GetLevel(), gx, gy, len, dst);
}

/* 按指定数据级别读取一行像素段(gx/gy/len 均为该级别坐标系):
 * 跨瓦片自动分段;负缓存/打开失败/越界填充 SNAP_FILL_FAIL。 */
static void Snapshot_ReadLineData(MapConv& conv, int dataLevel,
                                  int32_t gx, int32_t gy, int32_t len, lv_color_t* dst)
{
    while (len > 0)
    {
        if (gx < 0)
        {
            int32_t seg = -gx < len ? -gx : len;
            for (int32_t i = 0; i < seg; i++) dst[i] = SNAP_FILL_FAIL;
            dst += seg; gx += seg; len -= seg;
            continue;
        }

        int32_t inTileX = gx % SNAPSHOT_TILE_SIZE;
        int32_t seg = SNAPSHOT_TILE_SIZE - inTileX;
        if (seg > len) seg = len;

        uint32_t tileKey = ((uint32_t)dataLevel << 24)
                           ^ ((uint32_t)(gx / SNAPSHOT_TILE_SIZE) << 12)
                           ^ (uint32_t)(gy / SNAPSHOT_TILE_SIZE);
        if (Snapshot_TileRecentlyFailed(tileKey))
        {
            for (int32_t i = 0; i < seg; i++) dst[i] = SNAP_FILL_FAIL;
            dst += seg; gx += seg; len -= seg;
            continue;
        }

        char path[64];
        conv.ConvertMapPathAtLevel(dataLevel, gx, gy, path, sizeof(path));

        bool ok = false;
        _lv_img_cache_entry_t* ce = _lv_img_cache_open(path, lv_color_white(), 0);
        if (ce != nullptr)
        {
            ok = (lv_img_decoder_read_line(&ce->dec_dsc,
                                           (lv_coord_t)inTileX,
                                           (lv_coord_t)(gy % SNAPSHOT_TILE_SIZE),
                                           (lv_coord_t)seg,
                                           (uint8_t*)dst) == LV_RES_OK);
        }
        if (!ok)
        {
            Snapshot_TileMarkFailed(tileKey);
            for (int32_t i = 0; i < seg; i++) dst[i] = SNAP_FILL_FAIL;
        }

        dst += seg; gx += seg; len -= seg;
    }
}

/* 全量填充:缩放切换/首帧/跳变超过一屏时执行(一次约 40ms) */
static void Snapshot_Fill(MapConv& conv)
{
    lv_color_t* p = snapshotBuf;
    for (int32_t y = 0; y < SNAPSHOT_H; y++, p += SNAPSHOT_W)
    {
        Snapshot_ReadLine(conv, snapshotOriginX, snapshotOriginY + y, SNAPSHOT_W, p);
    }
}

/* 增量滚动:内容平移 + 只读新露出的边条(dx/dy 为快照原点位移,已更新) */
static void Snapshot_Scroll(MapConv& conv, int32_t dx, int32_t dy)
{
    /* 垂直:整块 memmove + 读新行 */
    if (dy > 0)
    {
        memmove(snapshotBuf, snapshotBuf + dy * SNAPSHOT_W,
                (size_t)(SNAPSHOT_H - dy) * SNAPSHOT_W * sizeof(lv_color_t));
        for (int32_t y = SNAPSHOT_H - dy; y < SNAPSHOT_H; y++)
        {
            Snapshot_ReadLine(conv, snapshotOriginX, snapshotOriginY + y,
                              SNAPSHOT_W, snapshotBuf + y * SNAPSHOT_W);
        }
    }
    else if (dy < 0)
    {
        memmove(snapshotBuf + (-dy) * SNAPSHOT_W, snapshotBuf,
                (size_t)(SNAPSHOT_H + dy) * SNAPSHOT_W * sizeof(lv_color_t));
        for (int32_t y = 0; y < -dy; y++)
        {
            Snapshot_ReadLine(conv, snapshotOriginX, snapshotOriginY + y,
                              SNAPSHOT_W, snapshotBuf + y * SNAPSHOT_W);
        }
    }

    /* 水平:逐行 memmove + 读新列段(垂直新行已按新 X 读全宽,跳过) */
    if (dx != 0)
    {
        int32_t rowStart = (dy > 0) ? 0 : ((dy < 0) ? -dy : 0);
        int32_t rowEnd = (dy > 0) ? (SNAPSHOT_H - dy) : SNAPSHOT_H;
        int32_t adx = dx > 0 ? dx : -dx;

        for (int32_t y = rowStart; y < rowEnd; y++)
        {
            lv_color_t* row = snapshotBuf + y * SNAPSHOT_W;
            if (dx > 0)
            {
                memmove(row, row + dx, (size_t)(SNAPSHOT_W - dx) * sizeof(lv_color_t));
                Snapshot_ReadLine(conv, snapshotOriginX + SNAPSHOT_W - dx,
                                  snapshotOriginY + y, adx, row + SNAPSHOT_W - dx);
            }
            else
            {
                memmove(row - dx, row, (size_t)(SNAPSHOT_W + dx) * sizeof(lv_color_t));
                Snapshot_ReadLine(conv, snapshotOriginX,
                                  snapshotOriginY + y, adx, row);
            }
        }
    }
}

/* 每个地图刷新周期调用:使快照窗口对齐当前显示坐标的视口,
 * 并同步快照 img 在瓦片容器坐标系中的位置。
 * phaseXFp/phaseYFp: 显示坐标的 1/256 像素相位(0..255),
 * 亚像素模式下经 pivot 编码为双线性变换的平移分量。 */
static void Snapshot_Update(int32_t dispX, int32_t dispY,
                            uint16_t phaseXFp, uint16_t phaseYFp,
                            LiveMapModel& model, LiveMapView& view)
{
    /* 视口左上角(全局像素);快照 X 原点向下对齐到 16px 网格,
     * 视口相对快照的偏差 0..15px 由 16px 水平 margin 吸收 */
    int32_t viewX = dispX - SNAPSHOT_VIEW_W / 2;
    int32_t newX = viewX - (((viewX % SNAPSHOT_GRID_X) + SNAPSHOT_GRID_X) % SNAPSHOT_GRID_X);
    int32_t newY = dispY - SNAPSHOT_H / 2;

    if (!snapshotValid)
    {
        snapshotOriginX = newX;
        snapshotOriginY = newY;
        Snapshot_Fill(model.mapConv);
        snapshotValid = true;
    }
    else
    {
        int32_t dx = newX - snapshotOriginX;
        int32_t dy = newY - snapshotOriginY;
        int32_t adx = dx > 0 ? dx : -dx;
        int32_t ady = dy > 0 ? dy : -dy;

        if (dx != 0 || dy != 0)
        {
            snapshotOriginX = newX;
            snapshotOriginY = newY;
            if (adx >= SNAPSHOT_W || ady >= SNAPSHOT_H)
            {
                Snapshot_Fill(model.mapConv);
            }
            else
            {
                Snapshot_Scroll(model.mapConv, dx, dy);
            }
        }
    }

    TileConv::Rect_t rect;
    model.tileConv.GetTileContainer(&rect);
    view.SetSnapshotPos(
        (lv_coord_t)(snapshotOriginX - rect.x),
        (lv_coord_t)(snapshotOriginY - rect.y)
    );

    (void)phaseXFp;
    (void)phaseYFp;

    /* 快照内容(RAM 位图)变化后须显式失效。快照恒铺满视口,失效屏幕与
     * 失效快照 img 等效且不依赖对象坐标状态(历史上容器高度为 0 的 bug
     * 曾让 img 级失效被可见性裁剪吞掉,屏幕级失效对这类问题免疫)。 */
    lv_obj_invalidate(lv_scr_act());
}

#endif /* CONFIG_LIVE_MAP_SNAPSHOT_ENABLE */

uint16_t LiveMap::mapLevelCurrent = CONFIG_LIVE_MAP_LEVEL_DEFAULT;

static bool TickReached(uint32_t now, uint32_t target)
{
    return (int32_t)(now - target) >= 0;
}

static void ClearFocusState(lv_obj_t* obj)
{
    if (obj == nullptr)
    {
        return;
    }

    lv_obj_clear_state(obj, (lv_state_t)(LV_STATE_FOCUSED | LV_STATE_EDITED | LV_STATE_FOCUS_KEY));
}

#define ICON_TURN_RIGHT     "\xEE\x98\xAB"
#define ICON_TURN_LEFT      "\xEE\x98\xAC"
#define ICON_TURN_STRAIGHT  "\xEE\x98\xBB"
#define ICON_TURN_UTURN     "\xEE\x98\xAD"

#define TXT_NAV_READY       "\xE8\xB7\xAF\xE7\xBA\xBF\xE5\xB7\xB2\xE5\xB0\xB1\xE7\xBB\xAA"
#define TXT_NAV_IMPORTING   "\xE6\xAD\xA3\xE5\x9C\xA8\xE5\xAF\xBC\xE5\x85\xA5"
#define TXT_NAV_INVALID     "\xE8\xB7\xAF\xE7\xBA\xBF\xE6\x97\xA0\xE6\x95\x88"
#define TXT_NAV_ERROR       "\xE5\xAF\xBC\xE8\x88\xAA\xE9\x94\x99\xE8\xAF\xAF"
#define TXT_NAV_APPROACH    "\xE5\x89\x8D\xE5\xBE\x80\xE8\xB7\xAF\xE7\xBA\xBF"
#define TXT_NAV_OFF_ROUTE   "\xE5\x81\x8F\xE7\xA6\xBB\xE8\xB7\xAF\xE7\xBA\xBF"
#define TXT_NAV_REVERSE     "\xE6\x96\xB9\xE5\x90\x91\xE7\x9B\xB8\xE5\x8F\x8D"
#define TXT_NAV_FINISH      "\xE5\x88\xB0\xE8\xBE\xBE\xE7\xBB\x88\xE7\x82\xB9"
#define TXT_NAV_LEFT        "\xE5\xB7\xA6\xE8\xBD\xAC"
#define TXT_NAV_RIGHT       "\xE5\x8F\xB3\xE8\xBD\xAC"
#define TXT_NAV_SHARP_LEFT  "\xE6\x80\xA5\xE5\xB7\xA6\xE8\xBD\xAC"
#define TXT_NAV_SHARP_RIGHT "\xE6\x80\xA5\xE5\x8F\xB3\xE8\xBD\xAC"
#define TXT_NAV_UTURN       "\xE6\x8E\x89\xE5\xA4\xB4"
#define TXT_NAV_STRAIGHT    "\xE7\x9B\xB4\xE8\xA1\x8C"

LiveMap::LiveMap()
{
    memset(&priv, 0, sizeof(priv));
}

LiveMap::~LiveMap()
{

}

void LiveMap::onCustomAttrConfig()
{
    SetCustomCacheEnable(false);
}

void LiveMap::onViewLoad()
{
    const uint32_t tileSize = 256;

    Model.tileConv.SetTileSize(tileSize);
    Model.tileConv.SetViewSize(
        CONFIG_LIVE_MAP_VIEW_WIDTH,
        CONFIG_LIVE_MAP_VIEW_HEIGHT
    );
    Model.tileConv.SetFocusPos(0, 0);

    TileConv::Rect_t rect;
    uint32_t tileNum = Model.tileConv.GetTileContainer(&rect);

    View.Create(_root, tileNum);
    lv_slider_set_range(
        View.ui.zoom.slider,
        Model.mapConv.GetLevelMin(),
        Model.mapConv.GetLevelMax()
    );
    View.SetMapTile(tileSize, rect.width / tileSize);

#if CONFIG_LIVE_MAP_SNAPSHOT_ENABLE
    /* 快照模式 tileNum=0,SetMapTile 依 tileNum 算出的容器高度为 0,
     * 会使全部子对象(快照/箭头/线条)被可见性裁剪而不绘制;
     * 容器尺寸必须直接取瓦片容器矩形 */
    lv_obj_set_size(View.ui.map.cont, (lv_coord_t)rect.width, (lv_coord_t)rect.height);

    snapshotDsc.header.always_zero = 0;
    snapshotDsc.header.reserved = 0;
    snapshotDsc.header.w = SNAPSHOT_W;
    snapshotDsc.header.h = SNAPSHOT_H;
    snapshotDsc.header.cf = LV_IMG_CF_TRUE_COLOR;
    snapshotDsc.data_size = sizeof(snapshotBuf);
    snapshotDsc.data = (const uint8_t*)snapshotBuf;
    View.SetSnapshotSrc(&snapshotDsc);
    snapshotValid = false;
#endif

#if CONFIG_LIVE_MAP_DEBUG_ENABLE
    lv_obj_t* contView = lv_obj_create(root);
    lv_obj_center(contView);
    lv_obj_set_size(contView, CONFIG_LIVE_MAP_VIEW_WIDTH, CONFIG_LIVE_MAP_VIEW_HEIGHT);
    lv_obj_set_style_border_color(contView, lv_palette_main(LV_PALETTE_RED), 0);
    lv_obj_set_style_border_width(contView, 1, 0);
#endif

    AttachEvent(_root);
    AttachEvent(View.ui.zoom.slider);
    AttachEvent(View.ui.sportInfo.cont);

    lv_slider_set_value(View.ui.zoom.slider, mapLevelCurrent, LV_ANIM_OFF);
    Model.mapConv.SetLevel(mapLevelCurrent);
    lv_obj_add_flag(View.ui.map.cont, LV_OBJ_FLAG_HIDDEN);

    /* Point filter */
    Model.pointFilter.SetOffsetThreshold(CONFIG_TRACK_FILTER_OFFSET_THRESHOLD);
    Model.pointFilter.SetOutputPointCallback([](TrackPointFilter * filter, const TrackPointFilter::Point_t* point)
    {
        LiveMap* instance = (LiveMap*)filter->userData;
        instance->TrackLineAppendToEnd((int32_t)point->x, (int32_t)point->y);
    });
    Model.pointFilter.userData = this;

    /* Line filter */
    Model.lineFilter.SetOutputPointCallback(onTrackLineEvent);
    Model.lineFilter.userData = this;
}

void LiveMap::onViewDidLoad()
{

}

void LiveMap::onViewWillAppear()
{
    lv_obj_set_style_opa(_root, LV_OPA_COVER, LV_PART_MAIN);
    Model.Init();

    char theme[16];
    Model.GetArrowTheme(theme, sizeof(theme));
    View.SetArrowTheme(theme);

    priv.isTrackAvtive = Model.GetTrackFilterActive();

    Model.SetStatusBarStyle(DataProc::STATUS_BAR_STYLE_BLACK);
    priv.sportInfoValid = false;
    priv.navInfoValid = false;
    priv.navBannerVisible = false;
    priv.routeRenderValid = false;
    priv.routeRenderRevision = 0;
    priv.routeRenderLevel = mapLevelCurrent;
    View.RouteLineReset();
    SportInfoUpdate();
    NavigationBannerUpdate();
    lv_obj_clear_flag(View.ui.labelInfo, LV_OBJ_FLAG_HIDDEN);
}

void LiveMap::onViewDidAppear()
{
    priv.lastMapUpdateTime = 0;
    priv.nextMapUpdateTime = 0;
    priv.lastSportUpdateTime = 0;
    priv.lastNavigationUpdateTime = 0;
    priv.lastRttStatsTime = lv_tick_get();
    priv.updateCnt = 0;
    priv.mapReloadCnt = 0;
    priv.hasLastMapPoint = false;
    priv.hasContPos = false;
    priv.recentering = false;
    priv.hasDispMap = false;
#if CONFIG_LIVE_MAP_SNAPSHOT_ENABLE
    snapshotValid = false;
#endif
    priv.zoomCtrlHidden = lv_obj_has_state(View.ui.zoom.cont, LV_STATE_USER_1);
#ifdef ARDUINO
    xtrack_img_line_cache_reset_stats();
    lv_port_disp_reset_refr_stats();
    SEGGER_RTT_printf(
        0,
        "LiveMap start: tiles=%u imgCache=%u view=%ux%u\r\n",
        (unsigned)View.ui.map.tileNum,
        (unsigned)LV_IMG_CACHE_DEF_SIZE,
        (unsigned)CONFIG_LIVE_MAP_VIEW_WIDTH,
        (unsigned)CONFIG_LIVE_MAP_VIEW_HEIGHT
    );
#endif
    priv.lastTileContOriPoint.x = 2147483647;
    priv.lastTileContOriPoint.y = 2147483647;

    priv.isTrackAvtive = Model.GetTrackFilterActive();
    if (!priv.isTrackAvtive)
    {
        Model.pointFilter.SetOutputPointCallback(nullptr);
    }

    /* Register SD card event callback for hot-plug support */
    HAL::SD_SetEventCallback([](bool isInsert)
    {
        if (isInsert)
        {
            /* SD card was inserted after system boot
             * Need to clear LVGL image cache because cached entries
             * may have failed state from previous load attempts */
            lv_img_cache_invalidate_src(NULL);  // Clear all cached images
#ifdef ARDUINO
            xtrack_img_line_cache_invalidate();
#endif
#if CONFIG_LIVE_MAP_SNAPSHOT_ENABLE
            snapshotValid = false;
#endif

            /* Note: Map tiles will be automatically reloaded on next Update() cycle
             * when CheckPosition() detects map needs refresh */
        }
    });

    lv_group_t* group = lv_group_get_default();
    if (group != nullptr && View.ui.zoom.slider != nullptr)
    {
        lv_group_remove_all_objs(group);
        lv_group_set_focus_cb(group, nullptr);
        lv_group_set_wrap(group, true);
        lv_group_set_editing(group, false);
        ClearFocusState(View.ui.zoom.slider);

        lv_group_add_obj(group, View.ui.zoom.slider);
        lv_group_focus_obj(View.ui.zoom.slider);
        lv_group_set_editing(group, true);
    }

    CheckPosition();
    priv.lastMapUpdateTime = lv_tick_get();

    lv_obj_clear_flag(View.ui.map.cont, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(View.ui.labelInfo, LV_OBJ_FLAG_HIDDEN);

    priv.timer = lv_timer_create([](lv_timer_t* timer)
    {
        LiveMap* instance = (LiveMap*)timer->user_data;
        instance->Update();
    },
    CONFIG_LIVE_MAP_TIMER_PERIOD,
    this);
}

void LiveMap::onViewWillDisappear()
{
    if (priv.timer != nullptr)
    {
        lv_timer_del(priv.timer);
        priv.timer = nullptr;
    }

    lv_group_t* group = lv_group_get_default();
    if (group != nullptr)
    {
        lv_group_set_focus_cb(group, nullptr);
        lv_group_set_editing(group, false);
        lv_group_remove_all_objs(group);
    }
    ClearFocusState(View.ui.zoom.slider);

    if (View.ui.map.cont != nullptr)
    {
        lv_obj_add_flag(View.ui.map.cont, LV_OBJ_FLAG_HIDDEN);
    }
    View.SetNavigationBannerVisible(false);
    View.SetApproachLine(0, 0, 0, 0, false);
    priv.navBannerVisible = false;
    lv_obj_fade_out(_root, 250, 250);
}

void LiveMap::onViewDidDisappear()
{
    /* Unregister SD card event callback to avoid dangling pointer */
    HAL::SD_SetEventCallback(nullptr);

    Model.Deinit();
}

void LiveMap::onViewUnload()
{
    View.Delete();
}

void LiveMap::onViewDidUnload()
{

}

void LiveMap::AttachEvent(lv_obj_t* obj)
{
    lv_obj_add_event_cb(obj, onEvent, LV_EVENT_ALL, this);
}

void LiveMap::Update()
{
#ifdef ARDUINO
    priv.updateCnt++;
    if (lv_tick_elaps(priv.lastRttStatsTime) >= 1000)
    {
        uint32_t hits = 0;
        uint32_t misses = 0;
        uint32_t readBytes = 0;
        uint32_t sdCycles = 0;
        xtrack_img_line_cache_get_stats(&hits, &misses, &readBytes, &sdCycles);

        uint32_t refrMs = 0;
        uint32_t refrCnt = 0;
        uint32_t refrPx = 0;
        lv_port_disp_get_refr_stats(&refrMs, &refrCnt, &refrPx);

        /* sdMs：本秒内渲染管线中 SD seek+read 的累计等待；
         * refrMs：本秒内 LVGL 刷新周期总耗时（渲染+SD 等待+flush 等待）；
         * refrMs - sdMs ≈ 纯渲染与传输等待，用于瓶颈归因。 */
        uint32_t sdMs = sdCycles / (system_core_clock / 1000u);

        SEGGER_RTT_printf(
            0,
            "LiveMap stat: update=%u reload=%u lineHit=%u lineMiss=%u lineReadKB=%u sdMs=%u refrMs=%u refrCnt=%u refrPxK=%u\r\n",
            (unsigned)priv.updateCnt,
            (unsigned)priv.mapReloadCnt,
            (unsigned)hits,
            (unsigned)misses,
            (unsigned)(readBytes / 1024),
            (unsigned)sdMs,
            (unsigned)refrMs,
            (unsigned)refrCnt,
            (unsigned)(refrPx / 1000)
        );

        priv.updateCnt = 0;
        priv.mapReloadCnt = 0;
        priv.lastRttStatsTime = lv_tick_get();
        xtrack_img_line_cache_reset_stats();
        lv_port_disp_reset_refr_stats();
    }
#endif

    if (HAL::USB_IsMassStorageOnSD() && HAL::USB_IsPlugged())
    {
        LV_LOG_WARN("LiveMap exits: USB MSC is using SD card storage");
        _Manager->Pop();
        return;
    }

    uint32_t now = lv_tick_get();
    bool mapUpdateEnabled = true;

    if (priv.nextMapUpdateTime != 0)
    {
        if (TickReached(now, priv.nextMapUpdateTime))
        {
            priv.nextMapUpdateTime = 0;
        }
        else
        {
            mapUpdateEnabled = false;
        }
    }

    if (mapUpdateEnabled && lv_tick_elaps(priv.lastMapUpdateTime) >= CONFIG_LIVE_MAP_REFR_PERIOD)
    {
        CheckPosition();
        priv.lastMapUpdateTime = now;
    }

    if (lv_tick_elaps(priv.lastSportUpdateTime) >= 1000)
    {
        SportInfoUpdate();
        priv.lastSportUpdateTime = lv_tick_get();
    }

    if (lv_tick_elaps(priv.lastNavigationUpdateTime) >= 500)
    {
        NavigationBannerUpdate();
        priv.lastNavigationUpdateTime = lv_tick_get();
    }

    if (!priv.zoomCtrlHidden && lv_tick_elaps(priv.lastContShowTime) >= 3000)
    {
        lv_obj_add_state(View.ui.zoom.cont, LV_STATE_USER_1);
        priv.zoomCtrlHidden = true;
    }
}

void LiveMap::UpdateDelay(uint32_t ms)
{
    priv.nextMapUpdateTime = lv_tick_get() + ms;
}

void LiveMap::SportInfoUpdate()
{
    int speed = (int)Model.sportStatusInfo.speedKph;
    if (!priv.sportInfoValid || speed != priv.lastSportSpeed)
    {
        lv_label_set_text_fmt(
            View.ui.sportInfo.labelSpeed,
            "%02d",
            speed
        );
        priv.lastSportSpeed = speed;
    }

    int32_t tripDeciKm = (int32_t)((Model.sportStatusInfo.singleDistance + 50.0f) / 100.0f);
    if (!priv.sportInfoValid || tripDeciKm != priv.lastSportTripDeciKm)
    {
        lv_label_set_text_fmt(
            View.ui.sportInfo.labelTrip,
            "%d.%d km",
            (int)(tripDeciKm / 10),
            (int)(tripDeciKm % 10)
        );
        priv.lastSportTripDeciKm = tripDeciKm;
    }

    uint32_t timeSec = (uint32_t)(Model.sportStatusInfo.singleTime / 1000);
    if (!priv.sportInfoValid || timeSec != priv.lastSportTimeSec)
    {
        char buf[16];
        lv_label_set_text(
            View.ui.sportInfo.labelTime,
            DataProc::MakeTimeString((uint64_t)timeSec * 1000, buf, sizeof(buf))
        );
        priv.lastSportTimeSec = timeSec;
    }

    priv.sportInfoValid = true;
}

static const char* NavigationTurnIcon(DataProc::Navigation_TurnType_t turnType)
{
    switch (turnType)
    {
    case DataProc::NAV_TURN_LEFT:
    case DataProc::NAV_TURN_SHARP_LEFT:
        return ICON_TURN_LEFT;
    case DataProc::NAV_TURN_RIGHT:
    case DataProc::NAV_TURN_SHARP_RIGHT:
        return ICON_TURN_RIGHT;
    case DataProc::NAV_TURN_UTURN:
    case DataProc::NAV_TURN_REVERSE:
        return ICON_TURN_UTURN;
    default:
        return ICON_TURN_STRAIGHT;
    }
}

static const char* NavigationDefaultText(const DataProc::Navigation_Info_t* info)
{
    switch (info->routeStatus)
    {
    case DataProc::NAV_ROUTE_STATUS_SELECTED_UNVALIDATED:
    case DataProc::NAV_ROUTE_STATUS_VALIDATING:
        return TXT_NAV_READY;
    case DataProc::NAV_ROUTE_STATUS_IMPORTING:
        return TXT_NAV_IMPORTING;
    case DataProc::NAV_ROUTE_STATUS_INVALID:
        return TXT_NAV_INVALID;
    case DataProc::NAV_ROUTE_STATUS_ERROR:
        return TXT_NAV_ERROR;
    default:
        break;
    }

    if (!info->active)
    {
        return TXT_NAV_READY;
    }

    switch (info->state)
    {
    case DataProc::NAV_STATE_APPROACHING_ROUTE:
        return TXT_NAV_APPROACH;
    case DataProc::NAV_STATE_OFF_ROUTE:
        return TXT_NAV_OFF_ROUTE;
    case DataProc::NAV_STATE_REVERSE_DIRECTION:
        return TXT_NAV_REVERSE;
    case DataProc::NAV_STATE_FINISHED:
        return TXT_NAV_FINISH;
    case DataProc::NAV_STATE_ERROR:
        return TXT_NAV_ERROR;
    default:
        break;
    }

    switch (info->turnType)
    {
    case DataProc::NAV_TURN_LEFT:
        return TXT_NAV_LEFT;
    case DataProc::NAV_TURN_RIGHT:
        return TXT_NAV_RIGHT;
    case DataProc::NAV_TURN_SHARP_LEFT:
        return TXT_NAV_SHARP_LEFT;
    case DataProc::NAV_TURN_SHARP_RIGHT:
        return TXT_NAV_SHARP_RIGHT;
    case DataProc::NAV_TURN_UTURN:
        return TXT_NAV_UTURN;
    case DataProc::NAV_TURN_FINISH:
        return TXT_NAV_FINISH;
    default:
        return TXT_NAV_STRAIGHT;
    }
}

void LiveMap::NavigationBannerUpdate()
{
    DataProc::Navigation_Info_t info;
    if (!Model.GetNavigationInfo(&info))
    {
        if (priv.navBannerVisible)
        {
            View.SetNavigationBannerVisible(false);
            priv.navBannerVisible = false;
        }
        priv.navInfoValid = false;
        return;
    }

    bool visible = (info.routeStatus != DataProc::NAV_ROUTE_STATUS_NO_ROUTE);
    if (!visible)
    {
        if (priv.navBannerVisible)
        {
            View.SetNavigationBannerVisible(false);
            priv.navBannerVisible = false;
        }
        priv.navInfoValid = true;
        priv.lastNavRevision = info.revision;
        priv.lastNavRouteStatus = info.routeStatus;
        if (priv.routeRenderValid)
        {
            View.RouteLineReset();
            priv.routeRenderValid = false;
            priv.routeRenderRevision = 0;
        }
        View.SetApproachLine(0, 0, 0, 0, false);
        return;
    }

    const char* text = NavigationDefaultText(&info);
    const char* icon = NavigationTurnIcon(info.turnType);
    uint32_t distanceM = info.distanceToTurnM;
    bool distanceValid = (info.active && distanceM > 0);

    bool changed = !priv.navInfoValid ||
                   !priv.navBannerVisible ||
                   priv.lastNavRevision != info.revision ||
                   priv.lastNavRouteStatus != info.routeStatus ||
                   priv.lastNavState != info.state ||
                   priv.lastNavTurnType != info.turnType ||
                   priv.lastNavDistanceM != distanceM ||
                   strcmp(priv.lastNavCueText, text) != 0;

    if (changed)
    {
        View.SetNavigationBanner(icon, text, distanceM, distanceValid);
        strncpy(priv.lastNavCueText, text, sizeof(priv.lastNavCueText));
        priv.lastNavCueText[sizeof(priv.lastNavCueText) - 1] = '\0';
        priv.lastNavRevision = info.revision;
        priv.lastNavRouteStatus = info.routeStatus;
        priv.lastNavState = info.state;
        priv.lastNavTurnType = info.turnType;
        priv.lastNavDistanceM = distanceM;
        priv.navInfoValid = true;
    }

    if (!priv.navBannerVisible)
    {
        View.SetNavigationBannerVisible(true);
        priv.navBannerVisible = true;
    }

    if (info.routeStatus == DataProc::NAV_ROUTE_STATUS_VALID)
    {
        if (!priv.routeRenderValid ||
            priv.routeRenderRevision != info.revision ||
            priv.routeRenderLevel != mapLevelCurrent)
        {
            RouteLineReload();
        }
    }
    else
    {
        if (priv.routeRenderValid)
        {
            View.RouteLineReset();
            priv.routeRenderValid = false;
            priv.routeRenderRevision = 0;
        }
        View.SetApproachLine(0, 0, 0, 0, false);
    }
}

void LiveMap::NavigationApproachLineUpdate(int32_t mapX, int32_t mapY)
{
    DataProc::Navigation_Info_t info;
    if (!Model.GetNavigationInfo(&info) ||
        !info.active ||
        info.routeStatus != DataProc::NAV_ROUTE_STATUS_VALID ||
        !info.approachTargetValid ||
        (info.state != DataProc::NAV_STATE_APPROACHING_ROUTE &&
         info.state != DataProc::NAV_STATE_OFF_ROUTE))
    {
        View.SetApproachLine(0, 0, 0, 0, false);
        return;
    }

    int32_t targetMapX = 0;
    int32_t targetMapY = 0;
    Model.mapConv.ConvertMapCoordinate(
        (double)info.approachTargetLonE7 / 10000000.0,
        (double)info.approachTargetLatE7 / 10000000.0,
        &targetMapX,
        &targetMapY
    );

    TileConv::Point_t fromOffset;
    TileConv::Point_t toOffset;
    TileConv::Point_t fromPoint = { mapX, mapY };
    TileConv::Point_t toPoint = { targetMapX, targetMapY };
    Model.tileConv.GetOffset(&fromOffset, &fromPoint);
    Model.tileConv.GetOffset(&toOffset, &toPoint);

    View.SetApproachLine(
        (lv_coord_t)fromOffset.x,
        (lv_coord_t)fromOffset.y,
        (lv_coord_t)toOffset.x,
        (lv_coord_t)toOffset.y,
        true
    );
}

void LiveMap::RouteLineReload()
{
    DataProc::Navigation_Info_t info;
    if (!Model.GetNavigationInfo(&info) ||
        info.routeStatus != DataProc::NAV_ROUTE_STATUS_VALID ||
        info.pointCount < 2)
    {
        View.RouteLineReset();
        priv.routeRenderValid = false;
        priv.routeRenderRevision = 0;
        return;
    }

    uint16_t stride = (uint16_t)((info.pointCount + ROUTE_RENDER_POINT_MAX - 1) / ROUTE_RENDER_POINT_MAX);
    if (stride == 0)
    {
        stride = 1;
    }

    DataProc::Navigation_RouteWindowQuery_t query;
    DATA_PROC_INIT_STRUCT(query);
    query.revision = info.revision;
    query.startIndex = 0;
    query.stride = stride;

    DataProc::Navigation_RouteWindowResult_t result;
    DATA_PROC_INIT_STRUCT(result);
    if (DataProc::Navigation_QueryRouteWindow(
            &query,
            priv.routeQueryPoints,
            ROUTE_RENDER_POINT_MAX,
            &result) == DataProc::NAV_ROUTE_WINDOW_ERROR ||
        result.written < 2)
    {
        View.RouteLineReset();
        priv.routeRenderValid = false;
        priv.routeRenderRevision = 0;
        return;
    }

    View.RouteLineReset();
    View.RouteLineStart();
    for (uint16_t i = 0; i < result.written; i++)
    {
        int32_t mapX = 0;
        int32_t mapY = 0;
        Model.mapConv.ConvertMapCoordinate(
            (double)priv.routeQueryPoints[i].lonE7 / 10000000.0,
            (double)priv.routeQueryPoints[i].latE7 / 10000000.0,
            &mapX,
            &mapY
        );

        TileConv::Point_t offset;
        TileConv::Point_t curPoint = { mapX, mapY };
        Model.tileConv.GetOffset(&offset, &curPoint);
        View.RouteLineAppend((lv_coord_t)offset.x, (lv_coord_t)offset.y);
    }
    View.RouteLineStop();

    priv.routeRenderValid = true;
    priv.routeRenderRevision = info.revision;
    priv.routeRenderLevel = mapLevelCurrent;
}

void LiveMap::CheckPosition()
{
    bool refreshMap = false;

    HAL::GPS_Info_t gpsInfo;
    Model.GetGPS_Info(&gpsInfo);

    mapLevelCurrent = lv_slider_get_value(View.ui.zoom.slider);
    if (mapLevelCurrent != Model.mapConv.GetLevel())
    {
        refreshMap = true;
        Model.mapConv.SetLevel(mapLevelCurrent);
#if CONFIG_LIVE_MAP_SNAPSHOT_ENABLE
        /* 坐标系随级别整体改变，快照内容全部作废 */
        snapshotValid = false;
#endif
    }

    int32_t mapX, mapY;
    Model.mapConv.ConvertMapCoordinate(
        gpsInfo.longitude, gpsInfo.latitude,
        &mapX, &mapY
    );

#if (!CONFIG_LIVE_MAP_RECENTER_ENABLE) && CONFIG_LIVE_MAP_SCROLL_INTERP_ENABLE
    /* 平滑滚动插值（8.8 定点）：显示坐标每周期向 GPS 目标坐标指数逼近。
     * 整像素快照直拷只能呈现 1px 步进；更细的步进只会触发无效整屏重绘。
     * 级别切换或首帧直接跳变到目标。 */
    const int32_t interpSnapFp = 256;   /* 1 px 吸附 */
    const int32_t interpMinStep = 256;  /* 最小步进 1 px */
    /* 定点坐标必须用 64 位:16 级全局像素坐标可达 1.3e7,<<8 后超出
     * int32 上限(2.1e9)溢出为负,曾致 16 级及以上整页填白(15 级
     * mapX≈6.6e6 恰在溢出线下,故"15 及以下正常"是溢出的指纹)。 */
    const int64_t targetXFp = (int64_t)mapX << 8;
    const int64_t targetYFp = (int64_t)mapY << 8;
    if (refreshMap || !priv.hasDispMap)
    {
        priv.dispMapXFp = targetXFp;
        priv.dispMapYFp = targetYFp;
        priv.hasDispMap = true;
    }
    else
    {
        int64_t remX = targetXFp - priv.dispMapXFp;
        int64_t remY = targetYFp - priv.dispMapYFp;
        int64_t absRemX = remX < 0 ? -remX : remX;
        int64_t absRemY = remY < 0 ? -remY : remY;

        if (absRemX <= interpSnapFp && absRemY <= interpSnapFp)
        {
            priv.dispMapXFp = targetXFp;
            priv.dispMapYFp = targetYFp;
        }
        else
        {
            /* 每周期逼近剩余 1/DIV，且每轴至少推进最小步进保证收敛 */
            int64_t stepX = remX / CONFIG_LIVE_MAP_SCROLL_INTERP_DIV;
            int64_t stepY = remY / CONFIG_LIVE_MAP_SCROLL_INTERP_DIV;
            if (stepX > -interpMinStep && stepX < interpMinStep && remX != 0)
                stepX = (remX > 0) ? interpMinStep : -interpMinStep;
            if (stepY > -interpMinStep && stepY < interpMinStep && remY != 0)
                stepY = (remY > 0) ? interpMinStep : -interpMinStep;
            priv.dispMapXFp += stepX;
            priv.dispMapYFp += stepY;
        }
    }
    /* 整数部分驱动坐标系（>>8 为 floor，负坐标下相位仍落在 [0,256)） */
    const int32_t dispX = (int32_t)(priv.dispMapXFp >> 8);
    const int32_t dispY = (int32_t)(priv.dispMapYFp >> 8);
    const bool interpSettled = (priv.dispMapXFp == targetXFp &&
                                priv.dispMapYFp == targetYFp);
#else
    /* 未启用插值：显示坐标即真实坐标 */
    const int32_t dispX = mapX;
    const int32_t dispY = mapY;
    const bool interpSettled = true;
#endif

    Model.tileConv.SetFocusPos(dispX, dispY);

    if (GetIsMapTileContChanged())
    {
        refreshMap = true;
    }

    int16_t courseAngle = (int16_t)(gpsInfo.course * 10);
    int16_t courseDiff = courseAngle - priv.lastCourseAngle;
    if (!refreshMap &&
        !priv.recentering &&
        priv.hasLastMapPoint &&
        mapX == priv.lastMapX &&
        mapY == priv.lastMapY &&
        interpSettled &&
        courseDiff >= -10 &&
        courseDiff <= 10)
    {
        return;
    }

    if (refreshMap)
    {
        TileConv::Rect_t rect;
        Model.tileConv.GetTileContainer(&rect);

        Area_t area =
        {
            .x0 = rect.x,
            .y0 = rect.y,
            .x1 = rect.x + rect.width - 1,
            .y1 = rect.y + rect.height - 1
        };

        onMapTileContRefresh(&area, dispX, dispY);
    }

#if CONFIG_LIVE_MAP_SNAPSHOT_ENABLE
#if (!CONFIG_LIVE_MAP_RECENTER_ENABLE) && CONFIG_LIVE_MAP_SCROLL_INTERP_ENABLE
    const uint16_t phaseXFp = (uint16_t)(priv.dispMapXFp & 0xFF);
    const uint16_t phaseYFp = (uint16_t)(priv.dispMapYFp & 0xFF);
#else
    const uint16_t phaseXFp = 0;
    const uint16_t phaseYFp = 0;
#endif
    Snapshot_Update(dispX, dispY, phaseXFp, phaseYFp, Model, View);
#endif
    MapTileContUpdate(dispX, dispY, gpsInfo.course, refreshMap);
    NavigationApproachLineUpdate(dispX, dispY);
    priv.lastMapX = mapX;
    priv.lastMapY = mapY;
    priv.lastCourseAngle = courseAngle;
    priv.hasLastMapPoint = true;

    if (priv.isTrackAvtive)
    {
        /* 轨迹记录必须使用真实 GPS 坐标，不受显示插值影响 */
        Model.pointFilter.PushPoint(mapX, mapY);
    }
}

void LiveMap::onMapTileContRefresh(const Area_t* area, int32_t x, int32_t y)
{
    priv.mapReloadCnt++;

    LV_LOG_INFO(
        "area: (%d, %d) [%dx%d]",
        area->x0, area->y0,
        area->x1 - area->x0 + 1,
        area->y1 - area->y0 + 1
    );

    MapTileContReload();

    /* Preload new tiles to cache after reload */
    MapTileContPreload();

    if (priv.isTrackAvtive)
    {
        TrackLineReload(area, x, y);
    }

    if (priv.routeRenderValid)
    {
        priv.routeRenderValid = false;
        RouteLineReload();
    }
}

void LiveMap::MapTileContUpdate(int32_t mapX, int32_t mapY, float course, bool forceRecenter)
{
    TileConv::Point_t offset;
    TileConv::Point_t curPoint = { mapX, mapY };
    Model.tileConv.GetOffset(&offset, &curPoint);

    /* arrow */
    lv_obj_t* img = View.ui.map.imgArrow;
    Model.tileConv.GetFocusOffset(&offset);
    lv_coord_t x = offset.x - lv_obj_get_width(img) / 2;
    lv_coord_t y = offset.y - lv_obj_get_height(img) / 2;
    View.SetImgArrowStatus(x, y, course);

    /* active line */
    if (priv.isTrackAvtive)
    {
        View.SetLineActivePoint((lv_coord_t)offset.x, (lv_coord_t)offset.y);
    }

    /* map cont —— 周期性 recenter：
     * centeredX/Y 是"让箭头回到屏幕中心"所需的容器位置。
     * 两次 recenter 之间容器保持在 priv.appliedCont 不动，箭头在静止地图上平滑移动；
     * 仅当箭头偏离中心超过阈值（或瓦片重载/首帧）时，才把容器移到 centered 位置，
     * 触发一次整屏重绘。 */
    Model.tileConv.GetTileContainerOffset(&offset);

    lv_coord_t baseX = (LV_HOR_RES - CONFIG_LIVE_MAP_VIEW_WIDTH) / 2;
    lv_coord_t baseY = (LV_VER_RES - CONFIG_LIVE_MAP_VIEW_HEIGHT) / 2;

    lv_coord_t centeredX = baseX - offset.x;
    lv_coord_t centeredY = baseY - offset.y;

#if CONFIG_LIVE_MAP_RECENTER_ENABLE
    /* 首帧或瓦片重载：直接吸附到位，避免加载瞬间出现滑动 */
    if (forceRecenter || !priv.hasContPos)
    {
        priv.appliedContX = centeredX;
        priv.appliedContY = centeredY;
        priv.hasContPos = true;
        priv.recentering = false;
    }
    else
    {
        /* 箭头相对屏幕中心的偏移量 = 当前容器位置 - 居中位置 */
        lv_coord_t driftX = priv.appliedContX - centeredX;
        lv_coord_t driftY = priv.appliedContY - centeredY;
        if (driftX < 0) driftX = -driftX;
        if (driftY < 0) driftY = -driftY;

        /* 静止（未在归位中）时，仅当偏离超过阈值才启动一次平滑归位 */
        if (!priv.recentering &&
            (driftX > CONFIG_LIVE_MAP_RECENTER_MARGIN ||
             driftY > CONFIG_LIVE_MAP_RECENTER_MARGIN))
        {
            priv.recentering = true;
        }

        if (priv.recentering)
        {
            lv_coord_t remX = centeredX - priv.appliedContX;
            lv_coord_t remY = centeredY - priv.appliedContY;
            lv_coord_t absRemX = remX < 0 ? -remX : remX;
            lv_coord_t absRemY = remY < 0 ? -remY : remY;

            if (absRemX <= CONFIG_LIVE_MAP_RECENTER_ANIM_SNAP &&
                absRemY <= CONFIG_LIVE_MAP_RECENTER_ANIM_SNAP)
            {
                /* 收尾：吸附到位并结束动画，回到静止省电状态 */
                priv.appliedContX = centeredX;
                priv.appliedContY = centeredY;
                priv.recentering = false;
            }
            else
            {
                /* 指数缓动：每周期向目标逼近 1/DIV，保证每轴至少推进 1px */
                lv_coord_t stepX = remX / CONFIG_LIVE_MAP_RECENTER_ANIM_DIV;
                lv_coord_t stepY = remY / CONFIG_LIVE_MAP_RECENTER_ANIM_DIV;
                if (stepX == 0 && remX != 0) stepX = (remX > 0) ? 1 : -1;
                if (stepY == 0 && remY != 0) stepY = (remY > 0) ? 1 : -1;
                priv.appliedContX += stepX;
                priv.appliedContY += stepY;
            }
        }
    }

    /* SetMapContPos 内部带缓存：位置不变时不会触发任何重绘 */
    View.SetMapContPos(priv.appliedContX, priv.appliedContY);
#else
    /* 原始实时渲染：箭头锁中心、地图每帧平滑滚动（每帧整屏重绘） */
    (void)forceRecenter;
    View.SetMapContPos(centeredX, centeredY);
#endif
}

void LiveMap::MapTileContReload()
{
    /* tile src */
    for (uint32_t i = 0; i < View.ui.map.tileNum; i++)
    {
        TileConv::Point_t pos;
        Model.tileConv.GetTilePos(i, &pos);

        char path[64];
        Model.mapConv.ConvertMapPath(pos.x, pos.y, path, sizeof(path));

        View.SetMapTileSrc(i, path);
    }
}

void LiveMap::MapTileContPreload()
{
    /* Preload map tiles to LVGL image cache to improve rendering performance */
    LV_LOG_INFO("Preloading map tiles to cache...");

    for (uint32_t i = 0; i < View.ui.map.tileNum; i++)
    {
        TileConv::Point_t pos;
        Model.tileConv.GetTilePos(i, &pos);

        char path[64];
        Model.mapConv.ConvertMapPath(pos.x, pos.y, path, sizeof(path));

        /* Preload image to cache using internal LVGL cache API */
        _lv_img_cache_open(path, lv_color_white(), 0);
    }

    LV_LOG_INFO("Map tiles preloaded, cache ready");
}

bool LiveMap::GetIsMapTileContChanged()
{
    TileConv::Point_t pos;
    Model.tileConv.GetTilePos(0, &pos);

    bool ret = (pos.x != priv.lastTileContOriPoint.x || pos.y != priv.lastTileContOriPoint.y);

    priv.lastTileContOriPoint = pos;

    return ret;
}

void LiveMap::TrackLineReload(const Area_t* area, int32_t x, int32_t y)
{
    Model.lineFilter.SetClipArea(area);
    Model.lineFilter.Reset();
    Model.TrackReload([](TrackPointFilter * filter, const TrackPointFilter::Point_t* point)
    {
        LiveMap* instance = (LiveMap*)filter->userData;
        instance->Model.lineFilter.PushPoint((int32_t)point->x, (int32_t)point->y);
    }, this);
    Model.lineFilter.PushPoint(x, y);
    Model.lineFilter.PushEnd();
}

void LiveMap::TrackLineAppend(int32_t x, int32_t y)
{
    TileConv::Point_t offset;
    TileConv::Point_t curPoint = { x, y };
    Model.tileConv.GetOffset(&offset, &curPoint);
    View.ui.track.lineTrack->append((lv_coord_t)offset.x, (lv_coord_t)offset.y);
}

void LiveMap::TrackLineAppendToEnd(int32_t x, int32_t y)
{
    TileConv::Point_t offset;
    TileConv::Point_t curPoint = { x, y };
    Model.tileConv.GetOffset(&offset, &curPoint);
    View.ui.track.lineTrack->append_to_end((lv_coord_t)offset.x, (lv_coord_t)offset.y);
}

void LiveMap::onTrackLineEvent(TrackLineFilter* filter, TrackLineFilter::Event_t* event)
{
    LiveMap* instance = (LiveMap*)filter->userData;
    lv_poly_line* lineTrack = instance->View.ui.track.lineTrack;

    switch (event->code)
    {
    case TrackLineFilter::EVENT_START_LINE:
        lineTrack->start();
        instance->TrackLineAppend(event->point->x, event->point->y);
        break;
    case TrackLineFilter::EVENT_APPEND_POINT:
        instance->TrackLineAppend(event->point->x, event->point->y);
        break;
    case TrackLineFilter::EVENT_END_LINE:
        if (event->point != nullptr)
        {
            instance->TrackLineAppend(event->point->x, event->point->y);
        }
        lineTrack->stop();
        break;
    case TrackLineFilter::EVENT_RESET:
        lineTrack->reset();
        break;
    default:
        break;
    }
}

void LiveMap::onEvent(lv_event_t* event)
{
    LiveMap* instance = (LiveMap*)lv_event_get_user_data(event);
    LV_ASSERT_NULL(instance);

    lv_obj_t* obj = lv_event_get_current_target(event);
    lv_event_code_t code = lv_event_get_code(event);

    if (code == LV_EVENT_LEAVE)
    {
        instance->_Manager->Pop();
        return;
    }

    if (code == LV_EVENT_GESTURE)
    {
        lv_indev_t* indev = lv_indev_get_act();
        lv_dir_t dir = lv_indev_get_gesture_dir(indev);

        if (dir == LV_DIR_LEFT || dir == LV_DIR_RIGHT)
        {
            instance->_Manager->Pop();
        }
        return;
    }

    if (obj == instance->View.ui.zoom.slider)
    {
        if (code == LV_EVENT_VALUE_CHANGED)
        {
            int32_t level = lv_slider_get_value(obj);
            int32_t levelMax = instance->Model.mapConv.GetLevelMax();
            lv_label_set_text_fmt(instance->View.ui.zoom.labelInfo, "%d/%d", level, levelMax);

            lv_obj_clear_state(instance->View.ui.zoom.cont, LV_STATE_USER_1);
            instance->priv.zoomCtrlHidden = false;
            instance->priv.lastContShowTime = lv_tick_get();
            instance->UpdateDelay(200);
        }
        else if (code == LV_EVENT_PRESSED)
        {
            instance->_Manager->Pop();
        }
    }

    if (obj == instance->View.ui.sportInfo.cont)
    {
        if (code == LV_EVENT_PRESSED)
        {
            instance->_Manager->Pop();
        }
    }
}
