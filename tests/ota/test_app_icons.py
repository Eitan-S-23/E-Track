import hashlib
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "app/bluetooth_flutter_Trace"
RES = PACKAGE / "android/app/src/main/res"
SHA = "fa849d68e0d718a08d8461f2e04caecb6807d1396090ad64201f2a88b0d4cf85"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def png_size(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("Not a PNG")
    return struct.unpack(">II", data[16:24])


class AppIconTests(unittest.TestCase):
    def test_exact_user_source_and_all_asset_hashes(self):
        source = PACKAGE / "branding/e_track_source.png"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), SHA)
        manifest = json.loads((PACKAGE / "branding/icons.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["sourceSha256"], SHA)
        expected = {source.relative_to(ROOT).as_posix(),
                    (PACKAGE / "windows/runner/resources/app_icon.ico").relative_to(ROOT).as_posix()}
        for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
            for name in ("ic_launcher.png", "ic_launcher_foreground.png"):
                expected.add((RES / ("mipmap-" + density) / name).relative_to(ROOT).as_posix())
        apple = PACKAGE / "ios/Runner/Assets.xcassets/AppIcon.appiconset"
        for item in json.loads((apple / "Contents.json").read_text())["images"]:
            if "filename" in item:
                expected.add((apple / item["filename"]).relative_to(ROOT).as_posix())
        self.assertEqual({item["path"] for item in manifest["assets"]}, expected)
        self.assertEqual(len(manifest["assets"]), len(expected))
        for item in manifest["assets"]:
            data = (ROOT / item["path"]).read_bytes()
            self.assertEqual(len(data), item["size"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])

    def test_platform_dimensions_and_windows_sizes(self):
        for density, scale in (("mdpi", 1), ("hdpi", 1.5), ("xhdpi", 2), ("xxhdpi", 3), ("xxxhdpi", 4)):
            folder = RES / ("mipmap-" + density)
            self.assertEqual(png_size(folder / "ic_launcher.png"), (round(48 * scale),) * 2)
            self.assertEqual(png_size(folder / "ic_launcher_foreground.png"), (round(108 * scale),) * 2)
        apple = PACKAGE / "ios/Runner/Assets.xcassets/AppIcon.appiconset"
        for item in json.loads((apple / "Contents.json").read_text())["images"]:
            if "filename" not in item:
                continue
            width = round(float(item["size"].split("x")[0]) * float(item["scale"].rstrip("x")))
            self.assertEqual(png_size(apple / item["filename"]), (width, width))
        ico = (PACKAGE / "windows/runner/resources/app_icon.ico").read_bytes()
        reserved, kind, count = struct.unpack("<HHH", ico[:6])
        self.assertEqual((reserved, kind, count), (0, 1, 7))
        self.assertEqual({ico[6 + index * 16] or 256 for index in range(count)}, {16, 24, 32, 48, 64, 128, 256})

    def test_adaptive_and_notification_resources(self):
        for level in (26, 33):
            icon = ET.parse(RES / f"mipmap-anydpi-v{level}/ic_launcher.xml").getroot()
            self.assertEqual(icon.find("foreground").get(ANDROID + "drawable"), "@mipmap/ic_launcher_foreground")
            self.assertEqual(icon.find("background").get(ANDROID + "drawable"), "@color/e_track_launcher_background")
        vector = ET.parse(RES / "drawable/ic_stat_e_track.xml").getroot()
        self.assertEqual(vector.tag, "vector")
        for element in vector.findall("path"):
            for attr in ("fillColor", "strokeColor"):
                value = element.get(ANDROID + attr)
                if value is not None:
                    self.assertIn(value, ("#FFFFFFFF", "#00000000"))
        for service in ("DeviceOtaService", "UpdateForegroundService"):
            code = (PACKAGE / f"android/app/src/main/kotlin/com/wen/gaia/gaia/{service}.kt").read_text(encoding="utf-8")
            self.assertIn("setSmallIcon(R.drawable.ic_stat_e_track)", code)
            self.assertNotIn("setSmallIcon(R.mipmap.ic_launcher)", code)


if __name__ == "__main__":
    unittest.main()
