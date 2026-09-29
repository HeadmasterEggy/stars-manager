# stars-manager

自动化管理 GitHub Stars 的分类工具集：抓取 → 分类（规则 / Claude）→ 生成 [`STARS.md`](STARS.md) 和一个可搜索的网页。

GitHub Actions 每周一自动跑一遍并提交结果，平时不用管。

## 目录结构

```
stars-manager/
├── scripts/
│   ├── fetch_stars.py        # 抓取全部 star（只用标准库，自动翻页）
│   ├── classify_stars.py     # 分类：手动 > AI（有缓存）> 关键词规则
│   ├── generate_readme.py    # 生成 STARS.md 和 docs/data.json
│   └── common.py
├── config/
│   ├── categories.json       # 分类及匹配规则（topics / 关键词 / 语言）
│   └── overrides.json        # 手动指定某个仓库的分类
├── data/
│   ├── stars.json            # 抓取结果（精简字段，也是备份）
│   └── classifications.json  # 分类结果 + AI 分类缓存
├── docs/index.html           # 网页：搜索 / 按分类、语言筛选 / 排序 / 统计
├── .github/workflows/update-stars.yml
└── STARS.md                  # 生成的分类列表（别手改）
```

## 本地运行

```bash
export GITHUB_TOKEN=ghp_xxx                     # 可选，不设置每小时只能请求 60 次
python3 scripts/fetch_stars.py HeadmasterEggy
python3 scripts/classify_stars.py               # 规则分类，免费、离线
python3 scripts/generate_readme.py

# 预览网页（直接双击 html 打不开，fetch 需要 HTTP）
python3 -m http.server -d docs 8000             # 打开 http://localhost:8000
```

### 用 Claude 分类（可选）

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-xxx
python3 scripts/classify_stars.py --ai          # 只给还没 AI 分类过的仓库分类
python3 scripts/classify_stars.py --ai --all    # 全部重新分类
```

- 每 40 个仓库一次请求，用结构化输出保证返回的分类名一定在 `categories.json` 里。
- 结果缓存在 `data/classifications.json`，之后每周只会为新 star 的仓库付费。
- 某一批失败时这批退回规则分类，不会中断。
- 默认模型 `claude-opus-5-5`，可用环境变量 `STARS_AI_MODEL` 换。

## 调整分类

- **改分类体系 / 规则**：编辑 `config/categories.json`。按顺序匹配，命中第一个即归类；`topics` 精确匹配仓库 topic，`keywords` 在仓库名、简介、topic 里按整词匹配（中文按子串），`languages` 匹配主语言。
- **某个仓库分错了**：在 `config/overrides.json` 里加 `"owner/repo": "分类名"`，优先级最高。

## 自动化（GitHub Actions）

`.github/workflows/update-stars.yml` 每周一 10:17（北京时间）运行，也可以在 Actions 页面手动触发（可勾选“用 AI 全部重新分类”）。

- 默认抓取仓库所有者（`github.repository_owner`）的公开 stars，用自带的 `GITHUB_TOKEN`，无需配置。
- 想用 AI 分类：在仓库 **Settings → Secrets and variables → Actions** 添加 `ANTHROPIC_API_KEY`。不加就用规则分类。
- 需要仓库 **Settings → Actions → General → Workflow permissions** 为 “Read and write”，才能提交结果。

## 网页展示（GitHub Pages）

仓库 **Settings → Pages** → Source 选 “Deploy from a branch”，分支 `main`、目录 `/docs`。之后访问 `https://headmastereggy.github.io/stars-manager/`。

## 关于 GitHub Lists

GitHub 的 Star Lists 目前没有公开 API，脚本无法自动同步，所以没有做 `sync_collections.py`。可以对照 `STARS.md` 手动整理。
