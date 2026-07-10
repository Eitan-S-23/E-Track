from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
CHROME = ROOT / ".claude" / "chrome_240.png"
SKIN = ROOT / ".claude" / "skin_new_240.png"
OUT_C = ROOT / "USER" / "App" / "Resource" / "Image" / "img_src_dialplate_skin.c"


def rgb565_bytes(pixel, high_first):
    r, g, b = pixel[:3]
    value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    if high_first:
        return (value >> 8) & 0xFF, value & 0xFF
    return value & 0xFF, (value >> 8) & 0xFF


def format_bytes(data):
    lines = []
    for i in range(0, len(data), 24):
        chunk = data[i:i + 24]
        lines.append("  " + ",".join(f"0x{b:02x}" for b in chunk) + ",")
    return "\n".join(lines)


def regenerate_c(image):
    pixels = list(image.convert("RGB").getdata())
    swapped = []
    little = []
    for px in pixels:
        swapped.extend(rgb565_bytes(px, True))
        little.extend(rgb565_bytes(px, False))

    return f"""#if defined(LV_LVGL_H_INCLUDE_SIMPLE)
#include "lvgl.h"
#else
#include "lvgl/lvgl.h"
#endif

#ifndef LV_ATTRIBUTE_MEM_ALIGN
#define LV_ATTRIBUTE_MEM_ALIGN
#endif

#ifndef LV_ATTRIBUTE_IMG_IMG_SRC_DIALPLATE_SKIN
#define LV_ATTRIBUTE_IMG_IMG_SRC_DIALPLATE_SKIN
#endif

const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_LARGE_CONST LV_ATTRIBUTE_IMG_IMG_SRC_DIALPLATE_SKIN uint8_t img_src_dialplate_skin_map[] = {{
#if LV_COLOR_DEPTH == 16 && LV_COLOR_16_SWAP != 0
  /*Pixel format: RGB565, byte-swapped (high byte first). TRUE_COLOR, no alpha.*/
{format_bytes(swapped)}
#else
  /*Pixel format: RGB565, little-endian (low byte first). TRUE_COLOR, no alpha.*/
{format_bytes(little)}
#endif
}};

const lv_img_dsc_t img_src_dialplate_skin = {{
  .header.always_zero = 0,
  .header.w = 240,
  .header.h = 320,
  .data_size = 240 * 320 * 2,
  .header.cf = LV_IMG_CF_TRUE_COLOR,
  .data = img_src_dialplate_skin_map,
}};
"""


def main():
    chrome = Image.open(CHROME).convert("RGB")
    skin = Image.open(SKIN).convert("RGB")

    # Restore the original chrome for the whole top navigation pod first.
    top_box = (42, 6, 197, 53)
    skin.paste(chrome.crop(top_box), top_box)

    draw = ImageDraw.Draw(skin)
    nav_fill = (0, 12, 15)

    # Clear only the pod interior. The inset polygon leaves the original top,
    # side and lower cyan chrome pixels from chrome_240.png untouched.
    draw.polygon(
        [
            (68, 10),
            (186, 10),
            (186, 32),
            (176, 47),
            (63, 47),
            (53, 27),
        ],
        fill=nav_fill,
    )

    # Remove the residual baked heart-rate icon fragment above the live icon.
    draw.rectangle((4, 43, 25, 59), fill=(0, 0, 0))

    skin.save(SKIN)
    OUT_C.write_text(regenerate_c(skin), encoding="utf-8")
    print(f"updated {SKIN}")
    print(f"updated {OUT_C}")


if __name__ == "__main__":
    main()
