#!/usr/bin/env python3
"""
楽天市場商品検索APIから商品データを取得する薄いラッパー。
rakuten_threads_bot/main.py の fetch_rakuten_items と同じロジック(アフィリエイトリンク付き)。
"""

import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

RAKUTEN_APP_ID = os.environ.get("RAKUTEN_APP_ID")
RAKUTEN_ACCESS_KEY = os.environ.get("RAKUTEN_ACCESS_KEY")
RAKUTEN_AFFILIATE_ID = os.environ.get("RAKUTEN_AFFILIATE_ID")
RAKUTEN_SEARCH_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
HITS = int(os.environ.get("RAKUTEN_HITS", "30"))


def fetch_items(keyword: str = "", genre_id: str = "") -> list[dict]:
    """楽天市場商品検索APIから商品リストを取得(レビュー数が多い順、アフィリエイトリンク付き)"""
    if not (RAKUTEN_APP_ID and RAKUTEN_ACCESS_KEY and RAKUTEN_AFFILIATE_ID):
        raise RuntimeError("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY / RAKUTEN_AFFILIATE_ID が設定されていません")

    params = {
        "applicationId": RAKUTEN_APP_ID,
        "accessKey": RAKUTEN_ACCESS_KEY,
        "affiliateId": RAKUTEN_AFFILIATE_ID,
        "format": "json",
        "hits": HITS,
        "sort": "-reviewCount",
    }
    if keyword:
        params["keyword"] = keyword
    if genre_id:
        params["genreId"] = genre_id

    resp = requests.get(RAKUTEN_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    items = []
    for entry in data.get("Items", []):
        item = entry["Item"]
        image = None
        if item.get("mediumImageUrls"):
            image = re.sub(r"_ex=\d+x\d+", "_ex=800x800", item["mediumImageUrls"][0]["imageUrl"])
        items.append({
            "id": str(item["itemCode"]),
            "name": item["itemName"],
            "price": item["itemPrice"],
            "url": item["affiliateUrl"] or item["itemUrl"],
            "image": image,
            "shop": item.get("shopName", ""),
            "review_count": item.get("reviewCount", 0),
            "review_average": item.get("reviewAverage", 0.0),
            "description": item.get("itemCaption", ""),
        })
    return items
