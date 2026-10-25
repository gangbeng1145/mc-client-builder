# -*- coding: utf-8 -*-
"""通用工具：maven 路径、规则判断、哈希、Java 探测、子进程。"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .constants import ASSET_HOST, BMCL_PREFIXES, OFFICIAL_FIRST_HOSTS, MOJANG_META, BMCLAPI


# ---------------------------------------------------------------- hashes
def sha1_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


# ---------------------------------------------------------------- url mirror
def map_to_bmcl(url: str) -> str:
    for src, dst in BMCL_PREFIXES:
        if url.startswith(src):
            return dst + url[len(src):]
    return url


def url_candidates(url: str, source: str = "auto") -> list[str]:
    """返回按优先级排序的候选 URL（去重）。"""
    if not url:
        return []
    if url.startswith(BMCLAPI):
        return [url]
    bmcl = map_to_bmcl(url)
    if "/v1/objects/" in url:
        # 日志配置等对象 BMCLAPI 没有镜像，直接走官方
        order = [url, bmcl]
    elif any(h in url for h in OFFICIAL_FIRST_HOSTS):
        order = [url, bmcl]
    elif ASSET_HOST in url:
        # 资源对象：自动模式走官方 CDN（实测更快），显式选镜像时尊重用户选择
        order = [bmcl, url] if source == "bmclapi" else [url, bmcl]
    elif source == "official":
        order = [url, bmcl]
    else:  # auto / bmclapi
        order = [bmcl, url]
    out = []
    for u in order:
        if u and u not in out:
            out.append(u)
    return out


# ---------------------------------------------------------------- maven
def maven_path(name: str) -> str:
    """把 `group:artifact:version[:classifier][@ext]` 转成相对路径。"""
    ext = "jar"
    if "@" in name:
        name, ext = name.split("@", 1)
    parts = name.split(":")
    if len(parts) < 3:
        return ""
    group, artifact, version = parts[0], parts[1], parts[2]
    classifier = parts[3] if len(parts) > 3 else None
    filename = f"{artifact}-{version}"
    if classifier:
        filename += f"-{classifier}"
    filename += f".{ext}"
    return "/".join(group.split(".")) + f"/{artifact}/{version}/{filename}"


# ---------------------------------------------------------------- rules
FEATURES: dict[str, bool] = {}


def _rule_matches(rule: dict) -> bool:
    os_restriction = rule.get("os")
    if os_restriction:
        name = os_restriction.get("name")
        if name and name != "windows":
            return False
        arch = os_restriction.get("arch")
        if arch and arch not in ("x86_64", "amd64", "x64"):
            return False
        version_re = os_restriction.get("version")
        if version_re:
            try:
                if not re.search(version_re, platform.version()):
                    return False
            except re.error:
                return False
    feats = rule.get("features")
    if feats:
        for k, v in feats.items():
            if bool(FEATURES.get(k, False)) != bool(v):
                return False
    return True


def rules_allow(rules: Optional[Iterable[dict]]) -> bool:
    if not rules:
        return True
    action = "disallow"
    for rule in rules:
        if _rule_matches(rule):
            action = rule.get("action", "disallow")
    return action == "allow"


# ---------------------------------------------------------------- files
def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def hardlink_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dst.exists():
            dst.unlink()
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} GB"


# ---------------------------------------------------------------- java
_JAVA_RE = re.compile(r'version "([^"]+)"')


def java_version(java: Path) -> Optional[int]:
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        out = subprocess.run(
            [str(java), "-version"],
            capture_output=True, timeout=20, creationflags=flags,
        )
        text = (out.stderr or b"").decode("utf-8", "replace") + (out.stdout or b"").decode("utf-8", "replace")
        m = _JAVA_RE.search(text)
        if not m:
            return None
        ver = m.group(1)
        if ver.startswith("1."):
            return int(ver.split(".")[1])
        return int(ver.split(".")[0].split("-")[0])
    except Exception:
        return None


def find_javas(extra_roots: Optional[list[Path]] = None) -> list[dict]:
    """扫描常见位置的 java.exe，返回 [{path, version}]。"""
    exe = "java.exe" if sys.platform == "win32" else "java"
    candidates: list[Path] = []
    for env in ("JAVA_HOME",):
        v = os.environ.get(env)
        if v:
            candidates.append(Path(v) / "bin" / exe)
    w = shutil.which("java")
    if w:
        candidates.append(Path(w))
    roots = [
        Path(r"C:\Program Files\Java"),
        Path(r"C:\Program Files\Eclipse Adoptium"),
        Path(r"C:\Program Files\Microsoft"),
        Path(r"C:\Program Files\Zulu"),
        Path(r"C:\Program Files (x86)\Java"),
        Path.home() / ".hmcl" / "java",
        Path.home() / "AppData" / "Roaming" / ".hmcl" / "java",
    ]
    if extra_roots:
        roots = list(extra_roots) + roots
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for child in root.iterdir():
                if child.is_dir():
                    candidates.append(child / "bin" / exe)
        except OSError:
            pass
    seen: set[str] = set()
    result: list[dict] = []
    for c in candidates:
        if not c.is_file():
            continue
        key = str(c).lower()
        if key in seen:
            continue
        seen.add(key)
        ver = java_version(c)
        if ver:
            result.append({"path": str(c), "version": ver})
    result.sort(key=lambda x: (-x["version"], x["path"]))
    return result


# ---------------------------------------------------------------- process
def run_process(cmd: list[str], cwd: Path, on_line=None, timeout: int = 1800) -> int:
    """运行外部命令，逐行回调输出。"""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=flags, bufsize=1, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line and on_line:
            on_line(line)
    return proc.wait(timeout=timeout)
