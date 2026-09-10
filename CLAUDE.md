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

- **サイトは実際に公開済み**: https://enupi80-droid.github.io/free-content-site/ (GitHubリポジトリ: https://github.com/enupi80-droid/free-content-site 、mainブランチ/docsフォルダをGitHub Pagesで配信)
- Phase 1(記事生成・サイト構築)・Phase 2(GitHub Pagesへの実公開)は実装・検証済み。情報系記事・商品紹介記事とも実データで生成成功を確認。
- GEMINI_API_KEYはこのサイト専用の新規キーに切り替え済み(他3プロジェクトと共有していた旧キーとは別)。ただし**Google検索連携(grounding)はこの無料枠キーでは429エラーになり使えない**ため、`ai_writer.py`のリサーチ工程はWeb検索なし(モデル自身の一般知識のみ、統計値等のでっち上げ禁止を明示)で構成している。
- 楽天商品名が長い(全角スペース混じりなど)ため、商品紹介記事のH2見出しには商品名をそのまま使わせていない。AIには`sections`の各要素に`product_index`(1始まり、何番目の商品データに対応するか)を出力させ、`content_pipeline._attach_items_to_sections`がそれを使って商品カードを紐付ける(`product_index`が無い場合のみ空白差異を無視した名前一致にフォールバック)。見出しは自然な短文、商品の正式名称は商品カード内に表示する。
- モデル名は`gemini-3.6-flash`(このキーで`gemini-2.5-flash`は404になったため)。
- 2026-09-10にデザインを全面刷新(Web検索でリサーチ済み、詳細は`C:\Users\naoya\.claude\skills\free-content-site\SKILL.md`の「デザイン方針」参照)。記事の全内容を`posted_articles.json`に保存するようにしたため、`python site_builder.py`(=`rebuild_all_pages()`)でAI呼び出しなしに全ページへデザイン変更を反映できる。
- ヘッダーにジャンル別ナビゲーション、`docs/categories/<genre_id>.html`のカテゴリー一覧ページ、トップページの注目記事(最新1件の大きなカード)、ファビコン、記事ページのJSON-LD(Article構造化データ)を追加済み。
- Phase 5のうち日次タスク`ContentSite_EveningAutoUpdate`(ログオン時トリガー+20時以降+1日1回ガード、`run_if_evening.py`)は登録済み。
- Phase 3(Search Console/Analytics連携によるアクセス分析→自動修正ループ)は**未着手**。Google Cloudでの OAuthクライアント発行・Search Console/Analyticsプロパティ作成というユーザー側の追加作業が必要。記事の蓄積・インデックス登録には数日〜数週間かかるため、急ぐ理由がない限り後回しでよい。
- Google Search Console/Analyticsの「サイト所有権確認」「アクセス解析タグの設置」自体は、ユーザーがプロパティを作成して確認コード/測定IDを教えてくれれば、Claudeが`templates/base.html`にタグを追加するだけで完了する(OAuth連携なしでも可視化はできる)。

## 自動投稿スケジュール

`ContentSite_EveningAutoUpdate`(日次・ログオン時トリガー、20時以降・当日未実行なら`generate_and_publish.py`を1回実行)を登録済み。`ContentSite_WeeklyReview`(週次のアクセス分析→修正)はPhase 3未着手のため未登録。

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
- **記事は必ずリサーチしてから書く(重要・繰り返し指摘あり)**: 2026-09-10、Gemini無料枠のGoogle検索連携(grounding)が429エラーで使えず、一時的に「検索なし・モデルの一般知識のみ」で記事を書く構成にしたところ、ユーザーから「ちゃんとリサーチしてからね。いつも言ってると思うけど」と明確な修正指示があった。これは他プロジェクトでも繰り返し伝えられている方針。記事生成の仕組みを変更する際は、検索なしを既定にしないこと。この指摘を受けて、記事生成エンジンをGemini APIからClaude Code CLI(ユーザーのClaudeサブスクリプション、`claude setup-token`の長期トークンで無人実行、WebSearchツールで実リサーチ)へ切り替える作業を実施中。

## 技術メモ

- 必須環境変数: `RAKUTEN_APP_ID`, `RAKUTEN_ACCESS_KEY`, `RAKUTEN_AFFILIATE_ID`, `GEMINI_API_KEY`
- 任意環境変数: `SITE_BASE_URL`(公開後のサイトURL。sitemap/canonical生成に使用。未設定の間はsitemapを生成しない)、`SITE_ARTICLE_TYPE_RATIO`(既定0.5、情報系記事になる確率)
- ローカルでの動作確認: `python generate_and_publish.py` を実行後、`python -m http.server --directory docs 8765` 等で`docs/`を配信してブラウザ確認できる
- 記事の質チェックはrakuten_threads_botの`ai_pipeline.py`と同じ「リサーチ→執筆→品質チェック(不合格なら差し戻し、最大2回)」パターンを踏襲
- ジャンル・トピックを増やす場合は`content_pipeline.py`の`GENRES`を編集する
