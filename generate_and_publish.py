#!/usr/bin/env python3
"""
記事を1本生成してdocs/フォルダへ反映し、Gitリポジトリが用意できていればGitHubへ公開する。

実行方法:
  python generate_and_publish.py

Gitリポジトリがまだ無い間(Phase 1)は、ローカルのdocs/フォルダを更新するだけで終わる
(docs/index.html をブラウザで開けば確認できる)。
`git init`してGitHubリポジトリのremoteを設定し、SITE_BASE_URLを.envに設定した後(Phase 2以降)は、
このスクリプトがそのままcommit&pushして公開まで行う。
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import content_pipeline
import site_builder
import thumbnail

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "site_log.txt"


def log(message: str):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def git_publish(slug: str):
    """gitリポジトリが初期化済みなら、変更をcommit&pushする"""
    if not (BASE_DIR / ".git").exists():
        log("  (Gitリポジトリが未初期化のため、ローカル生成のみ行いました。公開はスキップします)")
        return
    try:
        subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, check=True, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", f"記事追加: {slug}"],
            cwd=BASE_DIR, capture_output=True, text=True,
        )
        if result.returncode != 0 and "nothing to commit" not in result.stdout:
            log(f"  [警告] git commitに失敗しました: {result.stderr.strip()}")
            return
        push = subprocess.run(["git", "push"], cwd=BASE_DIR, capture_output=True, text=True)
        if push.returncode != 0:
            log(f"  [警告] git pushに失敗しました: {push.stderr.strip()}")
        else:
            log("  GitHubへpushしました")
    except Exception as e:
        log(f"  [警告] git公開処理でエラーが発生しました: {e}")


def main():
    log("記事生成を開始します")
    article = content_pipeline.generate_article()
    if article is None:
        log("記事を生成できませんでした(今回はスキップ)")
        sys.exit(1)

    thumbnail.create_thumbnail(article["title"], article["slug"])
    site_builder.render_article(article)

    posted = content_pipeline.load_posted()
    posted.append({
        "slug": article["slug"],
        "title": article["title"],
        "genre_id": article["genre_id"],
        "genre_label": article["genre_label"],
        "type": article["type"],
        "published_at": article["published_at"],
        "item_ids": article["item_ids"],
    })
    content_pipeline.save_posted(posted)
    site_builder.build_site(posted)

    log(f"公開しました: {article['title']} ({article['slug']})")
    git_publish(article["slug"])


if __name__ == "__main__":
    main()
