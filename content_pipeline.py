#!/usr/bin/env python3
"""
サイトに掲載する記事を1本組み立てるパイプライン。

rakuten_threads_bot/main.py と同じ「ジャンルローテーション+状態ファイル」の仕組みを流用し、
1回の呼び出しで以下のどちらか1本の記事データ(dict)を返す。

  - 商品紹介・比較記事: 楽天APIの実データ(複数商品)を根拠にAIが執筆。楽天アフィリエイトリンクを本文に挿入。
  - 情報系記事: 商品を紹介しない、検索に強いお役立ち記事。広告(アドセンス)向け。

生成失敗時は None を返す(呼び出し側でログに残すだけで、テンプレートへのフォールバックは行わない
 = 実データに基づかない記事を「それっぽく」出さないための安全側の設計)。
"""

import json
import os
import random
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

import claude_writer as ai_writer  # Gemini版ai_writerから、Claude Code CLI版に切り替え(2026-09-10)
import rakuten_source

load_dotenv()

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "bot_state.json"
POSTED_FILE = BASE_DIR / "posted_articles.json"

INFO_RATIO = float(os.environ.get("SITE_ARTICLE_TYPE_RATIO", "0.5"))  # 情報系記事になる確率
ITEMS_PER_PRODUCT_ARTICLE = 3

# ── ジャンルの定義。増やす場合はここに追記するだけでローテーション対象になる ──
GENRES = [
    {
        "id": "beauty",
        "label": "メンズ美容",
        "keyword": "メンズコスメ",
        "color": "#b45309",
        "photo_query": "men skincare grooming",
        "info_topics": [
            "メンズスキンケアの正しい順番",
            "清潔感を出すための髭・眉の整え方",
            "脂性肌・乾燥肌に合わせたメンズ化粧水の選び方",
            "メンズコスメの使用期限と保管方法",
            "朝だけでできる清潔感アップの習慣",
        ],
    },
    {
        "id": "kitchen",
        "label": "キッチン",
        "keyword": "キッチン用品",
        "color": "#0f766e",
        "photo_query": "kitchen cooking home",
        "info_topics": [
            "まな板・フライパンを長持ちさせる手入れ方法",
            "一人暮らしの自炊を時短にするキッチン収納の工夫",
            "冷蔵庫の野菜室を長持ちさせる保存のコツ",
            "キッチンのニオイ・カビ対策",
            "自炊初心者が最初に揃えるべき調理器具",
        ],
    },
    {
        "id": "lifestyle",
        "label": "生活雑貨",
        "keyword": "便利グッズ",
        "color": "#6d28d9",
        "photo_query": "cozy home lifestyle organization",
        "info_topics": [
            "一人暮らしの洗濯物を生乾きにしない干し方",
            "部屋の湿気・カビ対策の基本",
            "待機電力を減らして電気代を抑える方法",
            "スマホ・ガジェットのバッテリーを長持ちさせる使い方",
            "デスク・書類が片付く仕分けルール",
        ],
    },
]


def load_json(path: Path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_state() -> dict:
    return load_json(STATE_FILE, {})


def save_state(state: dict):
    save_json(STATE_FILE, state)


def load_posted() -> list[dict]:
    return load_json(POSTED_FILE, [])


def save_posted(posted: list[dict]):
    save_json(POSTED_FILE, posted)


def pick_genre(state: dict) -> dict:
    idx = (state.get("last_genre_index", -1) + 1) % len(GENRES)
    state["last_genre_index"] = idx
    return GENRES[idx]


def pick_info_topic(genre: dict, state: dict) -> str:
    topics = genre["info_topics"]
    key = f"last_info_topic_index_{genre['id']}"
    idx = (state.get(key, -1) + 1) % len(topics)
    state[key] = idx
    return topics[idx]


def slugify(genre_id: str, article_type: str) -> str:
    today = date.today().strftime("%Y%m%d")
    existing = load_posted()
    seq = sum(1 for a in existing if a["slug"].startswith(f"{today}-")) + 1
    return f"{today}-{genre_id}-{article_type}-{seq}"


def _titles_for_genre(posted: list[dict], genre_id: str) -> list[str]:
    return [a["title"] for a in posted if a.get("genre_id") == genre_id]


def _used_item_ids(posted: list[dict]) -> set:
    used = set()
    for a in posted:
        used.update(a.get("item_ids", []))
    return used


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _attach_items_to_sections(sections: list[dict], items: list[dict]):
    """各セクションに対応する商品をproduct_index(1始まり、AIが付与)から特定し、
    section["item"] に紐付ける。見出しは商品名そのままではなく自然な文章にできるようにするため、
    見出しの文字列一致ではなくインデックスで対応付ける設計にしている。"""
    for section in sections:
        idx = section.get("product_index")
        item = None
        if isinstance(idx, int) and 1 <= idx <= len(items):
            item = items[idx - 1]
        elif isinstance(idx, str) and idx.isdigit() and 1 <= int(idx) <= len(items):
            item = items[int(idx) - 1]
        else:
            # AIがproduct_indexを付け忘れた場合のフォールバック(空白差異を無視した名前一致)
            heading_norm = _normalize_ws(section.get("heading", ""))
            body_norm = _normalize_ws(section.get("body", ""))
            item = next(
                (i for i in items if _normalize_ws(i["name"]) in heading_norm + body_norm),
                None,
            )
        section["item"] = item


def _add_section_ids(sections: list[dict]):
    """目次(TOC)用に各セクションへ一意なアンカーID(section-1, section-2, ...)を付与する"""
    for i, section in enumerate(sections, 1):
        section["id"] = f"section-{i}"


def build_info_article(genre: dict, posted: list[dict], state: dict) -> dict | None:
    topic = pick_info_topic(genre, state)
    print(f"  情報系記事を作成します(ジャンル: {genre['label']} / テーマ: {topic})")
    avoid = _titles_for_genre(posted, genre["id"])
    raw = ai_writer.generate_info_article(genre["label"], topic, avoid)
    if raw is None:
        print("  [エラー] 記事生成に失敗しました")
        return None

    _add_section_ids(raw["sections"])

    slug = slugify(genre["id"], "info")
    return {
        "slug": slug,
        "title": raw["title"],
        "meta_description": raw["meta_description"],
        "genre_id": genre["id"],
        "genre_label": genre["label"],
        "genre_color": genre.get("color", "#374151"),
        "photo_query": genre.get("photo_query", ""),
        "type": "info",
        "intro": raw["intro"],
        "sections": raw["sections"],
        "conclusion": raw["conclusion"],
        "affiliate_items": [],
        "published_at": datetime.now().isoformat(timespec="seconds"),
        "item_ids": [],
    }


def build_product_article(genre: dict, posted: list[dict], state: dict) -> dict | None:
    print(f"  商品紹介記事を作成します(ジャンル: {genre['label']})")
    try:
        items = rakuten_source.fetch_items(keyword=genre["keyword"])
    except Exception as e:
        print(f"  [エラー] 楽天APIの商品取得に失敗しました: {e}")
        return None

    used = _used_item_ids(posted)
    new_items = [i for i in items if i["id"] not in used][:ITEMS_PER_PRODUCT_ARTICLE]
    if len(new_items) < 2:
        print(f"  {genre['label']}に投稿可能な新規商品が足りません({len(new_items)}件)")
        return None

    # 楽天の商品名は80〜150字の長い販促文になっていることが多く、AIに一字一句そのまま
    # 再現させるのは非現実的(全角スペースの微妙な差異などで容易に不一致になる)。
    # rakuten_threads_bot/main.py と同じく40字に短縮した表示名を「正式名称」として扱う。
    for item in new_items:
        if len(item["name"]) > 40:
            item["name"] = item["name"][:40] + "…"

    topic = f"{genre['label']}のおすすめアイテム比較"
    avoid = _titles_for_genre(posted, genre["id"])
    raw = ai_writer.generate_product_article(genre["label"], topic, new_items, avoid)
    if raw is None:
        print("  [エラー] 記事生成に失敗しました(商品名が正しく含まれない等)")
        return None

    _attach_items_to_sections(raw["sections"], new_items)
    _add_section_ids(raw["sections"])

    slug = slugify(genre["id"], "product")
    return {
        "slug": slug,
        "title": raw["title"],
        "meta_description": raw["meta_description"],
        "genre_id": genre["id"],
        "genre_label": genre["label"],
        "genre_color": genre.get("color", "#374151"),
        "photo_query": genre.get("photo_query", ""),
        "type": "product",
        "intro": raw["intro"],
        "sections": raw["sections"],
        "conclusion": raw["conclusion"],
        "affiliate_items": new_items,
        "published_at": datetime.now().isoformat(timespec="seconds"),
        "item_ids": [i["id"] for i in new_items],
    }


def generate_article() -> dict | None:
    """記事1本を生成する。失敗時はNoneを返す(呼び出し側でログ・リトライを判断)。"""
    state = load_state()
    posted = load_posted()
    genre = pick_genre(state)

    is_info = random.random() < INFO_RATIO
    article = None
    if is_info:
        article = build_info_article(genre, posted, state)
    else:
        article = build_product_article(genre, posted, state)
        if article is None:
            # その場でジャンルを変えて情報系記事にフォールバック(商品が尽きていても記事は出す)
            print("  商品紹介記事が作れなかったため、情報系記事にフォールバックします")
            article = build_info_article(genre, posted, state)

    save_state(state)
    return article
