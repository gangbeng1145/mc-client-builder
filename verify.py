# -*- coding: utf-8 -*-
"""独立校验器：按 launcher 规范合并 inheritsFrom，检查 classpath / assets / mainClass。

用法：
    python verify.py <游戏目录> <版本id>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.util import maven_path, rules_allow  # noqa: E402


def load_chain(root: Path, vid: str) -> list[dict]:
    chain = []
    seen = set()
    cur = vid
    while cur and cur not in seen:
        seen.add(cur)
        p = root / "versions" / cur / f"{cur}.json"
        if not p.is_file():
            raise FileNotFoundError(f"缺少版本 JSON：{p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        chain.append(data)
        cur = data.get("inheritsFrom")
    return list(reversed(chain))


def merge(chain: list[dict]) -> dict:
    out: dict = {"libraries": [], "arguments": {"game": [], "jvm": []}}
    libs_seen = set()
    for data in chain:
        for k, v in data.items():
            if k in ("libraries", "arguments", "id", "inheritsFrom"):
                continue
            if k == "minecraftArguments" and out.get("minecraftArguments"):
                continue
            out[k] = v
        for lib in data.get("libraries", []):
            name = lib.get("name")
            if name in libs_seen:
                continue
            libs_seen.add(name)
            out["libraries"].append(lib)
        args = data.get("arguments") or {}
        for key in ("game", "jvm"):
            out["arguments"].setdefault(key, []).extend(args.get(key, []))
    # id 用最子层
    out["id"] = chain[-1]["id"]
    return out


def lib_file(root: Path, lib: dict) -> Path | None:
    art = ((lib.get("downloads") or {}).get("artifact")) or {}
    if art.get("path"):
        return root / "libraries" / art["path"]
    name = lib.get("name", "")
    rel = maven_path(name)
    return root / "libraries" / rel if rel else None


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: python verify.py <游戏目录> <版本id>")
        return 2
    root = Path(sys.argv[1])
    vid = sys.argv[2]
    chain = load_chain(root, vid)
    v = merge(chain)
    libs = [l for l in v["libraries"] if rules_allow(l.get("rules"))]
    missing = []
    for lib in libs:
        art = ((lib.get("downloads") or {}).get("artifact")) or {}
        if not art.get("path") and not lib.get("url"):
            # 只有 natives 分类器的库（如 1.12.2 的 jinput-platform），没有主 jar 是正常的
            continue
        f = lib_file(root, lib)
        if f and not f.is_file():
            missing.append(str(f.relative_to(root)))
    jar = None
    for data in reversed(chain):
        cand = root / "versions" / data["id"] / f"{data['id']}.jar"
        if cand.is_file():
            jar = cand
            break
    if jar is None and v.get("jar"):
        jar = root / "versions" / v["jar"] / f"{v['jar']}.jar"
    print(f"版本：{vid}  继承链：{' -> '.join(d['id'] for d in chain)}")
    print(f"mainClass：{v.get('mainClass')}")
    print(f"libraries：{len(libs)} 个（缺失 {len(missing)}）")
    for m in missing[:20]:
        print("   缺:", m)
    jar_ok = jar is not None and jar.is_file()
    print(f"client jar：{'OK' if jar_ok else '缺失'}  {jar}")

    ai = v.get("assetIndex") or {}
    ai_id = ai.get("id")
    index = root / "assets" / "indexes" / f"{ai_id}.json"
    if index.is_file():
        data = json.loads(index.read_text(encoding="utf-8"))
        objs = data.get("objects") or {}
        miss = 0
        for obj in objs.values():
            h = obj["hash"]
            if not (root / "assets" / "objects" / h[:2] / h).is_file():
                miss += 1
        print(f"assets：{len(objs)} 个对象，缺失 {miss}")
    else:
        print(f"assets：缺少索引 {index}")

    ok = not missing and jar_ok and index.is_file()
    print("结论：", "结构完整，可被 HMCL 解析" if ok else "存在问题")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
