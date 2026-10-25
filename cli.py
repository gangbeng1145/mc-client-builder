# -*- coding: utf-8 -*-
"""命令行测试入口（GUI 之前用来验证核心流程）。"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.installer import InstallOptions, Installer  # noqa: E402
from core.java_install import install_runtime  # noqa: E402
from core.net import Downloader  # noqa: E402
from core.util import find_javas  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", default="1.20.1")
    ap.add_argument("--loader", default="none", choices=["none", "forge", "optifine", "fabric", "quilt"])
    ap.add_argument("--loader-version", default="")
    ap.add_argument("--work", default=str(Path.home() / "MC_Downloader_Work"))
    ap.add_argument("--out", default=str(Path.home() / "MC_Downloader_Out"))
    ap.add_argument("--name", default="")
    ap.add_argument("--java", default="")
    ap.add_argument("--source", default="auto")
    ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--install-java", default="", help="只安装 Java 运行时，例如 java-runtime-beta")
    ap.add_argument("--no-assets", action="store_true")
    args = ap.parse_args()

    if args.install_java:
        dl = Downloader(Path(args.work) / ".cache", source=args.source,
                        concurrency=args.threads, log=print)
        path = install_runtime(dl, Path(args.work) / "java", args.install_java,
                               log=print, stage=lambda s: print(f"=== {s} ==="))
        print("JAVA:", path)
        return 0

    javas = find_javas()
    if not args.java:
        if not javas:
            print("找不到 Java，请用 --java 指定")
            return 1
        args.java = javas[0]["path"]
        print("自动选择 Java：", args.java, "版本", javas[0]["version"])

    name = args.name or (args.mc if args.loader == "none" else f"{args.mc}-{args.loader}")
    opt = InstallOptions(
        work_root=Path(args.work),
        output_dir=Path(args.out),
        instance_name=name,
        mc_version=args.mc,
        loader=args.loader,
        loader_version=args.loader_version,
        java_path=args.java,
        source=args.source,
        include_assets=not args.no_assets,
        threads=args.threads,
    )

    last = [0.0]

    def log(s: str):
        print(s, flush=True)

    def progress(done: int, total: int, detail: str):
        now = time.time()
        if now - last[0] < 0.5 and done not in (0, total):
            return
        last[0] = now
        if done < 0:
            print(f"\r  {detail}", end="", flush=True)
        else:
            pct = (done / total * 100) if total else 0
            print(f"\r  [{done}/{total}] {pct:5.1f}%  {detail[:80]}", end="", flush=True)

    def stage(s: str):
        print(f"\n=== {s} ===", flush=True)

    t0 = time.time()
    inst = Installer(opt, log=log, progress=progress, stage=stage)
    try:
        z = inst.run()
    except KeyboardInterrupt:
        inst.cancel()
        print("\n已取消")
        return 130
    print(f"\n完成：{z}  用时 {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
