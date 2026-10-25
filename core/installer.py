# -*- coding: utf-8 -*-
"""安装编排：原版 → 加载器 → 说明文件 → 打包。"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import manifest as manifest_mod
from .constants import SOURCE_AUTO
from .loaders import fabric as fabric_loader
from .loaders import forge as forge_loader
from .loaders import optifine as optifine_loader
from .net import Downloader
from .pack import pack_game
from .util import write_json
from .vanilla import install_vanilla

README = """========================================
   Minecraft 客户端（免启动器自动配置版）
========================================

这个压缩包里是一个完整的“游戏目录”，里面包含：

  versions/    版本（JSON + client jar）
  libraries/   全部依赖库
  assets/      游戏资源与语言文件
  launcher_profiles.json

【怎么用】

方式一（推荐）：整个文件夹当游戏目录
  1. 把压缩包里的 {folder} 文件夹解压到任意位置
  2. 打开 HMCL → 设置 → 游戏目录 → 选择 {folder} 这个文件夹
  3. 回到版本列表，选择「{version}」→ 启动

方式二：合并进现有 .minecraft
  把 {folder} 里的 versions、libraries、assets 三个文件夹
  一起复制到你的 .minecraft 里（缺一不可），然后启动 HMCL。

【说明】
  * 版本：Minecraft {mc}
  * 加载器：{loader}
  * Java：该版本建议 Java {java}
  * 已包含全部依赖和资源，不需要启动器再补下载。
  * 本包由 MC_Downloader 生成，仅包含客户端文件。

========================================
"""


@dataclass
class InstallOptions:
    work_root: Path
    output_dir: Path
    instance_name: str
    mc_version: str
    loader: str = "none"          # none / forge / optifine / fabric / quilt
    loader_version: str = ""
    java_path: str = ""
    source: str = SOURCE_AUTO
    include_assets: bool = True
    optifine_on_forge: str = ""   # Forge 之上再叠 OptiFine（旧版本）
    threads: int = 32             # 下载线程数


class Installer:
    def __init__(
        self,
        options: InstallOptions,
        log: Callable[[str], None] = lambda s: None,
        progress: Callable[[int, int, str], None] = lambda d, t, s: None,
        stage: Callable[[str], None] = lambda s: None,
    ):
        self.o = options
        self.log = log
        self.progress = progress
        self.stage = stage
        self.root = Path(options.work_root) / options.instance_name
        self.dl = Downloader(
            Path(options.work_root) / ".cache",
            source=options.source,
            log=log,
            progress=progress,
            concurrency=max(1, int(options.threads or 32)),
        )

    def cancel(self) -> None:
        self.dl.cancel()

    # ------------------------------------------------------------ helpers
    def _java(self) -> Path:
        if self.o.java_path and Path(self.o.java_path).is_file():
            return Path(self.o.java_path)
        raise RuntimeError("没有可用的 Java，请先在界面里选择")

    def _check_java(self, required: Optional[int]) -> None:
        java = self._java()
        from .util import java_version
        major = java_version(java)
        if major is None:
            raise RuntimeError(f"无法识别 Java 版本：{java}")
        if required and major < required:
            raise RuntimeError(
                f"该版本需要 Java {required} 或更高，当前选择的是 Java {major}。\n"
                f"请更换 Java 后重试：{java}"
            )
        self.log(f"  使用 Java {major}：{java}")

    def _prepare_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "versions").mkdir(exist_ok=True)
        (self.root / "libraries").mkdir(exist_ok=True)
        (self.root / "assets").mkdir(exist_ok=True)
        p = self.root / "launcher_profiles.json"
        if not p.exists():
            write_json(p, {"profiles": {}, "settings": {}, "version": 3})

    # ------------------------------------------------------------ main
    def run(self) -> Path:
        self.stage("读取版本清单")
        self._prepare_root()
        manifest = manifest_mod.fetch_manifest(self.dl)
        entry = manifest_mod.find_version(manifest, self.o.mc_version)
        if not entry:
            raise RuntimeError(f"版本清单里没有 {self.o.mc_version}")
        self.log(f"  已选择 Minecraft {self.o.mc_version}（{entry.get('type')}）")

        # 1. vanilla
        base = install_vanilla(self.dl, self.root, entry, self.stage, self.o.include_assets)
        self._check_java(base.get("java_major"))
        base_id = base["id"]

        # 2. loader
        loader_label = "原版"
        loader = self.o.loader
        if loader == "forge":
            self.stage("准备 Forge")
            versions = forge_loader.list_forge(self.dl, self.o.mc_version)
            target = self.o.loader_version
            item = next((v for v in versions if v["version"] == target), None)
            if not item:
                raise RuntimeError(f"找不到 Forge {target}")
            java = self._java()
            base_id = forge_loader.install_forge(
                self.dl, self.root, self.o.mc_version, item, java, self.stage, self.log,
            )
            loader_label = f"Forge {target}"
        elif loader == "fabric":
            self.stage("准备 Fabric")
            base_id = fabric_loader.install_fabric(
                self.dl, self.root, self.o.mc_version, self.o.loader_version, self.stage,
            )
            loader_label = f"Fabric {self.o.loader_version}"
        elif loader == "quilt":
            self.stage("准备 Quilt")
            base_id = fabric_loader.install_quilt(
                self.dl, self.root, self.o.mc_version, self.o.loader_version, self.stage,
            )
            loader_label = f"Quilt {self.o.loader_version}"
        elif loader == "optifine":
            self.stage("准备 OptiFine")
            rows = optifine_loader.list_optifine(self.dl, self.o.mc_version)
            row = next((r for r in rows if r["self_version"] == self.o.loader_version), None)
            if not row:
                raise RuntimeError(f"找不到 OptiFine {self.o.loader_version}")
            java = self._java()
            base_id = optifine_loader.install_optifine(
                self.dl, self.root, self.o.mc_version, row, java, base_id, self.stage, self.log,
            )
            loader_label = f"OptiFine {self.o.loader_version}"

        # 2b. Forge + OptiFine（旧版本）
        if self.o.optifine_on_forge and loader == "forge":
            self.stage("叠加 OptiFine")
            rows = optifine_loader.list_optifine(self.dl, self.o.mc_version)
            row = next((r for r in rows if r["self_version"] == self.o.optifine_on_forge), None)
            if row:
                base_id = optifine_loader.install_optifine(
                    self.dl, self.root, self.o.mc_version, row, self._java(), base_id, self.stage, self.log,
                )
                loader_label += f" + OptiFine {self.o.optifine_on_forge}"

        # 3. 说明
        self.stage("写入使用说明")
        (self.root / "使用说明.txt").write_text(
            README.format(folder=self.o.instance_name, version=base_id,
                          mc=self.o.mc_version, loader=loader_label,
                          java=base.get("java_major") or "8+"),
            encoding="utf-8-sig",
        )

        # 4. 打包
        self.stage("压缩游戏目录")
        zip_path = Path(self.o.output_dir) / f"{self.o.instance_name}.zip"
        self.log(f"  输出：{zip_path}")
        pack_game(self.root, zip_path, self.o.instance_name, self.progress)
        size = zip_path.stat().st_size
        self.log(f"  完成：{zip_path}（{size / 1048576:.1f} MB）")
        return zip_path
