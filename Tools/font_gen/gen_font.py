#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LVGL 中文子集字库一键生成脚本（配置驱动 + 增量累积去重）。

功能：
  1. 读取 JSON 配置（需要的中文字符、字号、bpp、输出路径等），调用 lv_font_conv
     生成 LVGL 可直接使用的 .c 文件。
  2. 若目标 .c 已存在：把它已包含的字符与配置中的新字符【合并去重】后整体重新生成，
     实现“增量添加”——既保留旧字，又并入新字，重复字符自动去重。
  3. 维护边车文件 <output>.chars（UTF-8，记录已累计的非 ASCII 字符集），作为最可靠的
     累积来源；缺失时回退到解析 .c 里的 /* U+XXXX */ 注释恢复字符集。
  4. 码点经 lv_font_conv 的 --range 传入（不在命令行直接传中文），规避 Windows 命令行
     中文编码问题。输出按码点排序，保证可复现、git 友好。

用法：
  python gen_font.py [config.json]      # 生成/更新配置里的全部字库（默认 ./font_config.json）
  python gen_font.py --cstr "无法进入地图"
                                        # 打印 AC5(armcc) 安全的 UTF-8 \\xNN C 字符串字面量

依赖：node + npx（首次联网拉取 lv_font_conv），或本机已安装的 lv_font_conv。
重置某字库：删除其 .c 与同名 .chars 边车文件后再运行即可从零生成。
"""

import sys
import os
import re
import json
import shutil
import subprocess

# lv_font_conv 调用方式：默认用 npx 拉取指定版本；也可改为本机已装的 ["lv_font_conv"]。
LV_FONT_CONV = ["npx", "--yes", "lv_font_conv@1.5.3"]


def to_cstr(text):
    """把字符串转为 AC5(armcc) 安全的 C 字面量：
    每个字符输出为相邻字符串字面量，ASCII 用原字符，非 ASCII 用 UTF-8 \\xNN 字节。
    相邻字面量自动拼接，且 \\xNN 后紧跟引号，杜绝十六进制转义贪婪吞并后续字符。"""
    parts = []
    for ch in text:
        o = ord(ch)
        if o < 0x80:
            if ch == '\\':
                parts.append('"\\\\"')
            elif ch == '"':
                parts.append('"\\""')
            else:
                parts.append('"%s"' % ch)
        else:
            parts.append('"' + ''.join('\\x%02X' % b for b in ch.encode('utf-8')) + '"')
    return ' '.join(parts) if parts else '""'


def resolve_path(p, base_dir):
    """相对路径按配置文件所在目录解析，绝对路径原样返回。"""
    if not p:
        return p
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base_dir, p))


def sidecar_path(c_path):
    """字符集边车文件路径：与 .c 同名追加 .chars。"""
    return c_path + ".chars"


def parse_codepoints_from_c(c_path):
    """从已生成的 .c 中解析 /* U+XXXX */ 注释，恢复其包含的码点集合。"""
    cps = set()
    if os.path.isfile(c_path):
        with open(c_path, encoding="utf-8", errors="ignore") as f:
            for m in re.finditer(r"U\+([0-9A-Fa-f]{2,6})", f.read()):
                cps.add(int(m.group(1), 16))
    return cps


def load_accumulated_symbols(c_path):
    """读取已累计的【非 ASCII】字符集合（ASCII 由 --range 统一处理，不入累积集）。
    优先读边车 .chars；缺失则回退解析 .c。"""
    chars = set()
    sc = sidecar_path(c_path)
    if os.path.isfile(sc):
        with open(sc, encoding="utf-8") as f:
            for ch in f.read():
                if not ch.isspace() and ord(ch) >= 0x80:
                    chars.add(ch)
    else:
        for cp in parse_codepoints_from_c(c_path):
            if cp >= 0x80:
                chars.add(chr(cp))
    return chars


def save_accumulated_symbols(c_path, symbols):
    """把累计字符集（按码点排序）写回边车文件。"""
    with open(sidecar_path(c_path), "w", encoding="utf-8") as f:
        f.write("".join(sorted(symbols, key=ord)))


def build_range_args(symbols, include_ascii):
    """构造 lv_font_conv 的 --range 参数列表：ASCII 用 0x20-0x7E，其余用码点逗号列表。"""
    ranges = []
    if include_ascii:
        ranges.append("0x20-0x7E")
    cps = sorted(ord(c) for c in symbols if ord(c) >= 0x80)
    if cps:
        ranges.append(",".join("0x%04X" % cp for cp in cps))
    return ranges


def run_lv_font_conv(extra_args):
    """跨平台调用 lv_font_conv（Windows 下经 cmd /c 运行 npx.cmd）。"""
    args = list(LV_FONT_CONV) + extra_args
    if os.name == "nt":
        exe = shutil.which(args[0]) or args[0]
        if exe.lower().endswith((".cmd", ".bat")):
            args = ["cmd", "/c", exe] + args[1:]
        else:
            args[0] = exe
    subprocess.run(args, check=True)


def symbol_name(c_path):
    """LVGL 字库符号名 = 输出文件基名（不含扩展名），与 lv_font_conv 行为一致。"""
    return os.path.splitext(os.path.basename(c_path))[0]


def gen_one(spec, base_dir, default_ttf):
    ttf = resolve_path(spec.get("ttf") or default_ttf, base_dir)
    out = resolve_path(spec["output"], base_dir)
    size = int(spec["size"])
    bpp = int(spec.get("bpp", 4))
    include_ascii = bool(spec.get("include_ascii", True))
    new_chars = set(c for c in spec.get("chars", "") if not c.isspace() and ord(c) >= 0x80)

    if not ttf or not os.path.isfile(ttf):
        raise FileNotFoundError("TTF 字体不存在：%s" % ttf)

    name = symbol_name(out)
    existing = load_accumulated_symbols(out)
    symbols = existing | new_chars            # 合并
    added = symbols - existing                # 本次新增（去重后）

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    ranges = build_range_args(symbols, include_ascii)

    extra = ["--font", ttf, "--size", str(size), "--bpp", str(bpp),
             "--format", "lvgl", "--no-compress", "--no-kerning"]
    for r in ranges:
        extra += ["--range", r]
    extra += ["-o", out]

    print("[字库] %s  size=%d bpp=%d ascii=%s" % (name, size, bpp, include_ascii))
    print("       非ASCII字形=%d（本次新增 %d），输出=%s" % (len(symbols), len(added), out))
    run_lv_font_conv(extra)
    save_accumulated_symbols(out, symbols)
    return name, out


def main():
    argv = sys.argv[1:]

    # 子命令：把一段文字转成 AC5 安全的 C 字面量，便于在源码里写中文 UI
    if argv and argv[0] == "--cstr":
        text = " ".join(argv[1:])
        print(to_cstr(text))
        return 0

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = resolve_path(argv[0], os.getcwd()) if argv else os.path.join(script_dir, "font_config.json")
    if not os.path.isfile(cfg_path):
        print("找不到配置文件：%s" % cfg_path)
        return 2

    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)

    base_dir = os.path.dirname(os.path.abspath(cfg_path))
    default_ttf = cfg.get("ttf")
    fonts = cfg.get("fonts")
    if fonts is None:
        fonts = [cfg]  # 允许配置直接是单个字库规格

    results = []
    for spec in fonts:
        results.append(gen_one(spec, base_dir, default_ttf))

    # 集成提示：回答“LVGL 使用前还需声明什么”
    print("\n==================== 集成到 LVGL（务必三步） ====================")
    for name, out in results:
        print("· 字库 %s  ->  %s" % (name, out))
    print("1) 声明（在使用处或公共头文件中）：")
    for name, _ in results:
        print("     LV_FONT_DECLARE(%s);" % name)
    print("2) 应用到控件/样式：")
    print("     lv_obj_set_style_text_font(label, &%s, 0);" % results[0][0])
    print("     // 或  lv_style_set_text_font(&style, &%s);" % results[0][0])
    print("3) 把生成的 .c 加入编译（Keil: 右键 Resource/Font 组 -> Add Existing Files）。")
    print("   注意：只声明不编译会链接报“未定义”。")
    print("提示：本工程为 ARMCC(AC5)，源码里的中文请用 \\xNN 转义，可用：")
    print("     python %s --cstr \"你的中文\"" % os.path.basename(__file__))
    print("     并确认 lv_conf.h 中 LV_TXT_ENC == LV_TXT_ENC_UTF8（默认）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
