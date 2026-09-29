"""各脚本共用的路径与 JSON 读写。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

STARS_FILE = DATA_DIR / "stars.json"                    # fetch_stars.py 输出
CLASSIFIED_FILE = DATA_DIR / "classifications.json"     # classify_stars.py 输出（也是 AI 分类缓存）
CATEGORIES_FILE = CONFIG_DIR / "categories.json"
OVERRIDES_FILE = CONFIG_DIR / "overrides.json"


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_categories():
    cfg = load_json(CATEGORIES_FILE)
    names = [c["name"] for c in cfg["categories"]]
    if cfg["fallback"] not in names:
        names.append(cfg["fallback"])
    return cfg, names


def load_overrides():
    return {k: v for k, v in (load_json(OVERRIDES_FILE, {}) or {}).items() if not k.startswith("_")}
