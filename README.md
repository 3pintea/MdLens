# MdReader

軽量な読み取り専用 Markdown リーダーです。

- `uv` と Python 3.12 で実行します。
- `.md` ファイルを SQLite index に登録します。
- SQL 操作は SQLAlchemy、API は FastAPI、入出力データは Pydantic で扱います。
- index がない状態でアプリを起動すると、自動で index を作成します。
- ブラウザ上で左に階層ファイル一覧、右にレンダリング済み Markdown を表示します。
- SQLite FTS を使って文字列検索できます。
- 画面上で対象フォルダを切り替えられます。
- 画面上の `Sync` から index を再作成できます。
- ファイルツリーは `Expand` / `Collapse` でまとめて開閉できます。

## 使い方

```powershell
uv run mdreader index C:\path\to\markdown-folder
uv run mdreader app C:\path\to\markdown-folder
```

現在のフォルダを対象にする場合:

```powershell
uv run mdreader index
uv run mdreader app
```

index ファイルは既定で対象フォルダ直下の `.mdreader_index.sqlite3` に作られます。

## 構成

```text
src/mdreader/
  cli.py         # CLI、アプリ起動
  config.py      # 設定値、アプリ設定モデル
  db.py          # SQLAlchemy engine、schema、FTS 操作
  indexer.py     # Markdown 走査、index 更新
  markdown.py    # Markdown 読み込み、HTML レンダリング
  models.py      # SQLAlchemy ORM モデル
  repository.py  # 一覧取得、検索
  schemas.py     # Pydantic API モデル
  web.py         # FastAPI app / API
  ui.py          # ブラウザ UI
```

詳しい設計は [docs/architecture.md](docs/architecture.md) を参照してください。

## コマンド

```powershell
uv run mdreader index [folder]
uv run mdreader app [folder]
```

主なオプション:

- `--index PATH`: index ファイルの保存先を指定します。
- `--refresh`: アプリ起動時に index を更新します。
- `--host HOST`: 待ち受け host を指定します。既定は `127.0.0.1` です。
- `--port PORT`: 待ち受け port を指定します。既定は `8765` です。
- `--no-browser`: 起動時にブラウザを開きません。

## テスト

```powershell
uv run --python 3.12 --group dev pytest
```

coverage は `pyproject.toml` で `90%` 以上を要求しています。テスト方針は [docs/testing.md](docs/testing.md) にまとめています。

## ドキュメント

- [docs/architecture.md](docs/architecture.md): アプリ構成、index 更新、API、UI の責務
- [docs/testing.md](docs/testing.md): pytest 実行方法、Given/When/Then 方針、coverage 対象
