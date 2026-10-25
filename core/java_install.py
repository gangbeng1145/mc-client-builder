# -*- coding: utf-8 -*-
"""安装 Java 运行时（Mojang runtime 清单，和 HMCL 用的是同一套）。"""
from __future__ import annotations

import lzma
import re
from pathlib import Path
from typing import Callable, Optional

from .constants import MOJANG_META
from .net import Downloader
from .util import url_candidates

JAVA_LIST_URL = (
    MOJANG_META
    + "/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json"
)

LABELS = {
    "jre-legacy": "Java 8（JRE）",
    "java-runtime-alpha": "Java 16",
    "java-runtime-beta": "Java 17",
    "java-runtime-gamma": "Java 17（gamma）",
    "java-runtime-delta": "Java 21",
    "java-runtime-epsilon": "Java 25",
}

MAJOR_BY_COMPONENT = {
    "jre-legacy": 8,
    "java-runtime-alpha": 16,
    "java-runtime-beta": 17,
    "java-runtime-gamma": 17,
    "java-runtime-delta": 21,
    "java-runtime-epsilon": 25,
}


def _major_from_version(name: str) -> int:
    m = re.match(r"(\d+)", name)
    return int(m.group(1)) if m else 0


def list_runtimes(dl: Downloader) -> list[dict]:
    data = dl.get_json(url_candidates(JAVA_LIST_URL), key="java-runtime-index")
    out = []
    for comp, candidates in (data.get("windows-x64") or {}).items():
        if comp == "minecraft-java-exe" or not candidates:
            continue
        best = max(candidates, key=lambda c: _major_from_version(c["version"]["name"]))
        out.append({
            "component": comp,
            "label": LABELS.get(comp, comp),
            "version": best["version"]["name"],
            "manifest": best["manifest"],
            "major": MAJOR_BY_COMPONENT.get(comp, _major_from_version(best["version"]["name"])),
        })
    out.sort(key=lambda x: x["major"], reverse=True)
    return out


def install_runtime(
    dl: Downloader,
    java_root: Path,
    component: str,
    log: Callable[[str], None] = lambda s: None,
    stage: Callable[[str], None] = lambda s: None,
) -> Path:
    runtimes = list_runtimes(dl)
    item = next((r for r in runtimes if r["component"] == component), None)
    if not item:
        raise RuntimeError(f"找不到 Java 运行时：{component}")

    stage(f"下载 {item['label']} 清单")
    manifest_url = item["manifest"]["url"]
    log(f"  Java {item['version']} -> {java_root}")
    manifest = dl.get_json(url_candidates(manifest_url))

    dest = java_root / f"{component}-{item['version']}"
    dest.mkdir(parents=True, exist_ok=True)

    stage(f"下载 {item['label']} 文件")
    items = []
    lzma_files = []
    for rel, info in (manifest.get("files") or {}).items():
        typ = info.get("type")
        target = dest / rel
        if typ == "directory":
            target.mkdir(parents=True, exist_ok=True)
            continue
        if typ != "file":
            continue
        downloads = info.get("downloads") or {}
        raw = downloads.get("raw")
        if raw and raw.get("url"):
            items.append({
                "urls": url_candidates(raw["url"]),
                "path": target,
                "sha1": raw.get("sha1"),
                "size": raw.get("size"),
                "label": rel,
            })
        elif downloads.get("lzma"):
            lzma_files.append((rel, target, downloads["lzma"]))

    # 大文件（lib/modules 等）单独串行下，避免和几百个小文件抢线程池
    big = [it for it in items if (it.get("size") or 0) >= 10 * 1024 * 1024]
    small = [it for it in items if (it.get("size") or 0) < 10 * 1024 * 1024]
    for it in big:
        stage(f"下载 {it['label']}")
        log(f"  {it['label']}  {round((it.get('size') or 0) / 1048576, 1)} MB")
        dl.download(it["urls"], it["path"], it.get("sha1"), it.get("size"), it["label"])
    dl.download_many(small, "Java 文件")
    for rel, target, info in lzma_files:
        stage(f"解压 {rel}")
        data = dl.get_bytes(url_candidates(info["url"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            raw = lzma.decompress(data, format=lzma.FORMAT_ALONE)
        except lzma.LZMAError:
            raw = lzma.decompress(data)
        target.write_bytes(raw)

    java_exe = dest / "bin" / "java.exe"
    if not java_exe.is_file():
        raise RuntimeError(f"Java 安装后找不到 java.exe：{java_exe}")
    return java_exe
