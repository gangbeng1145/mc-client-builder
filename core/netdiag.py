# -*- coding: utf-8 -*-
"""网络诊断：DNS / TCP / HTTPS / 代理 / 系统时间。"""
from __future__ import annotations

import os
import platform
import socket
import ssl
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlparse

import requests

from .constants import USER_AGENT

TARGETS = [
    ("基线（百度）", "https://www.baidu.com"),
    ("BMCLAPI 版本清单", "https://bmclapi2.bangbang93.com/mc/game/version_manifest.json"),
    ("Mojang 版本清单", "https://piston-meta.mojang.com/mc/game/version_manifest.json"),
    ("Fabric Meta", "https://meta.fabricmc.net/v2/versions/loader/1.20.1"),
]


def _proxy_env() -> dict:
    keys = ("http_proxy", "https_proxy", "all_proxy", "no_proxy",
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
    return {k: os.environ[k] for k in keys if os.environ.get(k)}


def _proxy_registry() -> dict:
    out = {}
    if sys.platform != "win32":
        return out
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        for name in ("ProxyEnable", "ProxyServer", "AutoConfigURL"):
            try:
                out[name] = winreg.QueryValueEx(key, name)[0]
            except OSError:
                pass
    except Exception as e:
        out["error"] = str(e)
    return out


def _clock_skew(server_date: Optional[str]) -> Optional[int]:
    if not server_date:
        return None
    try:
        remote = parsedate_to_datetime(server_date)
        local = datetime.now(remote.tzinfo)
        return int((local - remote).total_seconds())
    except Exception:
        return None


def diagnose() -> dict:
    data = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "proxy_env": _proxy_env(),
        "proxy_registry": _proxy_registry(),
        "targets": [],
    }
    for label, url in TARGETS:
        host = urlparse(url).hostname
        item = {"label": label, "url": url, "host": host}
        t0 = time.time()
        try:
            item["dns"] = sorted({ai[4][0] for ai in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)})
        except Exception as e:
            item["dns"] = f"失败：{type(e).__name__}: {e}"
        try:
            with socket.create_connection((host, 443), timeout=8):
                item["tcp443"] = f"通（{round((time.time() - t0) * 1000)}ms）"
        except Exception as e:
            item["tcp443"] = f"失败：{type(e).__name__}: {e}"
        t1 = time.time()
        try:
            r = requests.get(url, timeout=(8, 25), headers={"User-Agent": USER_AGENT})
            item["http"] = r.status_code
            item["bytes"] = len(r.content)
            item["elapsed"] = round(time.time() - t1, 2)
            item["server_date"] = r.headers.get("Date")
            skew = _clock_skew(item["server_date"])
            if skew is not None:
                item["clock_skew_seconds"] = skew
        except Exception as e:
            item["http"] = f"失败：{type(e).__name__}: {str(e)[:300]}"
            item["elapsed"] = round(time.time() - t1, 2)
        data["targets"].append(item)
    return data


def _cert_hint(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in ("certificate", "ssl", "tls", "wrong version number"))


def format_report(data: dict) -> str:
    lines = []
    lines.append(f"诊断时间：{data.get('time')}")
    lines.append(f"系统：{data.get('platform')}")
    lines.append(f"Python：{data.get('python')}")
    pe = data.get("proxy_env") or {}
    pr = data.get("proxy_registry") or {}
    lines.append(f"代理（环境变量）：{pe or '未设置'}")
    lines.append(f"代理（系统设置）：{pr or '未读取到'}")
    lines.append("")
    problems = []
    for it in data.get("targets", []):
        lines.append(f"■ {it['label']}")
        lines.append(f"   URL：{it['url']}")
        lines.append(f"   DNS：{it.get('dns')}")
        lines.append(f"   TCP 443：{it.get('tcp443')}")
        http = it.get("http")
        if isinstance(http, int):
            lines.append(f"   HTTP：{http}，{it.get('bytes')} 字节，{it.get('elapsed')}s")
        else:
            lines.append(f"   HTTP：{http}")
            problems.append((it, str(http)))
        skew = it.get("clock_skew_seconds")
        if skew is not None and abs(skew) > 300:
            lines.append(f"   ⚠ 本机时间与服务器相差 {skew} 秒")
        lines.append("")
    lines.append("—— 结论 ——")
    if not problems:
        lines.append("网络可以正常访问下载源。若界面仍报错，请提供截图，可能是防火墙在进程启动后才放行。")
    else:
        all_dns_fail = all("DNS" in str(p[1]) for p in problems)
        any_cert = any(_cert_hint(p[1]) for p in problems)
        any_proxy = bool(pe or pr.get("ProxyEnable"))
        if all_dns_fail:
            lines.append("所有域名解析失败：检查虚拟机网络模式（建议 NAT 或桥接）、DNS 设置。")
        elif any_cert:
            lines.append("证书校验失败：最常见是系统时间不对（虚拟机挂起/还原后常见），"
                         "请先校准 Windows 时间；其次是代理软件做了 HTTPS 拦截。")
        elif any_proxy:
            lines.append("检测到系统代理，但请求失败：检查代理是否可用，或尝试关闭代理。")
        else:
            lines.append("部分源不通：可能是 VM 防火墙或网络限制。可在软件里切换下载源，或换用能通的源。")
    return "\n".join(lines)
