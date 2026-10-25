# -*- coding: utf-8 -*-
"""Fabric / Quilt / LegacyFabric：读 meta 生成版本 JSON。"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from ..constants import BMCLAPI, FABRIC_META, FABRIC_MAVEN, QUILT_META
from ..net import Downloader
from ..util import maven_path, url_candidates, write_json


def _download_profile_libs(dl: Downloader, root: Path, profile: dict, stage: str, default_base: str = FABRIC_MAVEN) -> None:
    items = []
    for lib in profile.get("libraries", []):
        name = lib.get("name", "")
        base = lib.get("url") or default_base
        rel = maven_path(name)
        if not rel:
            continue
        items.append({
            "urls": url_candidates(base.rstrip("/") + "/" + rel),
            "path": root / "libraries" / rel,
            "sha1": lib.get("sha1"),
            "size": lib.get("size"),
            "label": name,
        })
    dl.download_many(items, stage)


def _save_profile(dl: Downloader, root: Path, profile: dict) -> str:
    vid = profile["id"]
    profile.setdefault("type", "release")
    now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    profile.setdefault("time", now)
    profile.setdefault("releaseTime", now)
    write_json(root / "versions" / vid / f"{vid}.json", profile)
    return vid


# ---------------------------------------------------------------- Fabric
def list_fabric(dl: Downloader, mc: str) -> list[dict]:
    data = dl.get_json(
        [f"{BMCLAPI}/fabric-meta/v2/versions/loader/{mc}", f"{FABRIC_META}/v2/versions/loader/{mc}"],
        key=f"fabric-{mc}",
    )
    out = []
    for row in data:
        loader = row.get("loader") or {}
        if not loader.get("version"):
            continue
        out.append({"version": loader["version"], "stable": bool(loader.get("stable"))})
    return out


def install_fabric(dl: Downloader, root: Path, mc: str, loader: str, stage: Callable[[str], None]) -> str:
    stage("安装 Fabric")
    prof = dl.get_json(
        [
            f"{FABRIC_META}/v2/versions/loader/{mc}/{loader}/profile/json",
            f"{BMCLAPI}/fabric-meta/v2/versions/loader/{mc}/{loader}/profile/json",
        ],
    )
    vid = _save_profile(dl, root, prof)
    stage("下载 Fabric 依赖")
    _download_profile_libs(dl, root, prof, "Fabric 依赖")
    return vid


# ---------------------------------------------------------------- Quilt
def list_quilt(dl: Downloader, mc: str) -> list[dict]:
    data = dl.get_json(
        [f"{QUILT_META}/v3/versions/loader/{mc}", f"{BMCLAPI}/quilt-meta/v3/versions/loader/{mc}"],
        key=f"quilt-{mc}",
    )
    out = []
    for row in data:
        loader = row.get("loader") or {}
        if not loader.get("version"):
            continue
        out.append({"version": loader["version"], "stable": bool(loader.get("stable"))})
    return out


def install_quilt(dl: Downloader, root: Path, mc: str, loader: str, stage: Callable[[str], None]) -> str:
    stage("安装 Quilt")
    prof = dl.get_json([f"{QUILT_META}/v3/versions/loader/{mc}/{loader}/profile/json"])
    vid = _save_profile(dl, root, prof)
    stage("下载 Quilt 依赖")
    from ..constants import QUILT_MAVEN
    _download_profile_libs(dl, root, prof, "Quilt 依赖", QUILT_MAVEN)
    return vid
