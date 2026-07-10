#include "StartUpView.h"

using namespace Page;

/* ============================================================================
 * 开机动画：1:1 复刻 UI/电路.html —— 8 条曼哈顿折线走线(坐标按 800x500 → 设备 0.3 缩放)，
 * 彩色辉光条(dash)沿折线流动并随转角改变朝向，汇入中央芯片；其后 E-Track 像素艺术字
 * 逐列点亮 + 青色扫描线。
 *
 * 安全实现：全部用真实 lv_obj 矩形/标签对象 + anim_timeline。走线和光条保持纯矩形，
 * 不使用 shadow/mask/lv_draw 等复杂绘制路径。流动用自定义 anim 回调 PulseExec——它只调用
 * lv_obj_set_pos/set_size 移动与改朝向(非 LV_EVENT_DRAW_POST 自绘，安全)。像素字揭示用
 * “容器宽度裁剪”。不使用自绘回调/刷新定时器。
 * ==========================================================================*/

namespace
{

static const uint32_t COL_BG     = 0x061114;
static const uint32_t COL_TRACE  = 0x2a2a2a;   /* 走线暗底(HTML #333) */
static const uint32_t COL_CHIP   = 0x123038;
static const uint32_t COL_BORDER = 0x00ccff;
static const uint32_t COL_PIN    = 0x7fdfe8;
static const uint32_t COL_LIT    = 0x9eff00;
static const uint32_t COL_SCAN   = 0x00ccff;

static const lv_coord_t DASH_LEN = 16;         /* 流动长条长度 */
static const lv_coord_t TRACE_THICKNESS = 2;   /* 对应原 SVG stroke-width 1.8 */

/* —— 8 条走线(电路.html 精确坐标 × 0.3 + 偏移；起点 x 各不相同)—— */
struct Trace
{
    lv_point_t p[4];
    uint32_t flowColor;   /* 移动光条/端点颜色：8 条互不相同 */
};
static const Trace TR[8] =
{
    /* 左 4：起点 x=32/26/20/32（对应 HTML 100/80/60/100）汇入芯片左缘 x=80 */
    {{{ 32, 83}, { 62, 83}, { 62,116}, { 80,116}}, 0xff40ff},   /* magenta */
    {{{ 26,107}, { 56,107}, { 56,122}, { 80,122}}, 0x00ffff},   /* cyan */
    {{{ 20,131}, { 47,131}, { 47,128}, { 80,128}}, 0xffff00},   /* yellow */
    {{{ 32,158}, { 62,158}, { 62,134}, { 80,134}}, 0x00ff3c},   /* green */
    /* 右 4：起点 x=212/224/218/206（对应 HTML 700/740/720/680）汇入芯片右缘 x=164 */
    {{{212, 80}, {170, 80}, {170,116}, {164,116}}, 0x0096ff},   /* blue */
    {{{224,101}, {176,101}, {176,122}, {164,122}}, 0xbaff00},   /* chartreuse */
    {{{218,128}, {179,128}, {179,128}, {164,128}}, 0xff2400},   /* red */
    {{{206,155}, {173,155}, {173,134}, {164,134}}, 0xffa000},   /* amber */
};

/* —— 中央芯片(放大以容下 "Loading"，居中于原 1:1 位置)—— */
static const lv_coord_t CHIP_X = 80, CHIP_Y = 103, CHIP_W = 84, CHIP_H = 44;

struct PulseState
{
    lv_obj_t* obj;
    uint8_t traceIndex;
};
static PulseState PULSES[8];

/* —— E-Track 像素字模 —— */
static const uint16_t BRAND_GLYPHS[] =
{
    0xF800, 0x8000, 0x8000, 0xF000, 0x8000, 0x8000, 0xF800, /* E */
    0x0000, 0x0000, 0x0000, 0xF800, 0x0000, 0x0000, 0x0000, /* - */
    0xF800, 0x2000, 0x2000, 0x2000, 0x2000, 0x2000, 0x2000, /* T */
    0x0000, 0x0000, 0xB000, 0xC800, 0x8000, 0x8000, 0x8000, /* r */
    0x0000, 0x0000, 0x7000, 0x0800, 0x7800, 0x8800, 0x7800, /* a */
    0x0000, 0x0000, 0x7800, 0x8000, 0x8000, 0x8000, 0x7800, /* c */
    0x8000, 0x8800, 0x9000, 0xE000, 0x9000, 0x8800, 0x8400, /* k */
};
static const lv_coord_t CELL = 5, GLYPH_W = 5, GLYPH_H = 7, GAP = 1, GLYPH_NUM = 7;
static const lv_coord_t LOGO_W = (GLYPH_NUM * GLYPH_W + (GLYPH_NUM - 1) * GAP) * CELL;
static const lv_coord_t LOGO_H = GLYPH_H * CELL;
static const lv_coord_t LOGO_X = (240 - LOGO_W) / 2;
static const lv_coord_t LOGO_Y = 205;

static lv_obj_t* MakeRect(lv_obj_t* par, lv_coord_t x, lv_coord_t y,
                          lv_coord_t w, lv_coord_t h, uint32_t color,
                          lv_opa_t opa = LV_OPA_COVER)
{
    lv_obj_t* o = lv_obj_create(par);
    if(o == nullptr) return nullptr;
    lv_obj_remove_style_all(o);
    lv_obj_clear_flag(o, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(o, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_pos(o, x, y);
    lv_obj_set_size(o, w, h);
    lv_obj_set_style_bg_color(o, lv_color_hex(color), 0);
    lv_obj_set_style_bg_opa(o, opa, 0);
    return o;
}

static void MakeSeg(lv_obj_t* par, const lv_point_t* a, const lv_point_t* b, uint32_t color,
                    lv_opa_t opa = LV_OPA_60)
{
    if(a->y == b->y)
    {
        lv_coord_t x0 = LV_MIN(a->x, b->x), x1 = LV_MAX(a->x, b->x);
        MakeRect(par, x0, (lv_coord_t)(a->y - 1), (lv_coord_t)(x1 - x0 + 2), 2, color, opa);
    }
    else
    {
        lv_coord_t y0 = LV_MIN(a->y, b->y), y1 = LV_MAX(a->y, b->y);
        MakeRect(par, (lv_coord_t)(a->x - 1), y0, 2, (lv_coord_t)(y1 - y0 + 2), color, opa);
    }
}

static void SetPulseGeometry(PulseState* pulse, lv_coord_t cx, lv_coord_t cy, bool horizontal)
{
    if(pulse == nullptr || pulse->obj == nullptr)
    {
        return;
    }

    if(horizontal)
    {
        lv_obj_set_size(pulse->obj, DASH_LEN, TRACE_THICKNESS);
        lv_obj_set_pos(pulse->obj,
                       (lv_coord_t)(cx - DASH_LEN / 2),
                       (lv_coord_t)(cy - TRACE_THICKNESS / 2));
    }
    else
    {
        lv_obj_set_size(pulse->obj, TRACE_THICKNESS, DASH_LEN);
        lv_obj_set_pos(pulse->obj,
                       (lv_coord_t)(cx - TRACE_THICKNESS / 2),
                       (lv_coord_t)(cy - DASH_LEN / 2));
    }
}

/* 自定义 anim 回调：prog 0..1000 → 沿该 dash 所属走线 H-V-H 折线流动，随段改朝向 */
static void PulseExec(void* var, int32_t prog)
{
    PulseState* p = (PulseState*)var;
    int idx = p ? p->traceIndex : 0;
    const Trace* t = &TR[idx];

    int32_t len[3], total = 0;
    for(int s = 0; s < 3; s++)
    {
        int32_t dx = t->p[s + 1].x - t->p[s].x, dy = t->p[s + 1].y - t->p[s].y;
        len[s] = (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy);
        total += len[s];
    }
    int32_t d = total * prog / 1000;

    int seg = 0;
    while(seg < 2 && d > len[seg]) { d -= len[seg]; seg++; }
    const lv_point_t* a = &t->p[seg];
    const lv_point_t* b = &t->p[seg + 1];

    if(a->y == b->y)   /* 水平段：横条 */
    {
        lv_coord_t cx = (lv_coord_t)(a->x + (b->x > a->x ? d : -d));
        SetPulseGeometry(p, cx, a->y, true);
    }
    else               /* 垂直段：竖条 */
    {
        lv_coord_t cy = (lv_coord_t)(a->y + (b->y > a->y ? d : -d));
        SetPulseGeometry(p, a->x, cy, false);
    }
}

} // namespace

StartupView::StartupView()
{
    ui.cont = nullptr;
    ui.labelLogo = nullptr;
    ui.anim_timeline = nullptr;
}

void StartupView::Create(lv_obj_t* root)
{
    if(root == nullptr)
    {
        return;
    }

    lv_obj_set_style_bg_color(root, lv_color_hex(COL_BG), 0);
    lv_obj_set_style_bg_opa(root, LV_OPA_COVER, 0);

    ui.anim_timeline = lv_anim_timeline_create();
    if(ui.anim_timeline == nullptr)
    {
        return;
    }

    /* —— 走线暗底 + 起点端点 + 流动长条 —— */
    for(int i = 0; i < 8; i++)
    {
        const Trace* t = &TR[i];
        MakeSeg(root, &t->p[0], &t->p[1], COL_TRACE);
        MakeSeg(root, &t->p[1], &t->p[2], COL_TRACE);
        MakeSeg(root, &t->p[2], &t->p[3], COL_TRACE);
        MakeRect(root, (lv_coord_t)(t->p[0].x - 2), (lv_coord_t)(t->p[0].y - 2), 5, 5, t->flowColor);

        PULSES[i].traceIndex = (uint8_t)i;
        PULSES[i].obj = MakeRect(root,
                                 (lv_coord_t)(t->p[0].x - DASH_LEN / 2),
                                 (lv_coord_t)(t->p[0].y - TRACE_THICKNESS / 2),
                                 DASH_LEN,
                                 TRACE_THICKNESS,
                                 t->flowColor,
                                 LV_OPA_COVER);
        if(PULSES[i].obj == nullptr)
        {
            continue;
        }

        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, &PULSES[i]);
        lv_anim_set_exec_cb(&a, PulseExec);
        lv_anim_set_values(&a, 0, 1000);
        lv_anim_set_time(&a, STARTUP_PULSE_TIME);
        lv_anim_set_path_cb(&a, lv_anim_path_linear);
        lv_anim_set_early_apply(&a, true);
        if(ui.anim_timeline)
        {
            lv_anim_timeline_add(ui.anim_timeline, (uint32_t)(i * STARTUP_PULSE_STAGGER), &a);
        }
    }

    /* —— 芯片 + 引脚 + "Loading" —— */
    lv_obj_t* chip = lv_obj_create(root);
    if(chip == nullptr)
    {
        return;
    }
    lv_obj_remove_style_all(chip);
    lv_obj_clear_flag(chip, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(chip, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_pos(chip, CHIP_X, CHIP_Y);
    lv_obj_set_size(chip, CHIP_W, CHIP_H);
    lv_obj_set_style_radius(chip, 5, 0);
    lv_obj_set_style_bg_color(chip, lv_color_hex(COL_CHIP), 0);
    lv_obj_set_style_bg_opa(chip, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(chip, lv_color_hex(COL_BORDER), 0);
    lv_obj_set_style_border_width(chip, 2, 0);
    lv_obj_set_style_border_opa(chip, LV_OPA_COVER, 0);

    const lv_coord_t pinY[4] = { 116, 122, 128, 134 };
    for(int i = 0; i < 4; i++)
    {
        MakeRect(root, (lv_coord_t)(CHIP_X - 4), (lv_coord_t)(pinY[i] - 1), 4, 3, COL_PIN);
        MakeRect(root, (lv_coord_t)(CHIP_X + CHIP_W), (lv_coord_t)(pinY[i] - 1), 4, 3, COL_PIN);
    }

    lv_obj_t* loading = lv_label_create(chip);
    if(loading)
    {
        lv_obj_set_style_text_font(loading, ResourcePool::GetFont("bahnschrift_13"), 0);
        lv_obj_set_style_text_color(loading, lv_color_hex(0xe9fbff), 0);
        lv_label_set_text(loading, "Loading");
        lv_obj_center(loading);
    }

    /* —— E-Track 像素艺术字：裁剪容器(初始宽 0)内点亮像素(同行连续格合并横条) —— */
    lv_obj_t* cont = lv_obj_create(root);
    if(cont == nullptr)
    {
        return;
    }
    lv_obj_remove_style_all(cont);
    lv_obj_clear_flag(cont, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(cont, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_pos(cont, LOGO_X, LOGO_Y);
    lv_obj_set_size(cont, 0, LOGO_H);
    ui.cont = cont;

    for(lv_coord_t g = 0; g < GLYPH_NUM; g++)
    {
        lv_coord_t glyphX = g * (GLYPH_W + GAP) * CELL;
        for(lv_coord_t r = 0; r < GLYPH_H; r++)
        {
            uint16_t bits = BRAND_GLYPHS[g * GLYPH_H + r];
            lv_coord_t c = 0;
            while(c < GLYPH_W)
            {
                if(bits & (uint16_t)(0x8000 >> c))
                {
                    lv_coord_t c0 = c;
                    while(c < GLYPH_W && (bits & (uint16_t)(0x8000 >> c))) c++;
                    MakeRect(cont, (lv_coord_t)(glyphX + c0 * CELL), (lv_coord_t)(r * CELL),
                             (lv_coord_t)((c - c0) * CELL - 1), (lv_coord_t)(CELL - 1), COL_LIT);
                }
                else c++;
            }
        }
    }

    lv_obj_t* scan = MakeRect(root, LOGO_X, (lv_coord_t)(LOGO_Y - 3), 3, (lv_coord_t)(LOGO_H + 6), COL_SCAN);
    ui.labelLogo = scan;
    if(ui.labelLogo == nullptr)
    {
        return;
    }

    {
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, ui.cont);
        lv_anim_set_exec_cb(&a, (lv_anim_exec_xcb_t)lv_obj_set_width);
        lv_anim_set_values(&a, 0, LOGO_W);
        lv_anim_set_time(&a, STARTUP_ANIM_TOTAL);
        lv_anim_set_path_cb(&a, lv_anim_path_ease_out);
        lv_anim_set_early_apply(&a, true);
        lv_anim_timeline_add(ui.anim_timeline, 0, &a);
    }
    {
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, ui.labelLogo);
        lv_anim_set_exec_cb(&a, (lv_anim_exec_xcb_t)lv_obj_set_x);
        lv_anim_set_values(&a, LOGO_X, (lv_coord_t)(LOGO_X + LOGO_W));
        lv_anim_set_time(&a, STARTUP_ANIM_TOTAL);
        lv_anim_set_path_cb(&a, lv_anim_path_ease_out);
        lv_anim_set_early_apply(&a, true);
        lv_anim_timeline_add(ui.anim_timeline, 0, &a);
    }
}

void StartupView::Delete()
{
    if(ui.anim_timeline)
    {
        lv_anim_timeline_del(ui.anim_timeline);
        ui.anim_timeline = nullptr;
    }
}
