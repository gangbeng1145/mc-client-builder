# -*- coding: utf-8 -*-
"""安装 Java 运行时对话框。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from core.java_install import install_runtime, list_runtimes
from core.net import Downloader

from . import theme


class RuntimesWorker(QThread):
    ok = Signal(list)
    fail = Signal(str)

    def __init__(self, work: Path, source: str):
        super().__init__()
        self.work = work
        self.source = source

    def run(self):
        try:
            dl = Downloader(self.work / ".cache", source=self.source)
            self.ok.emit(list_runtimes(dl))
        except Exception as e:
            self.fail.emit(str(e))


class JavaInstallWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int, str)
    stage = Signal(str)
    ok = Signal(str)
    fail = Signal(str)

    def __init__(self, work: Path, component: str, source: str, threads: int):
        super().__init__()
        self.work = work
        self.component = component
        self.source = source
        self.threads = threads
        self._dl: Downloader | None = None

    def run(self):
        try:
            self._dl = Downloader(
                self.work / ".cache", source=self.source, concurrency=self.threads,
                log=self.log.emit,
            )
            path = install_runtime(
                self._dl, self.work / "java", self.component,
                log=self.log.emit, stage=self.stage.emit,
            )
            self.ok.emit(str(path))
        except Exception as e:
            self.fail.emit(f"{type(e).__name__}: {e}")

    def cancel(self):
        if self._dl:
            self._dl.cancel()


class JavaInstallDialog(QDialog):
    def __init__(self, work: Path, source: str, threads: int, parent=None):
        super().__init__(parent)
        self.work = Path(work)
        self.source = source
        self.threads = threads
        self.result_path: str = ""
        self._runtimes: list[dict] = []
        self._worker: JavaInstallWorker | None = None

        self.setWindowTitle("安装 Java 运行时")
        self.resize(680, 480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        title = QLabel("安装 Java 运行时")
        title.setObjectName("SectionTitle")
        lay.addWidget(title)

        tip = QLabel(f"下载到：{self.work / 'java'}\n来源：Mojang 官方运行时（和 HMCL 使用同一套清单）")
        tip.setObjectName("Hint")
        lay.addWidget(tip)

        row = QHBoxLayout()
        row.addWidget(QLabel("运行时"))
        self.combo = QComboBox()
        self.combo.addItem("正在读取可用版本…", "")
        self.combo.setEnabled(False)
        row.addWidget(self.combo, 1)
        lay.addLayout(row)

        self.stage_label = QLabel("")
        self.stage_label.setObjectName("Stage")
        lay.addWidget(self.stage_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        lay.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000)
        lay.addWidget(self.log_view, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.cancel_btn = QPushButton("关闭")
        self.cancel_btn.setObjectName("Ghost")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btns.addWidget(self.cancel_btn)
        self.install_btn = QPushButton("开始安装")
        self.install_btn.setObjectName("Primary")
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self._start)
        btns.addWidget(self.install_btn)
        lay.addLayout(btns)

        self._loader = RuntimesWorker(self.work, self.source)
        self._loader.ok.connect(self._on_runtimes)
        self._loader.fail.connect(self._on_runtimes_fail)
        self._loader.start()

    # ------------------------------------------------------------ data
    def _on_runtimes(self, items: list):
        self._runtimes = items
        self.combo.clear()
        for it in items:
            self.combo.addItem(f"{it['label']}  ·  {it['version']}", it["component"])
        self.combo.setEnabled(bool(items))
        self.install_btn.setEnabled(bool(items))

    def _on_runtimes_fail(self, msg: str):
        self.combo.clear()
        self.combo.addItem("读取失败", "")
        self.log_view.appendPlainText("读取 Java 列表失败：" + msg)

    # ------------------------------------------------------------ install
    def _start(self):
        comp = self.combo.currentData()
        if not comp or self._worker:
            return
        self.install_btn.setEnabled(False)
        self.cancel_btn.setText("取消")
        self.log_view.appendPlainText(f"\n开始安装 {self.combo.currentText()}")
        w = JavaInstallWorker(self.work, comp, self.source, self.threads)
        self._worker = w
        w.log.connect(self.log_view.appendPlainText)
        w.stage.connect(self.stage_label.setText)
        w.progress.connect(self._on_progress)
        w.ok.connect(self._on_ok)
        w.fail.connect(self._on_fail)
        w.start()

    def _on_progress(self, done: int, total: int, detail: str):
        if done < 0:
            return
        if total:
            self.progress.setValue(int(done * 100 / total))

    def _on_ok(self, path: str):
        self.result_path = path
        self.stage_label.setText("安装完成")
        self.log_view.appendPlainText(f"完成：{path}")
        self.accept()

    def _on_fail(self, msg: str):
        self._worker = None
        self.cancel_btn.setText("关闭")
        self.install_btn.setEnabled(True)
        self.stage_label.setText("安装失败")
        self.log_view.appendPlainText("失败：" + msg)

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(2000)
            self._worker = None
        self.reject()

    def closeEvent(self, event):
        if self._worker:
            self._worker.cancel()
        super().closeEvent(event)
