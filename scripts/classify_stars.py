#!/usr/bin/env python3
"""给 data/stars.json 里的仓库分类，结果写入 data/classifications.json。

优先级：config/overrides.json（手动）> AI 分类结果（缓存，只对新仓库调用）> 规则分类（config/categories.json）

用法：
    python3 scripts/classify_stars.py              # 仅规则分类（免费、离线）；已有的 AI 结果会保留
    python3 scripts/classify_stars.py --ai         # 对还没有 AI 结果的仓库调用 Claude（需 ANTHROPIC_API_KEY）
    python3 scripts/classify_stars.py --ai --all   # 全部重新用 AI 分类
"""
import argparse
import json
import os
import re
import sys

from common import CLASSIFIED_FILE, STARS_FILE, load_categories, load_json, load_overrides, save_json

AI_MODEL = os.environ.get("STARS_AI_MODEL", "claude-opus-5-5")
AI_BATCH = 40


def _has_cjk(s):
    return re.search(r"[一-鿿]", s) is not None


def rule_classify(repo, cfg):
    topics = {t.lower() for t in repo["topics"]}
    text = f"{repo['name']} {repo['description']} {' '.join(repo['topics'])}".lower()
    for cat in cfg["categories"]:
        if topics & {t.lower() for t in cat.get("topics", [])}:
            return cat["name"]
        if repo["language"] and repo["language"] in cat.get("languages", []):
            return cat["name"]
        for kw in cat.get("keywords", []):
            kw = kw.lower()
            # 英文关键词按整词匹配（避免 "cli" 命中 "client"），中文直接子串匹配
            if (kw in text) if _has_cjk(kw) else re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", text):
                return cat["name"]
    return cfg["fallback"]


def ai_classify(repos, names, cfg):
    """批量调用 Claude，用结构化输出保证返回的分类名一定在列表里。"""
    import anthropic

    client = anthropic.Anthropic()
    guide = "\n".join(
        f"- {c['name']}：参考 {', '.join((c.get('topics') or [])[:8])}" for c in cfg["categories"]
    ) + f"\n- {cfg['fallback']}：以上都不合适时使用"
    schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "full_name": {"type": "string"},
                        "category": {"type": "string", "enum": names},
                    },
                    "required": ["full_name", "category"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["results"],
        "additionalProperties": False,
    }
    out = {}
    for i in range(0, len(repos), AI_BATCH):
        batch = repos[i:i + AI_BATCH]
        items = [
            {"full_name": r["full_name"], "description": r["description"][:300],
             "language": r["language"], "topics": r["topics"][:10]}
            for r in batch
        ]
        prompt = (
            "把下面这些 GitHub 仓库各归入一个分类。分类说明：\n"
            f"{guide}\n\n"
            "判断依据是仓库“主要用途”：例如 awesome 列表、教程归学习资源；做 agent 框架的归 AI Agent，"
            "而普通的大模型推理/训练/RAG 库归 LLM & 大模型。每个仓库都要返回，full_name 原样照抄。\n\n"
            + json.dumps(items, ensure_ascii=False)
        )
        try:
            resp = client.beta.messages.create(
                model=AI_MODEL,
                max_tokens=8000,
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": schema},
                },
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIStatusError as e:
            print(f"  AI 分类第 {i // AI_BATCH + 1} 批失败（{e.status_code}），这批用规则分类", file=sys.stderr)
            continue
        except anthropic.APIConnectionError:
            print(f"  AI 分类第 {i // AI_BATCH + 1} 批连接失败，这批用规则分类", file=sys.stderr)
            continue
        if resp.stop_reason != "end_turn":
            print(f"  第 {i // AI_BATCH + 1} 批 stop_reason={resp.stop_reason}，这批用规则分类", file=sys.stderr)
            continue
        text = next(b.text for b in resp.content if b.type == "text")
        wanted = {r["full_name"] for r in batch}
        for row in json.loads(text)["results"]:
            if row["full_name"] in wanted:
                out[row["full_name"]] = row["category"]
        print(f"  AI 已分类 {min(i + AI_BATCH, len(repos))}/{len(repos)}", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ai", action="store_true", help="用 Claude 分类（需要 ANTHROPIC_API_KEY）")
    ap.add_argument("--all", action="store_true", help="配合 --ai：忽略缓存，全部重新分类")
    args = ap.parse_args()

    stars = load_json(STARS_FILE)
    if not stars:
        sys.exit(f"找不到 {STARS_FILE}，先运行 scripts/fetch_stars.py")
    cfg, names = load_categories()
    overrides = load_overrides()
    previous = load_json(CLASSIFIED_FILE, {}) or {}

    # 之前的 AI 结果（且分类名还有效）继续沿用，省钱
    ai_cache = {} if args.all else {
        k: v["category"] for k, v in previous.items()
        if v.get("source") == "ai" and v.get("category") in names
    }

    if args.ai:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("--ai 需要设置 ANTHROPIC_API_KEY")
        todo = [r for r in stars["repos"] if r["full_name"] not in ai_cache and r["full_name"] not in overrides]
        print(f"需要 AI 分类的仓库：{len(todo)} 个", file=sys.stderr)
        if todo:
            ai_cache.update(ai_classify(todo, names, cfg))

    result = {}
    for repo in stars["repos"]:
        fn = repo["full_name"]
        if overrides.get(fn) in names:
            result[fn] = {"category": overrides[fn], "source": "manual"}
        elif fn in ai_cache:
            result[fn] = {"category": ai_cache[fn], "source": "ai"}
        else:
            result[fn] = {"category": rule_classify(repo, cfg), "source": "rule"}
    for fn, cat in overrides.items():
        if cat not in names:
            print(f"  警告：overrides 里 {fn} 的分类“{cat}”不存在，已忽略", file=sys.stderr)

    save_json(CLASSIFIED_FILE, dict(sorted(result.items())))
    counts = {n: 0 for n in names}
    for v in result.values():
        counts[v["category"]] += 1
    for n in names:
        print(f"  {n:<16} {counts[n]}")
    print(f"分类完成 → data/classifications.json")


if __name__ == "__main__":
    main()
