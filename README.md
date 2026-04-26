# MdLens

軽量な読み取り専用 Markdown リーダーです。
ブラウザ上で左に階層ファイル一覧、右にレンダリング済み Markdown を表示します。

## 使い方

```powershell
uv run mdlens index C:\path\to\markdown-folder
uv run mdlens app C:\path\to\markdown-folder
```

現在のフォルダを対象にする場合:

```powershell
uv run mdlens index
uv run mdlens app
```


## GitHub/GitLab リポジトリ

画面上部の入力欄には、ローカルフォルダパスの代わりに GitHub/GitLab のリポジトリURLも入力できます。

```text
https://github.com/owner/repository
github.com/owner/repository
https://gitlab.com/group/subgroup/repository
```

`Go` を押すと、対象リポジトリをOSの一時フォルダへ shallow clone し、その clone 先をMarkdownの読み取り対象にします。別のフォルダやリポジトリへ切り替えた場合、直前に使っていた一時 clone フォルダは削除されます。

この機能はローカルの `git` コマンドを使用するため、Git for Windows が必要です。

## 構成

```text
src/mdlens/
  cli.py         # CLI、アプリ起動
  config.py      # 設定値、アプリ設定モデル
  db.py          # SQLAlchemy engine、schema、FTS 操作
  indexer.py     # Markdown 走査、index 更新
  markdown.py    # Markdown 読み込み、HTML レンダリング
  models.py      # SQLAlchemy ORM モデル
  repo_clone.py  # GitHub/GitLab clone 用一時作業領域
  repository.py  # 一覧取得、検索
  schemas.py     # Pydantic API モデル
  web.py         # FastAPI app / API
  ui.py          # ブラウザ UI
```

詳しい設計は [docs/architecture.md](docs/architecture.md) を参照してください。

## コマンド

```powershell
uv run mdlens index [folder]
uv run mdlens app [folder]
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

詳しくは [docs/testing.md](docs/testing.md) を参照してください。

## ドキュメント

- [docs/architecture.md](docs/architecture.md): アプリ構成
- [docs/testing.md](docs/testing.md): pytest 実行方法
- [docs/publishing.md](docs/publishing.md): PyPI / TestPyPI publishing guide
