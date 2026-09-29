#!/usr/bin/env python3
"""抓取某个用户的全部 GitHub Stars，精简后写入 data/stars.json。

用法：
    python3 scripts/fetch_stars.py                 # 用 GITHUB_TOKEN 对应的账号（/user/starred）
    python3 scripts/fetch_stars.py HeadmasterEggy  # 指定用户名（公开 stars，无 token 也能跑，但限流 60 次/小时）

环境变量：GITHUB_TOKEN（可选，强烈建议），STARS_USER（可代替命令行参数）。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from common import STARS_FILE, save_json

API = "https://api.github.com"


def request(url, token):
    headers = {
        # star+json 才会返回 starred_at
        "Accept": "application/vnd.github.star+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "stars-manager",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
                return json.load(resp), resp.headers.get("Link", "")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
                sys.exit(f"GitHub API 限流了（重置时间 {e.headers.get('X-RateLimit-Reset')}），请设置 GITHUB_TOKEN 后重试")
            if e.code >= 500 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            sys.exit(f"请求失败 {e.code}: {url}\n{e.read().decode(errors='replace')[:300]}")
        except urllib.error.URLError:
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise


def next_link(link_header):
    m = re.search(r'<([^>]+)>;\s*rel="next"', link_header or "")
    return m.group(1) if m else None


def slim(item):
    """只保留分类和展示需要的字段，避免备份文件动辄几十 MB。"""
    repo = item.get("repo", item)
    return {
        "full_name": repo["full_name"],
        "name": repo["name"],
        "owner": repo["owner"]["login"],
        "url": repo["html_url"],
        "description": repo.get("description") or "",
        "language": repo.get("language") or "",
        "topics": repo.get("topics") or [],
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "archived": repo.get("archived", False),
        "homepage": repo.get("homepage") or "",
        "license": (repo.get("license") or {}).get("spdx_id") or "",
        "pushed_at": repo.get("pushed_at"),
        "starred_at": item.get("starred_at"),
    }


def fetch_all_stars(username=None, token=None):
    path = f"/users/{username}/starred" if username else "/user/starred"
    url = f"{API}{path}?per_page=100"
    stars = []
    while url:
        page, link = request(url, token)
        stars.extend(slim(x) for x in page)
        print(f"  已获取 {len(stars)} 个", file=sys.stderr)
        url = next_link(link)
    return stars


def main():
    username = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STARS_USER")) or None
    token = os.environ.get("GITHUB_TOKEN") or None
    if not username and not token:
        sys.exit("需要用户名参数，或设置 GITHUB_TOKEN")
    stars = fetch_all_stars(username, token)
    stars.sort(key=lambda r: r.get("starred_at") or "", reverse=True)
    save_json(STARS_FILE, {
        "user": username or "(token owner)",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(stars),
        "repos": stars,
    })
    print(f"共 {len(stars)} 个 star → {STARS_FILE.relative_to(STARS_FILE.parents[1])}")


if __name__ == "__main__":
    main()
