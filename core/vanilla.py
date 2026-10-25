# -*- coding: utf-8 -*-
"""原版 Minecraft 安装：json / client jar / libraries / assets / logging。"""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Callable, Optional

from .constants import RESOURCES
from .net import Downloader
from .util import maven_path, rules_allow, url_candidates, write_json


def _native_classifier(natives: dict, classifiers: dict) -> Optional[str]:
    raw = natives.get("windows")
    if not raw:
        return None
    bits = "64" if struct.calcsize("P") == 8 else "32"
    candidates = []
    if "${arch}" in raw:
        candidates += [raw.replace("${arch}", bits), raw.replace("${arch}", "64"),
                       raw.replace("${arch}", "32"), "natives-windows"]
    else:
        candidates.append(raw)
    for c in candidates:
        if c in classifiers:
            return c
    return candidates[0]


def _library_items(v: dict) -> list[dict]:
    items: list[dict] = []
    for lib in v.get("libraries", []):
        if not rules_allow(lib.get("rules")):
            continue
        downloads = lib.get("downloads") or {}
        artifact = downloads.get("artifact")
        if artifact and artifact.get("url"):
            items.append({
                "urls": url_candidates(artifact["url"]),
                "rel": artifact["path"],
                "sha1": artifact.get("sha1"),
                "size": artifact.get("size"),
                "label": lib.get("name", "").split(":")[1] if ":" in lib.get("name", "") else lib.get("name", ""),
            })
        else:
            rel = maven_path(lib.get("name", ""))
            base = lib.get("url")
            if rel and base:
                items.append({
                    "urls": url_candidates(base.rstrip("/") + "/" + rel),
                    "rel": rel,
                    "sha1": None,
                    "size": None,
                    "label": lib.get("name", ""),
                })
        natives = lib.get("natives")
        if natives:
            classifiers = downloads.get("classifiers") or {}
            classifier = _native_classifier(natives, classifiers)
            if classifier:
                info = classifiers.get(classifier)
                if info and info.get("url"):
                    items.append({
                        "urls": url_candidates(info["url"]),
                        "rel": info["path"],
                        "sha1": info.get("sha1"),
                        "size": info.get("size"),
                        "label": lib.get("name", "") + " (natives)",
                    })
                else:
                    name = lib.get("name", "")
                    if name:
                        full = f"{name}:{classifier}"
                        rel = maven_path(full)
                        base = lib.get("url") or "https://libraries.minecraft.net/"
                        items.append({
                            "urls": url_candidates(base.rstrip("/") + "/" + rel),
                            "rel": rel,
                            "sha1": None,
                            "size": None,
                            "label": lib.get("name", "") + " (natives)",
                        })
    return items


def install_vanilla(
    dl: Downloader,
    root: Path,
    entry: dict,
    on_stage: Optional[Callable[[str], None]] = None,
    include_assets: bool = True,
) -> dict:
    stage = on_stage or (lambda s: None)
    vid = entry["id"]
    vdir = root / "versions" / vid
    vdir.mkdir(parents=True, exist_ok=True)

    # 1. version json
    stage("下载版本 JSON")
    raw = dl.get_bytes(url_candidates(entry["url"]))
    version = json.loads(raw.decode("utf-8", "replace"))
    (vdir / f"{vid}.json").write_bytes(raw)

    # 2. client jar
    stage("下载 client jar")
    client = (version.get("downloads") or {}).get("client")
    if client and client.get("url"):
        dl.download(
            url_candidates(client["url"]), vdir / f"{vid}.jar",
            client.get("sha1"), client.get("size"), f"{vid}.jar",
        )

    # 3. logging config
    logging = version.get("logging") or {}
    for side in ("client",):
        info = ((logging.get(side) or {}).get("file") or {})
        if info.get("url"):
            dl.download(
                url_candidates(info["url"]),
                root / "assets" / "log_configs" / info["id"],
                info.get("sha1"), info.get("size"), info["id"],
            )

    # 4. asset index
    stage("下载资源索引")
    ai = version.get("assetIndex") or {}
    ai_id = ai.get("id")
    if ai.get("url") and ai_id:
        dl.download(
            url_candidates(ai["url"]),
            root / "assets" / "indexes" / f"{ai_id}.json",
            ai.get("sha1"), ai.get("size"), f"{ai_id}.json",
        )

    # 5. assets objects
    if include_assets and ai_id:
        index_file = root / "assets" / "indexes" / f"{ai_id}.json"
        if index_file.is_file():
            stage("下载游戏资源")
            index = json.loads(index_file.read_text(encoding="utf-8"))
            items = []
            for name, obj in (index.get("objects") or {}).items():
                h = obj["hash"]
                loc = f"{h[:2]}/{h}"
                items.append({
                    "urls": url_candidates(f"{RESOURCES}/{loc}"),
                    "path": root / "assets" / "objects" / h[:2] / h,
                    "sha1": h,
                    "size": obj.get("size"),
                    "label": name,
                })
            dl.download_many(items, "游戏资源")

    # 6. libraries
    stage("下载依赖库")
    items = []
    for it in _library_items(version):
        items.append({
            "urls": it["urls"],
            "path": root / "libraries" / it["rel"],
            "sha1": it["sha1"],
            "size": it["size"],
            "label": it["label"],
        })
    dl.download_many(items, "依赖库")

    return {
        "id": vid,
        "version": version,
        "jar": vdir / f"{vid}.jar",
        "asset_index": ai_id,
        "java_major": (version.get("javaVersion") or {}).get("majorVersion"),
    }
