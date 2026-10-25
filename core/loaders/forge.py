# -*- coding: utf-8 -*-
"""Forge：调用官方 installer 的 --installClient，让 installer 自己跑 processors。"""
from __future__ import annotations

import json
import re
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional

from ..constants import BMCLAPI, FORGE_MAVEN, FORGE_MAVEN2
from ..net import Downloader
from ..util import run_process, url_candidates, write_json


def list_forge(dl: Downloader, mc: str) -> list[dict]:
    data = dl.get_json([f"{BMCLAPI}/forge/minecraft/{mc}"], key=f"forge-{mc}")
    out = []
    for e in data:
        ver = e.get("version")
        if not ver:
            continue
        branch = e.get("branch") or ""
        classifier = f"{mc}-{ver}" + (f"-{branch}" if branch else "")
        sha1 = None
        for f in e.get("files", []):
            if f.get("category") == "installer" and f.get("format") == "jar":
                h = (f.get("hash") or "").lower()
                if len(h) == 40:
                    sha1 = h
        out.append({
            "version": ver,
            "branch": branch,
            "classifier": classifier,
            "sha1": sha1,
            "urls": [
                f"{FORGE_MAVEN}/net/minecraftforge/forge/{classifier}/forge-{classifier}-installer.jar",
                f"{FORGE_MAVEN2}/net/minecraftforge/forge/{classifier}/forge-{classifier}-installer.jar",
            ],
        })
    out.sort(key=lambda x: _ver_key(x["version"]), reverse=True)
    return out


def _ver_key(v: str):
    return [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", v)]


def _ensure_profile(root: Path) -> None:
    p = root / "launcher_profiles.json"
    if not p.exists():
        write_json(p, {"profiles": {}, "settings": {}, "version": 3})


def install_forge(
    dl: Downloader,
    root: Path,
    mc: str,
    entry: dict,
    java: Path,
    stage: Callable[[str], None],
    log: Callable[[str], None],
) -> str:
    stage("下载 Forge 安装器")
    _ensure_profile(root)
    installer = root / ".cache" / "installers" / f"forge-{entry['classifier']}-installer.jar"
    dl.download(
        entry["urls"], installer, entry.get("sha1"), None,
        f"forge-{entry['classifier']}-installer.jar",
    )
    try:
        with zipfile.ZipFile(installer) as z:
            z.namelist()
    except Exception:
        installer.unlink(missing_ok=True)
        dl.download(
            entry["urls"], installer, entry.get("sha1"), None,
            f"forge-{entry['classifier']}-installer.jar",
        )

    expected = _profile_version(installer)
    if expected and (root / "versions" / expected / f"{expected}.json").is_file():
        log(f"  检测到已安装的 Forge {expected}，跳过安装器")
        return expected

    stage("运行 Forge 安装器")
    log(f"  java -jar forge-{entry['classifier']}-installer.jar --installClient .")
    code = run_process(
        [str(java), "-jar", str(installer), "--installClient", str(root)],
        cwd=root,
        on_line=lambda s: log("  [forge] " + s),
        timeout=3600,
    )
    if code != 0:
        raise RuntimeError(f"Forge 安装器退出码 {code}")

    vid = expected
    vdir = root / "versions" / vid
    if not (vdir / f"{vid}.json").is_file():
        vid = _find_new_version(root, mc)
        if not vid:
            raise RuntimeError("Forge 安装器没有生成版本 JSON")
    return vid


def _profile_version(installer: Path) -> Optional[str]:
    try:
        with zipfile.ZipFile(installer) as z:
            prof = json.loads(z.read("install_profile.json"))
        return prof.get("version")
    except Exception:
        return None


def _find_new_version(root: Path, mc: str) -> Optional[str]:
    best = None
    best_time = 0.0
    vroot = root / "versions"
    if not vroot.is_dir():
        return None
    for d in vroot.iterdir():
        j = d / f"{d.name}.json"
        if not j.is_file():
            continue
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("inheritsFrom") != mc:
            continue
        if "forge" not in d.name.lower():
            continue
        mt = j.stat().st_mtime
        if mt > best_time:
            best, best_time = d.name, mt
    return best
