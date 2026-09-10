#!/usr/bin/env python3
"""
記事のヒーロー画像として使う実写真をPexels API(無料)から取得する。
youtube_jidoで発行済みのPEXELS_API_KEYを共有利用する。

取得できない場合(キー未設定・該当写真なし・通信エラー)はNoneを返し、
呼び出し側(content_pipeline.py)がPillow生成のサムネイルにフォールバックする。
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"


def fetch_photo(query: str, dest_path: Path) -> bool:
    """queryに合う写真を1枚探してdest_pathに保存する。成功したらTrue。"""
    if not PEXELS_API_KEY:
        return False
    try:
        resp = requests.get(
            PEXELS_SEARCH_URL,
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            timeout=15,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return False
        image_url = photos[0]["src"]["large"]
        img_resp = requests.get(image_url, timeout=20)
        img_resp.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(img_resp.content)
        return True
    except Exception:
        return False
