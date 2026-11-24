"""Exact archived bytes for four superseded tooling inputs and one old header.

This validates historical evidence, never the current implementation. Runtime
source pins continue to use actual paths/hashes through p34_session.record.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = {
    "Libraries/OTA/ota_backup.h": (".cache/p34-erase/before/ota_backup.h",
        "fecc7d1901690c73b0e157bb98dd2e485248ab00bde29644def7187f80f78d32"),
    "Tools/ota/p34_patch_assets.py": (".cache/p34-erase/provenance-before/p34_patch_assets.py",
        "5d41a09152988ee10728b67a546fe997c17da4f252cfa8c1a521acad3a4a1707"),
    "Tools/ota/p34_patch_preparation.py": (".cache/p34-erase/provenance-before/p34_patch_preparation.py",
        "51724ea9f4fc3102c14b5d9a64aec1304365a37ff48451862a4cfaf5691462da"),
    "Tools/ota/p34_cost_assets.py": (".cache/p34-erase/provenance-before/p34_cost_assets.py",
        "17d42eff9ed52916a7923b8715748a31300e513c67a2482beda60ec82269b025"),
    "Tools/ota/p34_erase_assets.py": (".cache/p34-erase/provenance-before/p34_erase_assets.py",
        "6ca1414e4d0929eb45ced95e485d4d1ce496bf1b26f0915500b5194b72fb8cfe"),
}


def resolve(item):
    """Return a byte-verified source; leave the original evidence record intact."""
    path = Path(item["path"])
    def matches(candidate):
        data = candidate.read_bytes()
        return len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    if matches(path):
        return path
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        relative = ""
    archive = ARCHIVES.get(relative)
    if archive and archive[1] == item["sha256"]:
        candidate = ROOT / archive[0]
        if matches(candidate):
            return candidate
    raise RuntimeError("bound input changed: " + str(path))
