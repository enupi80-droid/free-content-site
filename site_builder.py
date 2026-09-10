#!/usr/bin/env python3
"""
記事データ(dict)からJinja2テンプレートを使って静的HTMLを生成する。
GitHub Pagesなど静的ホスティングにそのまま置ける docs/ フォルダを作る(GitHub Pagesの「mainブランチ/docsフォルダ」設定にそのまま対応)。
"""

import os
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

BASE_DIR = Path(__file__).parent
SITE_DIR = BASE_DIR / "docs"
ARTICLES_DIR = SITE_DIR / "articles"
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "").rstrip("/")

_env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")), autoescape=True)


def _canonical(path: str) -> str:
    return f"{SITE_BASE_URL}/{path}" if SITE_BASE_URL else ""


def render_article(article: dict):
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    html = _env.get_template("article.html").render(
        article=article,
        title=article["title"],
        description=article["meta_description"],
        canonical_url=_canonical(f"articles/{article['slug']}.html"),
        og_image=_canonical(f"images/{article['slug']}.png"),
        root="../",
        year=date.today().year,
    )
    (ARTICLES_DIR / f"{article['slug']}.html").write_text(html, encoding="utf-8")


def render_index(posted: list[dict], max_items: int = 30):
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    recent = sorted(posted, key=lambda a: a["published_at"], reverse=True)[:max_items]
    html = _env.get_template("index.html").render(
        articles=recent,
        title="サイト名(仮) | 暮らしを少し良くする情報サイト",
        description="暮らしに役立つ情報と、実際のレビューを踏まえたアイテム紹介をお届けします。",
        canonical_url=_canonical("index.html"),
        og_image="",
        root="",
        year=date.today().year,
    )
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")


def write_sitemap(posted: list[dict]):
    if not SITE_BASE_URL:
        return  # 公開URLが未設定の間はサイトマップを作らない(間違った絶対URLを埋め込まないため)
    urls = [f"{SITE_BASE_URL}/index.html"]
    urls += [f"{SITE_BASE_URL}/articles/{a['slug']}.html" for a in posted]
    body = "\n".join(f"  <url><loc>{escape(u)}</loc></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'
    (SITE_DIR / "sitemap.xml").write_text(xml, encoding="utf-8")


def write_robots():
    lines = ["User-agent: *", "Allow: /"]
    if SITE_BASE_URL:
        lines.append(f"Sitemap: {SITE_BASE_URL}/sitemap.xml")
    (SITE_DIR / "robots.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_site(posted: list[dict]):
    """全記事分のindex/sitemap/robotsを再生成する(新しい記事を1本作った後などに呼ぶ)"""
    render_index(posted)
    write_sitemap(posted)
    write_robots()
