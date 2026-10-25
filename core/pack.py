# -*- coding: utf-8 -*-
"""把构建好的游戏目录打包成 zip。"""
from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .constants import STORED_EXTS

SKIP_DIRS = {".cache"}
SKIP_SUFFIX = {".part", ".tmp"}


def collect_files(root: Path) -> list[Path]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if Path(name).suffix.lower() in SKIP_SUFFIX or name.endswith((".part", ".tmp")):
                continue
            files.append(Path(dirpath) / name)
    files.sort()
    return files


def pack_game(
    root: Path,
    zip_path: Path,
    folder_name: str,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> tuple[Path, int]:
    progress = progress or (lambda d, t, s: None)
    files = collect_files(root)
    total = len(files)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = zip_path.with_suffix(zip_path.suffix + ".part")
    total_bytes = 0
    with zipfile.ZipFile(tmp, "w", allowZip64=True, compresslevel=6) as z:
        for i, f in enumerate(files, 1):
            rel = f.relative_to(root).as_posix()
            arc = f"{folder_name}/{rel}"
            ext = f.suffix.lower()
            if ext in STORED_EXTS:
                z.write(f, arc, compress_type=zipfile.ZIP_STORED)
            else:
                z.write(f, arc, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
            total_bytes += f.stat().st_size
            if i % 20 == 0 or i == total:
                progress(i, total, f"打包 {i}/{total}")
    os.replace(tmp, zip_path)
    return zip_path, total_bytes
