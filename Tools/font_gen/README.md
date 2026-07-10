# LVGL 中文子集字库生成器

配置驱动的一键脚本：读取 `font_config.json`（需要的中文字符 + 字号等），调用
[`lv_font_conv`](https://github.com/lvgl/lv_font_conv) 生成 LVGL 可直接使用的 `.c` 字库。
支持**增量累积去重**：目标 `.c` 已存在时，把旧字符与新字符合并去重后整体重生成。

## 依赖
- Node.js（提供 `npx`）。脚本默认用 `npx --yes lv_font_conv@1.5.3`，首次需联网拉取；
  若已全局安装，可把 `gen_font.py` 顶部的 `LV_FONT_CONV` 改为 `["lv_font_conv"]`。
- Python 3。

## 用法
```bash
# 生成/更新 font_config.json 中的全部字库
python gen_font.py

# 指定其它配置
python gen_font.py path/to/config.json

# 把一段中文转成 ARMCC(AC5) 安全的 UTF-8 \xNN C 字面量（见下「AC5 注意」）
python gen_font.py --cstr "无法进入地图"
```
**懒人法：双击 `gen_font.bat`** 即按 `font_config.json` 生成（窗口会停留显示结果）。
该 bat 已设好 UTF-8 控制台，故中文提示正常显示；也可命令行带参：`gen_font.bat --cstr "无法进入地图"`。

## 配置文件（font_config.json）
```jsonc
{
  "ttf": "C:/Windows/Fonts/simhei.ttf",   // 默认字体；可被各字库的 ttf 覆盖
  "fonts": [
    {
      "output": "../../USER/App/Resource/Font/font_cn_16.c", // 相对本配置文件目录
      "size": 16,            // 字号(px)
      "bpp": 4,              // 1/2/4/8，越大越平滑也越占空间
      "include_ascii": true, // 是否一并包含 ASCII 0x20-0x7E（便于中英混排）
      "chars": "无法进入地图卡正作为盘，拔出后可。" // 需要的中文/符号
    }
    // 可再列多个不同字号的字库
  ]
}
```
- **新增中文**：把字追加到对应字库的 `chars` 再运行即可；与已有字符自动合并去重。
- **字库符号名** = 输出文件基名，例如 `font_cn_16.c` → `font_cn_16`。
- **路径**：`output`/`ttf` 的相对路径按本配置文件所在目录解析。

## 累积去重机制
每个字库旁生成边车文件 `<output>.chars`（UTF-8，按码点排序记录累计的非 ASCII 字符），
作为最可靠的累积来源；边车缺失时回退解析 `.c` 里的 `/* U+XXXX */` 注释恢复字符集。
**重置**：删除该 `.c` 及同名 `.chars` 后重新运行，即从零按当前 `chars` 生成。

## 在 LVGL 中使用（务必三步，回答“是否还需声明”）
生成的 `.c` 里定义了 `const lv_font_t <name>`（如 `font_cn_16`）。要用起来：

1. **声明**（在使用处或公共头文件）：
   ```c
   LV_FONT_DECLARE(font_cn_16);   // 等价于 extern const lv_font_t font_cn_16;
   ```
2. **应用**到控件或样式：
   ```c
   lv_obj_set_style_text_font(label, &font_cn_16, 0);
   // 或： lv_style_set_text_font(&style, &font_cn_16);
   ```
3. **加入编译**：把生成的 `.c` 加进工程（Keil：右键 `Resource/Font` 组 → Add Existing Files；
   或在 `proj.uvprojx` 的该组补一个 `<File>` 条目）。
   ⚠️ 只声明不编译会在链接期报“`font_cn_16` 未定义”。

另需确认 `lv_conf.h` 中 `LV_TXT_ENC == LV_TXT_ENC_UTF8`（默认即是），否则 UTF-8 文本无法正确解码。

## AC5（armcc）写中文字符串的注意
本工程用 ARMCC 5。源码里直接写中文字面量可能因编码处理出问题，推荐用 UTF-8 `\xNN` 转义：
```bash
python gen_font.py --cstr "无法进入地图"
# 输出： "\xE6\x97\xA0" "\xE6\xB3\x95" "\xE8\xBF\x9B" "\xE5\x85\xA5" "\xE5\x9C\xB0" "\xE5\x9B\xBE"
```
直接把输出粘进 `lv_label_set_text(...)` 即可（相邻字面量自动拼接，且杜绝十六进制转义吞并）。

## 局限
- 面向**子集**（数十~数百字）。码点经命令行 `--range` 传入，字符极多时可能触及命令行长度上限。
- 需要的字必须存在于所选 TTF 中（如 `Tools/AGENCYB.TTF` 是拉丁字体，无中文，请用 SimHei 等中文 TTF）。
