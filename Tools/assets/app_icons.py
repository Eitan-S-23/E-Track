"""Generate launcher assets from the exact user-approved raster; no API calls."""

import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, __version__ as pillow_version


SOURCE_SHA = "fa849d68e0d718a08d8461f2e04caecb6807d1396090ad64201f2a88b0d4cf85"
PACKAGE = Path("app/bluetooth_flutter_Trace")
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def output_path(root, relative):
    target = Path(os.path.abspath(root / relative))
    target.relative_to(root)
    for item in (target, *target.parents):
        if item.exists() and (item.is_symlink() or
                getattr(item.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Redirected icon output: " + str(item))
    return target


def encode(image, kind="PNG", **options):
    data = BytesIO()
    image.save(data, format=kind, **options)
    return data.getvalue()


def artifacts(root, original):
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA:
        raise ValueError("This is not the user-approved 29.png")
    source = Image.open(BytesIO(original)).convert("RGB")
    if source.size != (1254, 1254):
        raise ValueError("Unexpected approved-source dimensions")
    result = {PACKAGE / "branding/e_track_source.png": original}
    res = PACKAGE / "android/app/src/main/res"
    for density, scale in DENSITIES.items():
        size = round(48 * scale)
        result[res / f"mipmap-{density}/ic_launcher.png"] = encode(
            source.resize((size, size), Image.Resampling.LANCZOS))
        edge, content = round(108 * scale), round(96 * scale)
        foreground = Image.new("RGBA", (edge, edge))
        inset = (edge - content) // 2
        foreground.paste(source.resize((content, content), Image.Resampling.LANCZOS), (inset, inset))
        result[res / f"mipmap-{density}/ic_launcher_foreground.png"] = encode(foreground)
    apple = PACKAGE / "ios/Runner/Assets.xcassets/AppIcon.appiconset"
    contents = json.loads((root / apple / "Contents.json").read_text(encoding="utf-8"))
    for entry in contents["images"]:
        name = entry.get("filename")
        if name is None:
            continue
        if Path(name).name != name or not name.endswith(".png"):
            raise ValueError("Invalid app icon filename")
        width, height = (float(part) for part in entry["size"].split("x"))
        scale = float(entry["scale"].removesuffix("x"))
        size = (round(width * scale), round(height * scale))
        if size[0] != size[1] or not 16 <= size[0] <= 1024:
            raise ValueError("Invalid app icon size")
        result[apple / name] = encode(source.resize(size, Image.Resampling.LANCZOS))
    result[PACKAGE / "windows/runner/resources/app_icon.ico"] = encode(
        source.resize((256, 256), Image.Resampling.LANCZOS), "ICO",
        sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
    preview = Image.new("RGB", (768, 280), "#eff3f6")
    for index, shape in enumerate(("square", "circle", "rounded")):
        tile = source.resize((200, 200), Image.Resampling.LANCZOS)
        mask = Image.new("L", tile.size)
        drawing = ImageDraw.Draw(mask)
        if shape == "circle":
            drawing.ellipse((0, 0, 199, 199), fill=255)
        elif shape == "rounded":
            drawing.rounded_rectangle((0, 0, 199, 199), radius=44, fill=255)
        else:
            drawing.rectangle((0, 0, 199, 199), fill=255)
        preview.paste(tile, (28 + index * 250, 18), mask)
        small = source.resize((48, 48), Image.Resampling.LANCZOS)
        preview.paste(small, (104 + index * 250, 226))
    result[Path(".cache/app-companion-icons/preview.png")] = encode(preview)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--source")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(os.path.abspath(args.repo_root))
    output_path(root, Path("Tools/assets/app_icons.py"))
    if not (root / ".git").exists() or Path.cwd().resolve() != root.resolve():
        raise ValueError("Run from the explicitly selected worktree")
    source = Path(args.source) if args.source else root / PACKAGE / "branding/e_track_source.png"
    outputs = artifacts(root, source.read_bytes())
    manifest = PACKAGE / "branding/icons.json"
    # Check every controllable destination before creating or replacing any file.
    targets = {relative: output_path(root, relative) for relative in [*outputs, manifest]}
    entries = [{"path": relative.as_posix(), "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest()} for relative, data in outputs.items()
               if relative.parts[0] != ".cache"]
    if args.check:
        for relative, data in outputs.items():
            if relative.parts[0] == ".cache":
                continue
            if targets[relative].read_bytes() != data:
                raise ValueError("Icon differs from approved-source rendering: " + str(relative))
        recorded = json.loads(targets[manifest].read_text(encoding="utf-8"))
        if recorded["sourceSha256"] != SOURCE_SHA or recorded["assets"] != entries:
            raise ValueError("Icon provenance differs")
        print(f"Verified {len(entries)} canonical approved-source assets; source unchanged")
        return
    for relative, data in outputs.items():
        target = targets[relative]
        target.parent.mkdir(parents=True, exist_ok=True)
        output_path(root, relative).write_bytes(data)
    targets[manifest].write_text(json.dumps({"sourceSha256": SOURCE_SHA,
        "pillow": pillow_version, "assets": entries}, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(outputs)} approved-source assets in {root}")


if __name__ == "__main__":
    main()
