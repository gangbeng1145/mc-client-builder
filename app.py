# -*- coding: utf-8 -*-
"""MC 客户端构建器 入口。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# PyInstaller 打包后资源在临时目录，源码运行时在脚本目录
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(BASE_DIR))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui import theme  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

TEST_DIR = Path(os.environ.get("MC_TEST_OUT") or Path.cwd())


def main() -> int:
    if "--netdiag" in sys.argv:
        from core.netdiag import diagnose, format_report

        idx = sys.argv.index("--netdiag")
        out = Path(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else TEST_DIR / "netdiag.txt"
        text = format_report(diagnose())
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        try:
            os.startfile(str(out))
        except Exception:
            pass
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("MC 客户端构建器")
    app.setOrganizationName("MCBuilder")
    theme.apply_theme(app)

    icon_path = BASE_DIR / "assets" / "icon.png"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    win = MainWindow()
    win.show()

    if "--smoke" in sys.argv:
        out = TEST_DIR / "smoke.png"

        def shoot():
            win.grab().save(str(out))
            app.quit()

        QTimer.singleShot(6000, shoot)

    if "--selftest" in sys.argv:
        idx = sys.argv.index("--selftest")
        out = Path(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else TEST_DIR / "selftest.json"

        def check():
            if not win.all_versions or not win.java_combo.currentData():
                QTimer.singleShot(1000, check)
                return
            import platform

            import PySide6

            data = {
                "ok": True,
                "qt": PySide6.__version__,
                "versions": len(win.all_versions),
                "javas": win.java_combo.count(),
                "frozen": bool(getattr(sys, "frozen", False)),
                "platform": platform.platform(),
                "exe": sys.executable,
            }
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            app.quit()

        QTimer.singleShot(2500, check)

    if "--auto-test" in sys.argv:
        out_ok = TEST_DIR / "auto_ok.png"
        out_fail = TEST_DIR / "auto_fail.png"

        def patched_done(path):
            win.progress.setValue(100)
            win.grab().save(str(out_ok))
            print("AUTO_OK", path, flush=True)
            app.quit()

        def patched_fail(msg):
            win.grab().save(str(out_fail))
            print("AUTO_FAIL", msg, flush=True)
            app.quit()

        win._on_done = patched_done
        win._on_fail = patched_fail

        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning = staticmethod(lambda *a, **k: print("[dialog] warn:", a[2:], flush=True))
        QMessageBox.critical = staticmethod(lambda *a, **k: print("[dialog] crit:", a[2:], flush=True))
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

        def start_auto():
            if not win.all_versions or not win.java_combo.currentData():
                QTimer.singleShot(1000, start_auto)
                return
            win.name_edit.setText("gui-auto")
            win.work_edit.setText(str(Path(tempfile.gettempdir()) / "mc_builder_test"))
            win.out_edit.setText(str(Path(tempfile.gettempdir()) / "mc_builder_test_out"))
            win.assets_check.setChecked(False)
            win.search.setText("1.20.1")
            model = win.version_list.model()
            target = None
            for row in range(model.rowCount()):
                idx = model.index(row, 0)
                if idx.data() == "1.20.1":
                    target = idx
                    break
            if target is None and model.rowCount():
                target = model.index(0, 0)
            if target is None:
                QTimer.singleShot(1000, start_auto)
                return
            win.version_list.setCurrentIndex(target)
            QTimer.singleShot(800, win._start_install)

        QTimer.singleShot(3000, start_auto)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
