# LVGL 图标字体一键转换

`convert_iconfont.bat` 用于把 iconfont.cn 下载的图标字体包转换为 LVGL 可直接编译的 `.c` 字库。

## 依赖

- Node.js，需要提供 `npx`。
- 脚本调用 `npx --yes lv_font_conv@1.5.3`，首次运行可能需要联网下载转换工具。

## 图标包放置方式

把 iconfont.cn 下载并解压后的 `font_xxxxx` 文件夹放在当前目录下，例如：

```text
Tools/图标/
  convert_iconfont.bat
  font_8tb3b7jawi9/
    iconfont.json
    iconfont.ttf
    iconfont.css
```

脚本会自动选择当前目录下最新的、同时包含 `iconfont.json` 和 `iconfont.ttf` 的子目录。

## 用法

双击运行：

```bat
convert_iconfont.bat
```

默认输出：

```text
USER/App/Resource/Font/font_iconfont_20.c
```

命令行指定图标包：

```bat
convert_iconfont.bat "font_8tb3b7jawi9"
```

命令行指定输出文件、字号和 bpp：

```bat
convert_iconfont.bat "font_8tb3b7jawi9" "..\..\USER\App\Resource\Font\font_iconfont_24.c" 24 4
```

参数顺序：

```text
convert_iconfont.bat [iconfont目录] [输出.c路径] [字号] [bpp]
```

默认值：

```text
iconfont目录 = 自动选择最新图标包
输出.c路径  = ../../USER/App/Resource/Font/font_iconfont_20.c
字号        = 20
bpp         = 4
```

## 转换范围

脚本会读取 `iconfont.json` 中 `glyphs[].unicode`，自动生成 `--range` 参数，所以新增或删除图标后无需手工维护码点列表。

例如当前图标包中有：

```json
{
  "name": "心率",
  "unicode": "e8bf"
}
```

脚本会自动把它加入 LVGL 字库。

## 在 LVGL 中使用

生成文件名决定 LVGL 字体符号名。

例如：

```text
font_iconfont_20.c
```

对应符号：

```c
font_iconfont_20
```

使用前需要声明：

```c
LV_FONT_DECLARE(font_iconfont_20);
```

设置到 label：

```c
lv_obj_set_style_text_font(label, &font_iconfont_20, 0);
lv_label_set_text(label, "\xEE\xA2\xBF"); /* U+E8BF 心率 */
```

## 加入工程

生成 `.c` 后还需要加入编译：

- Keil: 将生成的 `.c` 加入 `Resource/Font` 分组。
- 本项目当前还需要确保 `MDK-ARM_F435/Objects/X-Track.lnp` 中存在对应 `.o`，例如 `font_iconfont_20.o`。
- 模拟器工程也需要把生成的 `.c` 加入 `Simulator/LVGL.Simulator/LVGL.Simulator.vcxproj`。

只声明字体但未加入编译，会导致链接阶段报 `font_iconfont_20` 未定义。

## ARMCC 5 注意

本项目使用 ARM Compiler 5。源码中建议用 UTF-8 字节转义写 iconfont 字符串，避免编码问题。

常用格式：

```c
#define ICON_HEART_RATE "\xEE\xA2\xBF"  /* U+E8BF */
```

码点转 UTF-8 字节可用在线工具，也可用 Python：

```powershell
python -c "print(chr(0xE8BF).encode('utf-8'))"
```
