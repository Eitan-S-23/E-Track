"""Machine-readable byte checks using the existing recovery/header owner."""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools"))
import etu_unpack
spec = importlib.util.spec_from_file_location(
    "recovery", ROOT / "Tools/jlink/prepare-bootstrap-app.py"
)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--kind", choices=["app", "recovery"], required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--placeholder", type=Path)
    parser.add_argument("--placeholder-sha256")
    parser.add_argument("--package", type=Path)
    parser.add_argument("--base-image", type=Path)
    args = parser.parse_args()
    try:
        blob = args.input.read_bytes()
        image, kind = recovery.split_asset(blob, args.kind)
        fields = recovery.validate_app(image)
        digest = hashlib.sha256(image).hexdigest()
        if kind != args.kind or fields["version_name"] != args.version:
            raise ValueError("image kind/version mismatch")
        if digest != args.sha256:
            raise ValueError("finalized App raw SHA-256 mismatch")
        if args.placeholder is not None:
            raw = args.placeholder.read_bytes()
            start = recovery.FW_HEADER_OFFSET
            end = start + recovery.FW_HEADER_SIZE
            if hashlib.sha256(raw).hexdigest() != args.placeholder_sha256:
                raise ValueError("GCC source changed")
            if raw[start:end] != bytes([0xFF]) * recovery.FW_HEADER_SIZE:
                raise ValueError("GCC input is not a placeholder App")
            if len(raw) != len(image) or raw[:start] != image[:start] or raw[end:] != image[end:]:
                raise ValueError("finalize changed bytes outside fw_header")
        if args.package is not None:
            package = args.package.read_bytes()
            outer = etu_unpack.parse_etu_header(package)
            old = args.base_image.read_bytes() if args.base_image is not None else None
            base_version = recovery.validate_app(old)["version_code"] if old is not None else 0
            base_sha8 = hashlib.sha256(old).digest()[:8] if old is not None else bytes(8)
            flags = etu_unpack.FLAG_AES | etu_unpack.FLAG_LZMA | (etu_unpack.FLAG_DIFF if old is not None else etu_unpack.FLAG_FULL)
            if (len(package) != etu_unpack.ETU_HEADER_LEN + outer["payload_len"]
                    or outer["flags"] != flags or outer["alg_id"] != 1 or outer["key_id"] != 1
                    or outer["target_vcode"] != fields["version_code"]
                    or outer["base_vcode"] != base_version or outer["base_sha8"] != base_sha8
                    or outer["hw_rev"] != 1 or outer["layout_id"] != 1 or outer["min_boot_ver"] != 1):
                raise ValueError("ETU outer identity/length does not match the verified App/base")
        print(json.dumps({"ok": True, "kind": kind, "sha256": digest, **fields}))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
