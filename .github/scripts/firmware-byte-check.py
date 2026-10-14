"""Machine-readable byte checks using the existing recovery/header owner."""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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
        print(json.dumps({"ok": True, "kind": kind, "sha256": digest, **fields}))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
