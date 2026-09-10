# CLAUDE.md

このファイルはClaude Codeがこのリポジトリで作業する際のガイドです。

## プロジェクト概要

**完全無料・完全自動**で運営する、複数ジャンルの収益サイト(GitHub Pagesでホスティング)。
「リサーチ→執筆→公開→アクセス分析→修正」のルーティンを人手を介さず回すことを目的とした個人プロジェクト。
`rakuten_threads_bot` / `youtube_jido` / `note_auto_bot` と同じ運用者が管理しており、それらのAI生成・スケジューリングの仕組みを流用している。

- **商品紹介・比較記事**: 楽天市場APIの実データ(価格・レビュー・商品説明)だけを根拠にAIが執筆。記事内に楽天アフィリエイトリンクを挿入し、必ず「PR」表記を付ける。
- **情報系記事**: 商品を紹介しない、検索流入・広告収益(将来のGoogleアドセンス)向けのお役立ち記事。
- 1回の実行(`generate_and_publish.py`)で記事を1本だけ生成・公開する。ジャンルは`content_pipeline.py`の`GENRES`でローテーション。

## 主要ファイル

- `content_pipeline.py`: ジャンルローテーション・記事タイプ選択(商品紹介 or 情報系)・楽天データ取得・AI呼び出しの統括
- `ai_writer.py`: Gemini API(無料枠)呼び出し。リサーチ→執筆→品質チェックのパイプライン
- `rakuten_source.py`: 楽天市場商品検索APIのラッパー(rakuten_threads_botと同じロジック)
- `thumbnail.py`: Pillowでサムネイル/OG画像をローカル生成(APIコストなし)
- `site_builder.py`: Jinja2で`docs/`配下に静的HTML(記事ページ・一覧・sitemap.xml・robots.txt)を生成(GitHub Pagesの「mainブランチ/docsフォルダ」設定にそのまま対応)
- `templates/`: `base.html` / `article.html` / `index.html`(Jinja2テンプレート)
- `generate_and_publish.py`: 上記を1回の実行でまとめて行うエントリーポイント。Gitリポジトリが初期化済みならcommit&pushまで行う
- `posted_articles.json`: 投稿済み記事の履歴(重複防止・使用済み商品ID管理)
- `bot_state.json`: ジャンル/トピックローテーションの現在位置
- `site_log.txt`: 実行ログ
- `docs/`: 生成された静的サイト本体(GitHub Pagesに公開する対象)
- `.env`: APIキー類(絶対にコミットしない)

## 現在のステータス(2026-09-10時点)

- Phase 1(ローカルでの文章生成・サイト構築の土台)は実装済み。ダミーデータでのサイト生成・表示確認は完了。
- 実データでのフルパイプライン(Gemini呼び出し)は、rakuten_threads_bot・youtube_jidoと共有しているGEMINI_API_KEYの**無料枠日次上限(1モデルにつき20リクエスト/日)に達したため未検証**。専用キーの発行 or 翌日の枠リセットを待って検証する。
- Phase 0(GitHubアカウント連携・Google Search Console/Analytics連携)は未着手。ユーザー側の作業が必要。
- Phase 2(GitHub Pagesへの実公開)・Phase 3(アクセス分析→自動修正ループ)は未実装。

## 自動投稿スケジュール

未設定(Phase 0完了後に`ContentSite_EveningAutoUpdate`(日次)・`ContentSite_WeeklyReview`(週次)をタスクスケジューラへ登録予定)。

## ユーザーについて

- **非エンジニア**。コードは自分でほぼ書けないため、実装・修正・運用のほとんどをClaude Codeに任せたい。
- 説明は専門用語を避け、平易な言葉で。「何が起きて」「次に何をすればいいか」を明確に伝える。

## 作業時の判断方針

2026-09-10にユーザーから「全部実装・スキル化・ルーティン化までやって」と明示的に全権委任を受けている。日々の運用判断(ジャンル選定・トピック選定・記事本数など)は都度確認せず実行してよい。

ただし以下は安全ルール上Claudeが代行できないため、都度ユーザーにお願いする:
- GitHubアカウントの新規作成・ログイン(`gh auth login`はブラウザ認可のみなら代行可)
- Googleアカウントでの新規サービス登録・フォーム送信(Search Console/Analyticsのプロパティ作成、Googleアドセンスへの申請)
- 上記に伴うパスワード入力

- `.env`の中身(APIキー・アクセストークン)を出力・ログ表示・コミットしない。
- 商品紹介記事は景品表示法のステマ規制対応として、必ず「PR」表記を含める(削除しない)。
- GEMINI_API_KEYは他3プロジェクトと共有のため、無料枠のレート制限に当たりやすい。発生時は`ai_writer.py`の自動リトライに任せるか、専用キーの発行を検討する。

## 技術メモ

- 必須環境変数: `RAKUTEN_APP_ID`, `RAKUTEN_ACCESS_KEY`, `RAKUTEN_AFFILIATE_ID`, `GEMINI_API_KEY`
- 任意環境変数: `SITE_BASE_URL`(公開後のサイトURL。sitemap/canonical生成に使用。未設定の間はsitemapを生成しない)、`SITE_ARTICLE_TYPE_RATIO`(既定0.5、情報系記事になる確率)
- ローカルでの動作確認: `python generate_and_publish.py` を実行後、`python -m http.server --directory docs 8765` 等で`docs/`を配信してブラウザ確認できる
- 記事の質チェックはrakuten_threads_botの`ai_pipeline.py`と同じ「リサーチ→執筆→品質チェック(不合格なら差し戻し、最大2回)」パターンを踏襲
- ジャンル・トピックを増やす場合は`content_pipeline.py`の`GENRES`を編集する
