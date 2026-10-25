# -*- coding: utf-8 -*-
"""OptiFine：用官方 Patcher 生成补丁库，再写 launchwrapper 版本 JSON。"""
from __future__ import annotations

import json
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional

from ..constants import BMCLAPI, LIBRARIES
from ..net import Downloader
from ..util import maven_path, run_process, url_candidates, write_json

PATCHER_MAIN = "optifine.Patcher"
LAUNCHWRAPPER_MAIN = "net.minecraft.launchwrapper.Launch"
TWEAK_CLASS = "optifine.OptiFineTweaker"


def list_optifine(dl: Downloader, mc: str) -> list[dict]:
    data = dl.get_json([f"{BMCLAPI}/optifine/versionlist"], key="optifine-list")
    rows = []
    seen = set()
    for e in data:
        if e.get("mcversion") != mc:
            continue
        typ = e.get("type")
        patch = e.get("patch")
        if not typ or not patch:
            continue
        key = (typ, patch)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "type": typ,
            "patch": patch,
            "self_version": f"{typ}_{patch}",
            "filename": e.get("filename") or f"OptiFine_{mc}_{typ}_{patch}.jar",
            "stable": not (patch.startswith("pre") or patch.startswith("alpha")),
        })
    rows.sort(key=lambda r: _patch_key(r["patch"]), reverse=True)
    return rows


def _patch_key(patch: str):
    return [int(x) if x.isdigit() else 0 for x in re.split(r"[._\-]", patch)]


def _installer_url(mc: str, row: dict) -> str:
    return f"{BMCLAPI}/optifine/{mc}/{row['type']}/{row['patch']}"


def _strip_mods_toml(jar: Path) -> None:
    """删除 META-INF/mods.toml，避免 Forge 把它当 mod 加载。"""
    try:
        with zipfile.ZipFile(jar, "r") as z:
            names = z.namelist()
            targets = [n for n in names if n.lower() == "meta-inf/mods.toml"]
            if not targets:
                return
            tmp = jar.with_suffix(".tmp")
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
                for n in names:
                    if n in targets:
                        continue
                    out.writestr(n, z.read(n))
        tmp.replace(jar)
    except Exception:
        pass


def install_optifine(
    dl: Downloader,
    root: Path,
    mc: str,
    row: dict,
    java: Path,
    base_id: str,
    stage: Callable[[str], None],
    log: Callable[[str], None],
) -> str:
    self_ver = row["self_version"]
    maven_ver = f"{mc}_{self_ver}"
    stage("下载 OptiFine 安装器")
    installer = root / ".cache" / "installers" / row["filename"]
    dl.download([_installer_url(mc, row)], installer, None, None, row["filename"])

    stage("运行 OptiFine Patcher")
    lib_dir = root / "libraries" / "optifine" / "OptiFine" / maven_ver
    lib_dir.mkdir(parents=True, exist_ok=True)
    installer_lib = lib_dir / f"OptiFine-{maven_ver}-installer.jar"
    shutil.copy2(installer, installer_lib)
    _strip_mods_toml(installer_lib)

    out_lib = lib_dir / f"OptiFine-{maven_ver}.jar"
    mc_jar = root / "versions" / mc / f"{mc}.jar"
    if not mc_jar.is_file():
        raise RuntimeError(f"找不到原版 jar：{mc_jar}")

    has_patcher = False
    with zipfile.ZipFile(installer) as z:
        names = set(z.namelist())
        has_patcher = "optifine/Patcher.class" in names

    if has_patcher:
        cmd = [str(java), "-cp", str(installer), PATCHER_MAIN, str(mc_jar), str(installer), str(out_lib)]
        log("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        code = run_process(cmd, cwd=root, on_line=lambda s: log("  [optifine] " + s), timeout=1800)
        if code != 0 or not out_lib.is_file():
            raise RuntimeError(f"OptiFine Patcher 失败（退出码 {code}）")
    else:
        shutil.copy2(installer, out_lib)
    _strip_mods_toml(out_lib)

    # launchwrapper
    libraries = [{"name": f"optifine:OptiFine:{maven_ver}"}]
    lw_added = False
    with zipfile.ZipFile(installer) as z:
        names = z.namelist()
        if "launchwrapper-of.txt" in names:
            lw_ver = z.read("launchwrapper-of.txt").decode("utf-8", "replace").strip()
            member = f"launchwrapper-of-{lw_ver}.jar"
            if member in names:
                rel = maven_path(f"optifine:launchwrapper-of:{lw_ver}")
                dst = root / "libraries" / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(z.read(member))
                libraries.append({"name": f"optifine:launchwrapper-of:{lw_ver}"})
                lw_added = True
        if not lw_added and "launchwrapper-2.0.jar" in names:
            rel = maven_path("optifine:launchwrapper:2.0")
            dst = root / "libraries" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(z.read("launchwrapper-2.0.jar"))
            libraries.append({"name": "optifine:launchwrapper:2.0"})
            lw_added = True
    if not lw_added:
        libraries.append({"name": "net.minecraft:launchwrapper:1.12"})
        rel = maven_path("net.minecraft:launchwrapper:1.12")
        dl.download(
            url_candidates(f"{LIBRARIES}/{rel}"),
            root / "libraries" / rel, None, None, "launchwrapper-1.12.jar",
        )

    # 校验基础版本的 mainClass
    base_json = root / "versions" / base_id / f"{base_id}.json"
    try:
        base_data = json.loads(base_json.read_text(encoding="utf-8"))
    except Exception:
        base_data = {}
    base_main = base_data.get("mainClass") or "net.minecraft.client.main.Main"
    allowed = {
        "net.minecraft.client.main.Main",
        "net.minecraft.launchwrapper.Launch",
        "cpw.mods.modlauncher.Launcher",
        "cpw.mods.bootstraplauncher.BootstrapLauncher",
    }
    if base_main not in allowed:
        raise RuntimeError(f"基础版本 mainClass 不受支持：{base_main}")
    if base_main not in ("net.minecraft.client.main.Main", "net.minecraft.launchwrapper.Launch"):
        raise RuntimeError(
            "该版本与 OptiFine 不兼容（Forge 1.13+ 使用 BootstrapLauncher，无法叠加 OptiFine）。\n"
            "请单独安装 OptiFine，或改用 1.12.2 及更早版本。"
        )

    stage("写入 OptiFine 版本配置")
    vid = f"{base_id}-OptiFine-{self_ver}"
    now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    version = {
        "id": vid,
        "inheritsFrom": base_id,
        "type": "release",
        "time": now,
        "releaseTime": now,
        "mainClass": LAUNCHWRAPPER_MAIN,
        "arguments": {"game": ["--tweakClass", TWEAK_CLASS]},
        "libraries": libraries,
    }
    write_json(root / "versions" / vid / f"{vid}.json", version)
    return vid
