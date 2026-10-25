# -*- coding: utf-8 -*-
"""版本清单：在线拉取 + 内置离线兜底。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from .constants import MANIFEST_BMCL, MANIFEST_OFFICIAL
from .net import Downloader


def _local_candidates() -> list[Path]:
    """按优先级找可用的本地清单：
    1. exe 同目录的 version_manifest.json（方便手动更新）
    2. 打包进 exe 的 assets/fallback/version_manifest.json
    3. 源码目录的 assets/fallback/version_manifest.json
    """
    cands: list[Path] = []
    try:
        cands.append(Path(sys.executable).resolve().parent / "version_manifest.json")
    except Exception:
        pass
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cands.append(Path(meipass) / "assets" / "fallback" / "version_manifest.json")
    cands.append(Path(__file__).resolve().parent.parent / "assets" / "fallback" / "version_manifest.json")
    return cands


def load_local_manifest() -> Optional[dict]:
    for p in _local_candidates():
        try:
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("versions"):
                    return data
        except Exception:
            continue
    return None


def fetch_manifest(dl: Downloader) -> dict:
    alt = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
    if dl.source == "official":
        urls = [MANIFEST_OFFICIAL, alt, MANIFEST_BMCL]
    else:
        urls = [MANIFEST_BMCL, MANIFEST_OFFICIAL, alt]
    try:
        data = dl.get_json(urls, key="manifest")
    except Exception:
        local = load_local_manifest()
        if not local:
            raise
        dl.log("  网络清单不可用，已切换为内置离线版本清单")
        data = local
    data["versions"] = [v for v in data.get("versions", []) if v.get("id") and v.get("url")]
    return data


def find_version(manifest: dict, version_id: str) -> Optional[dict]:
    for v in manifest.get("versions", []):
        if v["id"] == version_id:
            return v
    return None


TYPE_LABELS = {
    "release": "正式版",
    "snapshot": "快照",
    "old_beta": "远古 Beta",
    "old_alpha": "远古 Alpha",
}
