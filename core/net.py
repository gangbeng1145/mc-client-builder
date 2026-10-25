# -*- coding: utf-8 -*-
"""下载器：多源回退、并发、SHA-1 校验、按哈希缓存、原子写入。"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterable, Optional

import requests

from .constants import USER_AGENT
from .util import hardlink_or_copy, sha1_file, url_candidates


class DownloadCancelled(Exception):
    pass


class DownloadError(Exception):
    pass


class Downloader:
    def __init__(
        self,
        cache_dir: Path,
        source: str = "auto",
        log: Optional[Callable[[str], None]] = None,
        progress: Optional[Callable[[int, int, str], None]] = None,
        concurrency: int = 24,
    ):
        self.cache_dir = Path(cache_dir)
        self.source = source
        self.log = log or (lambda s: None)
        self.progress = progress or (lambda d, t, s: None)
        self.concurrency = max(1, concurrency)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._meta: dict[str, object] = {}
        self._bytes = 0
        self._last_report = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
        (self.cache_dir / "objects").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ control
    def cancel(self) -> None:
        self._stop.set()

    def check_cancel(self) -> None:
        if self._stop.is_set():
            raise DownloadCancelled("已取消")

    # ------------------------------------------------------------ low level
    def _get(self, url: str, stream: bool = False, timeout=(10, 60)):
        last = None
        for attempt in range(3):
            self.check_cancel()
            try:
                r = self.session.get(url, stream=stream, timeout=timeout)
                if r.status_code in (403, 404, 410):
                    raise DownloadError(f"HTTP {r.status_code}: {url}")
                if r.status_code >= 400:
                    raise DownloadError(f"HTTP {r.status_code}: {url}")
                return r
            except DownloadCancelled:
                raise
            except DownloadError:
                raise
            except Exception as e:  # 网络类错误重试
                last = e
                time.sleep(0.6 * (attempt + 1))
        raise DownloadError(f"{last} ({url})")

    def get_bytes(self, urls: Iterable[str]) -> bytes:
        errors = []
        for url in urls:
            try:
                r = self._get(url)
                return r.content
            except DownloadCancelled:
                raise
            except Exception as e:
                errors.append(str(e))
                self.log(f"  失败：{url}  ({e})")
        raise DownloadError("所有下载源都失败：\n" + "\n".join(errors))

    def get_json(self, urls: Iterable[str], key: Optional[str] = None):
        if key and key in self._meta:
            return self._meta[key]
        data = json.loads(self.get_bytes(urls).decode("utf-8", "replace"))
        if key:
            self._meta[key] = data
        return data

    # ------------------------------------------------------------ file
    def _dest_ok(self, dest: Path, sha1: Optional[str], size: Optional[int]) -> bool:
        if not dest.is_file():
            return False
        if size is not None and dest.stat().st_size != size:
            return False
        if sha1:
            try:
                if sha1_file(dest).lower() != sha1.lower():
                    return False
            except OSError:
                return False
        return True

    def _cache_path(self, sha1: str) -> Path:
        sha1 = sha1.lower()
        return self.cache_dir / "objects" / sha1[:2] / sha1

    def download(
        self,
        urls: Iterable[str],
        dest: Path,
        sha1: Optional[str] = None,
        size: Optional[int] = None,
        label: str = "",
    ) -> int:
        dest = Path(dest)
        if self._dest_ok(dest, sha1, size):
            return 0
        if sha1:
            cached = self._cache_path(sha1)
            if cached.is_file() and self._dest_ok(cached, sha1, size):
                hardlink_or_copy(cached, dest)
                return 0

        dest.parent.mkdir(parents=True, exist_ok=True)
        errors = []
        for url in urls:
            try:
                r = self._get(url, stream=True)
                tmp = dest.with_name(dest.name + ".part")
                h = hashlib.sha1()
                count = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        if not chunk:
                            continue
                        self.check_cancel()
                        h.update(chunk)
                        f.write(chunk)
                        count += len(chunk)
                        with self._lock:
                            self._bytes += len(chunk)
                        self._report_bytes(label)
                actual = h.hexdigest()
                if sha1 and actual.lower() != sha1.lower():
                    tmp.unlink(missing_ok=True)
                    raise DownloadError(f"SHA-1 不匹配：{dest.name}")
                if size is not None and count != size:
                    tmp.unlink(missing_ok=True)
                    raise DownloadError(f"大小不符：{dest.name} {count} != {size}")
                os.replace(tmp, dest)
                if sha1:
                    cached = self._cache_path(sha1)
                    if not cached.is_file():
                        try:
                            hardlink_or_copy(dest, cached)
                        except OSError:
                            pass
                return count
            except DownloadCancelled:
                raise
            except Exception as e:
                errors.append(f"{url} -> {e}")
                self.log(f"  下载失败：{label or dest.name}  {e}")
        raise DownloadError(f"下载失败：{label or dest.name}\n" + "\n".join(errors))

    def _report_bytes(self, label: str) -> None:
        now = time.time()
        if now - self._last_report > 0.15:
            self._last_report = now
            with self._lock:
                total = self._bytes
            self.progress(-1, -1, f"{label}  {total / 1048576:.1f} MB")

    # ------------------------------------------------------------ batch
    def download_many(self, items: list[dict], stage: str = "") -> None:
        """items: {urls, path, sha1, size, label}"""
        todo = [it for it in items if not self._dest_ok(Path(it["path"]), it.get("sha1"), it.get("size"))]
        skipped = len(items) - len(todo)
        total = len(items)
        done = skipped
        if skipped:
            self.log(f"  {stage}：已存在 {skipped} 个文件，跳过")
        self.progress(done, total, stage)

        errors: list[tuple[dict, Exception]] = []
        lock = threading.Lock()

        def work(item: dict):
            self.download(item["urls"], Path(item["path"]), item.get("sha1"), item.get("size"), item.get("label", ""))
            return item

        if todo:
            with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
                futures = {ex.submit(work, it): it for it in todo}
                try:
                    for fut in as_completed(futures):
                        item = futures[fut]
                        try:
                            fut.result()
                        except DownloadCancelled:
                            raise
                        except Exception as e:
                            errors.append((item, e))
                        with lock:
                            done += 1
                        self.progress(done, total, f"{stage} · {item.get('label', '')}")
                finally:
                    for f in futures:
                        f.cancel()

        if errors:
            self.log(f"  {len(errors)} 个文件失败，重试一次…")
            retry_errors = []
            for item, first in errors:
                try:
                    self.download(item["urls"], Path(item["path"]), item.get("sha1"), item.get("size"), item.get("label", ""))
                except Exception as e:
                    retry_errors.append(f"{item.get('label')}: {e}")
            if retry_errors:
                raise DownloadError("以下文件下载失败：\n" + "\n".join(retry_errors[:20]))
