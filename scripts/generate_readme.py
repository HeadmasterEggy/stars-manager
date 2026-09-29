#!/usr/bin/env python3
"""根据 stars.json + classifications.json 生成 STARS.md 和网页数据 docs/data.json。"""
import sys
from datetime import datetime, timezone

from common import CLASSIFIED_FILE, DOCS_DIR, ROOT, STARS_FILE, load_categories, load_json, save_json


def anchor(name):
    """GitHub 标题锚点：小写、去掉标点、空格变连字符。"""
    out = []
    for ch in name.lower():
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        elif ch == " ":
            out.append("-")
    return "".join(out)


def md_escape(s):
    return s.replace("|", "\\|").replace("\n", " ").strip()


def fmt_stars(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def main():
    stars = load_json(STARS_FILE)
    classified = load_json(CLASSIFIED_FILE)
    if not stars or classified is None:
        sys.exit("缺少 data/stars.json 或 data/classifications.json，先运行 fetch_stars.py 和 classify_stars.py")
    cfg, names = load_categories()
    emoji = {c["name"]: c.get("emoji", "") for c in cfg["categories"]}
    emoji.setdefault(cfg["fallback"], "📦")

    groups = {n: [] for n in names}
    for repo in stars["repos"]:
        cat = classified.get(repo["full_name"], {}).get("category", cfg["fallback"])
        groups.setdefault(cat, []).append(repo)

    total = len(stars["repos"])
    date = stars["fetched_at"][:10]
    lines = [
        "# 🌟 我的 GitHub Stars 分类",
        "",
        f"> 共 **{total}** 个项目 · 数据更新于 {date} · 由 [stars-manager](README.md) 自动生成，请勿手改",
        "",
        "## 目录",
        "",
    ]
    for n, repos in groups.items():
        if repos:
            lines.append(f"- [{emoji.get(n, '')} {n}](#{anchor(emoji.get(n, '') + ' ' + n + f' ({len(repos)})')}) — {len(repos)}")
    lines.append("")
    for n, repos in groups.items():
        if not repos:
            continue
        lines += [f"## {emoji.get(n, '')} {n} ({len(repos)})", "", "| 项目 | 简介 | ⭐ | 语言 |", "|---|---|---|---|"]
        for r in sorted(repos, key=lambda x: x["stars"], reverse=True):
            name = f"[{r['full_name']}]({r['url']})" + (" 🗄️" if r["archived"] else "")
            lines.append(f"| {name} | {md_escape(r['description'])} | {fmt_stars(r['stars'])} | {r['language']} |")
        lines.append("")
    (ROOT / "STARS.md").write_text("\n".join(lines), encoding="utf-8")

    # 网页数据：只放展示需要的字段
    save_json(DOCS_DIR / "data.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fetched_at": stars["fetched_at"],
        "categories": [{"name": n, "emoji": emoji.get(n, "")} for n in groups],
        "repos": [
            {**{k: r[k] for k in ("full_name", "url", "description", "language", "topics",
                                  "stars", "archived", "starred_at", "pushed_at")},
             "category": classified.get(r["full_name"], {}).get("category", cfg["fallback"])}
            for r in stars["repos"]
        ],
    })
    print(f"已生成 STARS.md 和 docs/data.json（{total} 个项目）")


if __name__ == "__main__":
    main()
