# Architecture

MdLens は、Markdown フォルダを SQLite index に登録し、FastAPI で提供するブラウザ UI から読み取り専用で閲覧するアプリです。

## Goals

- Python 3.12 と uv で動作すること
- Markdown の編集機能は持たず、読み取り専用にすること
- ファイル数が多いフォルダでも、表示時に毎回全ファイルを読み直さないこと
- 処理の責務を一般的な単位に分割すること

## Modules

```text
src/mdlens/
  cli.py         # CLI、アプリ起動
  config.py      # 設定値、AppConfig
  db.py          # SQLAlchemy engine、schema、FTS 操作
  indexer.py     # Markdown 走査、index 更新
  markdown.py    # Markdown 読み込み、HTML レンダリング
  models.py      # SQLAlchemy ORM モデル
  repository.py  # 一覧取得、検索
  schemas.py     # Pydantic API モデル
  repo_clone.py  # GitHub/GitLab clone 用一時作業領域
  web.py         # FastAPI app / API
  ui.py          # ブラウザ UI HTML/CSS/JS
```

## Data Flow

1. `mdlens index [folder]` または画面上の `Sync` で `indexer.refresh_index()` を実行します。
2. `indexer` は対象フォルダ配下の `.md` を走査し、変更があるファイルだけ読み込みます。
3. ファイル情報は `files` テーブルに保存し、検索対象テキストは `file_search` に保存します。
4. UI は `/api/tree` で一覧を取得し、左ペインへ階層表示します。
5. ファイル選択時は `/api/file?id=...` で Markdown を HTML にレンダリングして表示します。
6. 検索時は `/api/search?q=...` で SQLite FTS または plain LIKE 検索を行います。

## Repository URL Flow

1. UI の入力欄に GitHub/GitLab URL を入力して `Go` を押すと、従来の `/api/folder` にURLが送られます。
2. `web.prepare_source_config()` は入力値をローカルパスかリポジトリURLかに振り分けます。
3. リポジトリURLの場合、`repo_clone.parse_repository_source()` が GitHub/GitLab のWeb URLを HTTPS clone URL に正規化します。
4. `repo_clone.clone_repository()` が `git clone --depth 1 --single-branch` でOSの一時フォルダへ clone します。
5. clone 先フォルダに対して通常の index 作成を行い、以降の読み取り・検索はローカルフォルダと同じ処理を使います。
6. 別のフォルダやリポジトリへ切り替えた時、またはアプリ終了時に、直前の一時 clone フォルダを削除します。

## SQLite Index

`files` テーブルには、表示や差分更新に必要なメタデータを保存します。

- `rel_path`
- `name`
- `parent`
- `title`
- `size`
- `mtime_ns`
- `seen_scan`
- `indexed_at`

検索テーブルは環境に応じて選択します。

- `trigram`: 利用できる場合の既定。短い語や日本語検索に比較的向きます。
- `unicode61`: `trigram` が使えない場合の FTS fallback。
- `plain`: FTS5 が使えない環境の最終 fallback。

## FastAPI Endpoints

- `GET /`: ブラウザ UI
- `GET /api/tree`: 現在の index のファイル一覧
- `GET /api/file?id=...`: Markdown ファイルの HTML 表示
- `GET /api/search?q=...`: 文字列検索
- `POST /api/refresh`: 現在フォルダの index 更新
- `POST /api/folder`: 対象フォルダの切り替え
- `GET /asset`: Markdown から参照されたローカル画像などの配信

## UI

UI は `ui.py` の HTML 文字列として保持しています。ビルド工程を増やさないため、フロントエンドの bundler は使っていません。

主な操作は以下です。

- Folder path 入力 + `Go`: 対象フォルダ切り替え
- `Sync`: index 更新
- `Expand` / `Collapse`: ツリーの一括開閉
- 左右ペイン間の splitter: サイドバー幅変更
- `Search`: index 検索

## Safety Notes

- Markdown の raw HTML は `markdown-it-py` 側で無効化しています。
- `/asset` は対象 root 配下のファイルだけ返します。
- アプリは読み取り専用で、Markdown 本体を書き換えません。
