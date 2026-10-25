# -*- coding: utf-8 -*-
"""主窗口。"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
)

from core.constants import SOURCE_AUTO, SOURCE_BMCLAPI, SOURCE_OFFICIAL
from core.installer import InstallOptions, Installer
from core.loaders import fabric as fabric_loader
from core.loaders import forge as forge_loader
from core.loaders import optifine as optifine_loader
from core.manifest import TYPE_LABELS, fetch_manifest
from core.net import Downloader
from core.netdiag import diagnose, format_report
from core.util import find_javas

from . import theme
from .java_dialog import JavaInstallDialog
from .widgets import Card, TitleBar, VersionList, VersionModel

APP_DIR = Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False):
    _cfg_dir = Path(os.environ.get("APPDATA") or Path.home()) / "MCBuilder"
else:
    _cfg_dir = APP_DIR
try:
    _cfg_dir.mkdir(parents=True, exist_ok=True)
except OSError:
    _cfg_dir = Path.home()
CONFIG_PATH = _cfg_dir / "config.json"

_BASE = Path.home()
DEFAULT_WORK = _BASE / "MC_Downloader_Work"
DEFAULT_OUT = _BASE / "MC_Downloader_Out"

LOADERS = [
    ("none", "原版（不装加载器）"),
    ("forge", "Forge"),
    ("optifine", "OptiFine"),
    ("fabric", "Fabric"),
    ("quilt", "Quilt"),
]


# ==================================================================== workers
class ManifestWorker(QThread):
    ok = Signal(list, dict)
    fail = Signal(str)

    def __init__(self, work: Path, source: str):
        super().__init__()
        self.work = work
        self.source = source

    def run(self):
        try:
            dl = Downloader(self.work / ".cache", source=self.source)
            data = fetch_manifest(dl)
            self.ok.emit(data.get("versions", []), data.get("latest", {}) or {})
        except Exception as e:
            self.fail.emit(str(e))


class LoaderWorker(QThread):
    ok = Signal(int, list)
    fail = Signal(int, str)

    def __init__(self, token: int, mc: str, loader: str, work: Path, source: str):
        super().__init__()
        self.token = token
        self.mc = mc
        self.loader = loader
        self.work = work
        self.source = source

    def run(self):
        try:
            dl = Downloader(self.work / ".cache", source=self.source)
            if self.loader == "forge":
                rows = forge_loader.list_forge(dl, self.mc)
                items = [{"value": r["version"], "label": r["version"]} for r in rows]
            elif self.loader == "fabric":
                rows = fabric_loader.list_fabric(dl, self.mc)
                items = [
                    {"value": r["version"], "label": r["version"] + ("" if r["stable"] else "  (测试)")}
                    for r in rows
                ]
            elif self.loader == "quilt":
                rows = fabric_loader.list_quilt(dl, self.mc)
                items = [
                    {"value": r["version"], "label": r["version"] + ("" if r["stable"] else "  (测试)")}
                    for r in rows
                ]
            elif self.loader == "optifine":
                rows = optifine_loader.list_optifine(dl, self.mc)
                items = [
                    {"value": r["self_version"], "label": r["self_version"] + ("" if r["stable"] else "  (预览)")}
                    for r in rows
                ]
            else:
                items = []
            self.ok.emit(self.token, items)
        except Exception as e:
            self.fail.emit(self.token, str(e))


class JavaWorker(QThread):
    ok = Signal(list)

    def __init__(self, extra_roots=None):
        super().__init__()
        self.extra_roots = extra_roots or []

    def run(self):
        try:
            self.ok.emit(find_javas(self.extra_roots))
        except Exception:
            self.ok.emit([])


class DiagnoseWorker(QThread):
    done = Signal(str)

    def run(self):
        try:
            self.done.emit(format_report(diagnose()))
        except Exception as e:
            self.done.emit(f"诊断失败：{type(e).__name__}: {e}")


class InstallWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int, str)
    stage = Signal(str)
    ok = Signal(str)
    fail = Signal(str)

    def __init__(self, options: InstallOptions):
        super().__init__()
        self.options = options
        self._installer: Installer | None = None
        self._cancelled = False

    def run(self):
        try:
            self._installer = Installer(
                self.options,
                log=self.log.emit,
                progress=self.progress.emit,
                stage=self.stage.emit,
            )
            if self._cancelled:
                self._installer.cancel()
            path = self._installer.run()
            self.ok.emit(str(path))
        except Exception as e:
            if self._cancelled:
                self.fail.emit("已取消")
            else:
                self.fail.emit(str(e))

    def cancel(self):
        self._cancelled = True
        if self._installer:
            self._installer.cancel()


# ==================================================================== window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MC 客户端构建器")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMinimumSize(1080, 720)
        self.resize(1120, 780)

        self.all_versions: list[dict] = []
        self.filter_type: str | None = None
        self.model = VersionModel()
        self._name_edited = False
        self._loader_token = 0
        self._pending_java = ""
        self._worker: InstallWorker | None = None
        self._manifest_worker = None
        self._java_worker = None
        self._loader_worker = None

        self.config = self._load_config()

        self._build_ui()
        self._apply_config()
        self._start_manifest()
        self._start_java_scan()

    # ------------------------------------------------------------ config
    def _load_config(self) -> dict:
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_config(self) -> None:
        data = {
            "work": self.work_edit.text(),
            "out": self.out_edit.text(),
            "source": self.source_combo.currentData(),
            "threads": self.threads_combo.currentData(),
            "java": self.java_combo.currentData(),
            "width": self.width(),
            "height": self.height(),
        }
        try:
            CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _apply_config(self) -> None:
        cfg = self.config
        self.work_edit.setText(cfg.get("work") or str(DEFAULT_WORK))
        self.out_edit.setText(cfg.get("out") or str(DEFAULT_OUT))
        src = cfg.get("source") or SOURCE_AUTO
        idx = self.source_combo.findData(src)
        if idx >= 0:
            self.source_combo.setCurrentIndex(idx)
        th = cfg.get("threads")
        if th:
            try:
                j = self.threads_combo.findData(int(th))
                if j >= 0:
                    self.threads_combo.setCurrentIndex(j)
            except (TypeError, ValueError):
                pass
        if cfg.get("java"):
            self._preferred_java = cfg["java"]
        else:
            self._preferred_java = ""
        w = cfg.get("width")
        h = cfg.get("height")
        if isinstance(w, int) and isinstance(h, int):
            self.resize(w, h)

    # ------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar())

        content = QHBoxLayout()
        content.setContentsMargins(18, 4, 18, 14)
        content.setSpacing(14)
        outer.addLayout(content, 1)

        content.addWidget(self._build_left(), 0)

        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self._build_config_card())
        right.addWidget(self._build_loader_card())
        right.addWidget(self._build_progress_card(), 1)
        content.addLayout(right, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 0, 20, 8)
        hint = QLabel("成品是一个 zip：解压出的文件夹可直接作为 HMCL 的游戏目录")
        hint.setObjectName("Hint")
        bottom.addWidget(hint)
        bottom.addStretch(1)
        grip = QSizeGrip(self)
        grip.setFixedSize(16, 16)
        bottom.addWidget(grip, 0, Qt.AlignRight | Qt.AlignBottom)
        outer.addLayout(bottom)

    def _build_left(self) -> QWidget:
        card = Card("选择 Minecraft 版本")
        card.setFixedWidth(338)
        body = card.body()

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索版本号，例如 1.20 / 1.12.2 / 26.3")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refresh_filter)
        body.addWidget(self.search)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        for i, (key, text) in enumerate((("all", "全部"), ("release", "正式"), ("snapshot", "快照"), ("old", "远古"))):
            b = QPushButton(text)
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.clicked.connect(lambda _=False, k=key: self._set_filter(k))
            self.chip_group.addButton(b, i)
            chips.addWidget(b)
        chips.addStretch(1)
        body.addLayout(chips)

        self.count_label = QLabel("加载中…")
        self.count_label.setObjectName("Hint")
        body.addWidget(self.count_label)

        self.version_list = VersionList()
        self.version_list.setModel(self.model)
        self.version_list.selectionModel().currentChanged.connect(self._on_version_changed)
        body.addWidget(self.version_list, 1)

        return card

    def _build_config_card(self) -> QWidget:
        card = Card("实例配置")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(9)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 0)
        card.body().addLayout(grid)

        def label(text: str) -> QLabel:
            lab = QLabel(text)
            lab.setObjectName("FieldLabel")
            return lab

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("实例名称（也是输出 zip 名）")
        self.name_edit.textEdited.connect(lambda _: setattr(self, "_name_edited", True))
        grid.addWidget(label("实例名称"), 0, 0)
        grid.addWidget(self.name_edit, 0, 1, 1, 3)

        self.work_edit = QLineEdit()
        self.work_edit.setPlaceholderText("构建工作目录")
        grid.addWidget(label("构建目录"), 1, 0)
        grid.addWidget(self.work_edit, 1, 1, 1, 2)
        b = QPushButton("浏览")
        b.setObjectName("Ghost")
        b.clicked.connect(lambda: self._pick_dir(self.work_edit))
        grid.addWidget(b, 1, 3)

        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("最终 zip 放这里")
        grid.addWidget(label("输出目录"), 2, 0)
        grid.addWidget(self.out_edit, 2, 1, 1, 2)
        b = QPushButton("浏览")
        b.setObjectName("Ghost")
        b.clicked.connect(lambda: self._pick_dir(self.out_edit))
        grid.addWidget(b, 2, 3)

        self.source_combo = QComboBox()
        self.source_combo.addItem("自动（国内优先 BMCLAPI）", SOURCE_AUTO)
        self.source_combo.addItem("只用 BMCLAPI 镜像", SOURCE_BMCLAPI)
        self.source_combo.addItem("只用 Mojang 官方", SOURCE_OFFICIAL)
        grid.addWidget(label("下载源"), 3, 0)
        grid.addWidget(self.source_combo, 3, 1, 1, 3)

        self.threads_combo = QComboBox()
        for n in (4, 8, 16, 24, 32):
            self.threads_combo.addItem(f"{n} 线程" + ("（最快）" if n == 32 else ""), n)
        self.threads_combo.setCurrentIndex(self.threads_combo.findData(32))
        grid.addWidget(label("下载线程"), 4, 0)
        grid.addWidget(self.threads_combo, 4, 1, 1, 3)

        self.java_combo = QComboBox()
        grid.addWidget(label("Java"), 5, 0)
        grid.addWidget(self.java_combo, 5, 1)
        b = QPushButton("刷新")
        b.setObjectName("Ghost")
        b.clicked.connect(self._start_java_scan)
        grid.addWidget(b, 5, 2)
        b = QPushButton("安装 Java")
        b.setObjectName("Ghost")
        b.clicked.connect(self._install_java)
        self.java_install_btn = b
        grid.addWidget(b, 5, 3)

        self.assets_check = QCheckBox("包含游戏资源 assets（正式构建建议勾选）")
        self.assets_check.setChecked(True)
        grid.addWidget(self.assets_check, 6, 0, 1, 4)

        return card

    def _build_loader_card(self) -> QWidget:
        card = Card("加载器")
        row = QHBoxLayout()
        row.setSpacing(10)
        self.loader_combo = QComboBox()
        for key, text in LOADERS:
            self.loader_combo.addItem(text, key)
        self.loader_combo.setFixedWidth(230)
        self.loader_combo.currentIndexChanged.connect(self._on_loader_changed)
        row.addWidget(self.loader_combo)

        self.loader_ver_combo = QComboBox()
        self.loader_ver_combo.setMinimumWidth(220)
        self.loader_ver_combo.setEnabled(False)
        self.loader_ver_combo.currentIndexChanged.connect(lambda _: self._on_loader_ver_changed())
        row.addWidget(self.loader_ver_combo, 1)

        self.loader_hint = QLabel("仅安装原版")
        self.loader_hint.setObjectName("Hint")
        row.addWidget(self.loader_hint)
        row.addStretch(1)
        card.body().addLayout(row)
        return card

    def _build_progress_card(self) -> QWidget:
        card = Card("构建进度")
        body = card.body()

        head = QHBoxLayout()
        self.stage_label = QLabel("等待开始")
        self.stage_label.setObjectName("Stage")
        head.addWidget(self.stage_label)
        head.addStretch(1)
        self.percent_label = QLabel("")
        self.percent_label.setObjectName("Hint")
        head.addWidget(self.percent_label)
        body.addLayout(head)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        body.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(4000)
        self.log_view.setMinimumHeight(150)
        body.addWidget(self.log_view, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.diag_btn = QPushButton("网络诊断")
        self.diag_btn.setObjectName("Ghost")
        self.diag_btn.clicked.connect(self._diagnose)
        actions.addWidget(self.diag_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("Ghost")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        actions.addWidget(self.cancel_btn)

        self.start_btn = QPushButton("开始构建")
        self.start_btn.setObjectName("Primary")
        self.start_btn.setFixedWidth(180)
        self.start_btn.clicked.connect(self._start_install)
        actions.addWidget(self.start_btn)
        body.addLayout(actions)
        return card

    # ------------------------------------------------------------ helpers
    def _pick_dir(self, edit: QLineEdit) -> None:
        start = edit.text() or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, "选择目录", start)
        if d:
            edit.setText(d)

    def _set_filter(self, key: str) -> None:
        self.filter_type = None if key == "all" else key
        self._refresh_filter()

    def _refresh_filter(self) -> None:
        text = self.search.text().strip().lower()
        rows = []
        for v in self.all_versions:
            t = v.get("type")
            if self.filter_type == "old":
                if t not in ("old_beta", "old_alpha"):
                    continue
            elif self.filter_type and t != self.filter_type:
                continue
            if text and text not in str(v.get("id", "")).lower():
                continue
            rows.append(v)
        self.model.set_rows(rows)
        self.count_label.setText(f"共 {len(rows)} 个版本")
        if rows and not self.version_list.selectionModel().hasSelection():
            self.version_list.setCurrentIndex(self.model.index(0, 0))

    def _selected_version(self) -> dict | None:
        idx = self.version_list.currentIndex()
        if not idx.isValid():
            return None
        return idx.data(Qt.UserRole)

    def _current_loader(self) -> str:
        return self.loader_combo.currentData() or "none"

    # ------------------------------------------------------------ data
    def _start_manifest(self) -> None:
        work = Path(self.work_edit.text() or DEFAULT_WORK)
        self.count_label.setText("正在读取版本清单…")
        w = ManifestWorker(work, self.source_combo.currentData() or SOURCE_AUTO)
        self._manifest_worker = w
        w.ok.connect(self._on_manifest)
        w.fail.connect(self._on_manifest_fail)
        w.start()

    def _on_manifest(self, versions: list, latest: dict) -> None:
        self.all_versions = versions
        self._latest = latest or {}
        self._refresh_filter()
        self.log_view.appendPlainText(f"版本清单：{len(versions)} 个版本")
        release = self._latest.get("release")
        if release:
            for row in range(self.model.rowCount()):
                idx = self.model.index(row, 0)
                if idx.data(Qt.UserRole).get("id") == release:
                    self.version_list.setCurrentIndex(idx)
                    self.version_list.scrollTo(idx)
                    break
        self._on_loader_changed()

    def _on_manifest_fail(self, msg: str) -> None:
        self.count_label.setText("版本清单加载失败")
        self.log_view.appendPlainText("版本清单加载失败：" + msg)
        box = QMessageBox(self)
        box.setWindowTitle("加载失败")
        box.setIcon(QMessageBox.Warning)
        box.setText("读取版本清单失败")
        box.setInformativeText("可能是虚拟机未联网、系统时间不对或网络被拦截。\n可以先点「网络诊断」看具体原因。")
        box.setDetailedText(msg)
        retry = box.addButton("重试", QMessageBox.AcceptRole)
        diag = box.addButton("网络诊断", QMessageBox.ActionRole)
        box.addButton("关闭", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is retry:
            self._start_manifest()
        elif box.clickedButton() is diag:
            self._diagnose()

    def _diagnose(self) -> None:
        self.diag_btn.setEnabled(False)
        self.stage_label.setText("网络诊断中…")
        self.stage_label.setStyleSheet(f"color: {theme.ACCENT};")
        self.log_view.appendPlainText("\n开始网络诊断（约 20 秒）…")
        w = DiagnoseWorker()
        self._diag_worker = w
        w.done.connect(self._show_diag)
        w.start()

    def _show_diag(self, text: str) -> None:
        self.diag_btn.setEnabled(True)
        self.stage_label.setText("网络诊断完成")
        self.stage_label.setStyleSheet(f"color: {theme.MUTED};")
        self.log_view.appendPlainText("\n===== 网络诊断 =====\n" + text + "\n====================")
        box = QMessageBox(self)
        box.setWindowTitle("网络诊断")
        box.setIcon(QMessageBox.Information)
        box.setText("诊断结果（点「Show Details」可复制全文）")
        box.setDetailedText(text)
        retry = box.addButton("重试加载", QMessageBox.AcceptRole)
        box.addButton("关闭", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is retry:
            self._start_manifest()

    def _start_java_scan(self, select: str | None = None) -> None:
        self._pending_java = select or ""
        self.java_combo.clear()
        self.java_combo.addItem("正在扫描 Java…", "")
        work = Path(self.work_edit.text().strip() or DEFAULT_WORK)
        w = JavaWorker([work / "java"])
        self._java_worker = w
        w.ok.connect(self._on_javas)
        w.start()

    def _install_java(self) -> None:
        work = Path(self.work_edit.text().strip() or DEFAULT_WORK)
        dlg = JavaInstallDialog(
            work,
            self.source_combo.currentData() or SOURCE_AUTO,
            int(self.threads_combo.currentData() or 32),
            self,
        )
        if dlg.exec() == QDialog.Accepted and dlg.result_path:
            self._start_java_scan(select=dlg.result_path)

    def _on_javas(self, javas: list) -> None:
        self.java_combo.clear()
        if not javas:
            self.java_combo.addItem("未找到 Java，请安装 JDK 8/17/21", "")
            return
        for j in javas:
            self.java_combo.addItem(f"Java {j['version']}  ·  {j['path']}", j["path"])
        prefer = getattr(self, "_pending_java", "") or getattr(self, "_preferred_java", "")
        if prefer:
            idx = self.java_combo.findData(prefer)
            if idx >= 0:
                self.java_combo.setCurrentIndex(idx)
        self._pending_java = ""

    # ------------------------------------------------------------ selection
    def _on_version_changed(self, *_args) -> None:
        v = self._selected_version()
        if not v:
            return
        if not self._name_edited:
            self._auto_name()
        if self._current_loader() != "none":
            self._fetch_loader_versions()

    def _on_loader_changed(self, *_args) -> None:
        loader = self._current_loader()
        self._loader_token += 1
        self.loader_ver_combo.clear()
        self.loader_ver_combo.setEnabled(False)
        if loader == "none":
            self.loader_hint.setText("仅安装原版")
            self.loader_ver_combo.addItem("（原版不需要）", "")
            self.loader_ver_combo.setEnabled(False)
            if not self._name_edited:
                self._auto_name()
            return
        self.loader_hint.setText("正在读取版本…")
        self._fetch_loader_versions()

    def _fetch_loader_versions(self) -> None:
        v = self._selected_version()
        loader = self._current_loader()
        if not v or loader == "none":
            return
        self._loader_token += 1
        token = self._loader_token
        work = Path(self.work_edit.text() or DEFAULT_WORK)
        w = LoaderWorker(token, v["id"], loader, work, self.source_combo.currentData() or SOURCE_AUTO)
        self._loader_worker = w
        w.ok.connect(self._on_loader_versions)
        w.fail.connect(self._on_loader_fail)
        w.start()

    def _on_loader_versions(self, token: int, items: list) -> None:
        if token != self._loader_token:
            return
        self.loader_ver_combo.clear()
        for it in items:
            self.loader_ver_combo.addItem(it["label"], it["value"])
        self.loader_ver_combo.setEnabled(bool(items))
        self.loader_hint.setText(f"{len(items)} 个可选版本" if items else "该 MC 版本没有可用版本")
        if items:
            self.loader_ver_combo.setCurrentIndex(0)
        if not self._name_edited:
            self._auto_name()

    def _on_loader_fail(self, token: int, msg: str) -> None:
        if token != self._loader_token:
            return
        self.loader_hint.setText("加载失败")
        self.log_view.appendPlainText("加载器版本获取失败：" + msg)

    def _on_loader_ver_changed(self) -> None:
        if not self._name_edited:
            self._auto_name()

    def _auto_name(self) -> None:
        v = self._selected_version()
        if not v:
            return
        mc = v["id"]
        loader = self._current_loader()
        ver = self.loader_ver_combo.currentData() if loader != "none" else ""
        if loader == "none":
            name = mc
        elif loader == "optifine":
            name = f"{mc}-OptiFine-{ver}"
        else:
            name = f"{mc}-{loader}-{ver}"
        self.name_edit.setText(name)

    # ------------------------------------------------------------ install
    def _start_install(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        v = self._selected_version()
        if not v:
            QMessageBox.warning(self, "缺少版本", "请先在左侧选择一个 Minecraft 版本")
            return
        loader = self._current_loader()
        loader_ver = self.loader_ver_combo.currentData() if loader != "none" else ""
        if loader != "none" and not loader_ver:
            QMessageBox.warning(self, "缺少加载器版本", "请选择加载器版本，或等待列表加载完成")
            return
        java = self.java_combo.currentData()
        if not java:
            QMessageBox.warning(self, "缺少 Java", "没有找到可用的 Java，请安装 JDK 17（或 8）后点“刷新”")
            return

        name = self.name_edit.text().strip()
        name = re.sub(r'[\\/:*?"<>|]', "-", name)
        if not name:
            QMessageBox.warning(self, "实例名为空", "请填写实例名称")
            return
        self.name_edit.setText(name)

        work = Path(self.work_edit.text().strip() or DEFAULT_WORK)
        out = Path(self.out_edit.text().strip() or DEFAULT_OUT)
        try:
            work.mkdir(parents=True, exist_ok=True)
            out.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "目录不可用", str(e))
            return

        if (Path(out) / f"{name}.zip").exists():
            r = QMessageBox.question(
                self, "文件已存在",
                f"{name}.zip 已存在，继续会覆盖它。是否继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                return

        opt = InstallOptions(
            work_root=work,
            output_dir=out,
            instance_name=name,
            mc_version=v["id"],
            loader=loader,
            loader_version=loader_ver,
            java_path=java,
            source=self.source_combo.currentData() or SOURCE_AUTO,
            include_assets=self.assets_check.isChecked(),
            threads=int(self.threads_combo.currentData() or 32),
        )

        self.log_view.clear()
        self.progress.setValue(0)
        self.percent_label.setText("")
        self.stage_label.setText("准备中…")
        self.stage_label.setStyleSheet(f"color: {theme.ACCENT};")
        self._set_running(True)

        w = InstallWorker(opt)
        self._worker = w
        w.log.connect(self._append_log)
        w.progress.connect(self._on_progress)
        w.stage.connect(self._on_stage)
        w.ok.connect(self._on_done)
        w.fail.connect(self._on_fail)
        w.start()

    def _set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        for w in (self.loader_combo, self.source_combo, self.threads_combo,
                  self.java_combo, self.java_install_btn, self.assets_check, self.name_edit,
                  self.work_edit, self.out_edit):
            w.setEnabled(not running)
        if running:
            self.loader_ver_combo.setEnabled(False)
        else:
            self.loader_ver_combo.setEnabled(self._current_loader() != "none" and self.loader_ver_combo.count() > 0)

    def _append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    def _on_stage(self, text: str) -> None:
        self.stage_label.setText(text)

    def _on_progress(self, done: int, total: int, detail: str) -> None:
        if done < 0:
            self.percent_label.setText(detail[-90:])
            return
        if total > 0:
            pct = int(done * 100 / total)
            self.progress.setValue(pct)
            self.percent_label.setText(f"{done}/{total}  {pct}%")
        self.percent_label.setToolTip(detail)

    def _cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self.stage_label.setText("正在取消…")
            self.cancel_btn.setEnabled(False)

    def _on_done(self, path: str) -> None:
        self._set_running(False)
        self.progress.setValue(100)
        self.stage_label.setText("构建完成")
        self.stage_label.setStyleSheet(f"color: {theme.GREEN};")
        self.percent_label.setText("100%")
        self.log_view.appendPlainText(f"\n完成：{path}")
        box = QMessageBox(self)
        box.setWindowTitle("构建完成")
        box.setIcon(QMessageBox.Information)
        box.setText("成品已生成：")
        box.setInformativeText(
            f"{path}\n\n"
            "把 zip 解压出来的文件夹作为 HMCL 的游戏目录即可直接启动；\n"
            "也可以把里面的 versions / libraries / assets 合并进现有的 .minecraft。"
        )
        open_btn = box.addButton("打开输出目录", QMessageBox.ActionRole)
        box.addButton("关闭", QMessageBox.AcceptRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def _on_fail(self, msg: str) -> None:
        self._set_running(False)
        self.stage_label.setText("构建失败")
        self.stage_label.setStyleSheet(f"color: {theme.RED};")
        self.log_view.appendPlainText("\n失败：" + msg)
        QMessageBox.critical(self, "构建失败", msg[:3000])

    # ------------------------------------------------------------ window
    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            r = QMessageBox.question(
                self, "正在构建", "构建尚未完成，确定退出吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                event.ignore()
                return
            self._worker.cancel()
            self._worker.wait(3000)
        self._save_config()
        super().closeEvent(event)
