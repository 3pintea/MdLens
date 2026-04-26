# Testing

MdLens は pytest でテストします。

```powershell
uv run --group dev pytest
```

`pyproject.toml` の pytest 設定で coverage を有効化し、`90%` 以上を満たします。

## Test Layout

```text
tests/
  conftest.py                 # ワークスペース内一時ディレクトリ fixture
  test_cli.py                 # CLI、起動処理
  test_db.py                  # DB helper、plain search backend
  test_indexer_repository.py  # index 更新、検索 repository
  test_markdown.py            # Markdown 復号、タイトル抽出、リンク変換
  test_repo_clone.py          # GitHub/GitLab URL parsing and temporary clone
  test_web.py                 # FastAPI endpoints
```

## Temporary Files

Windows 環境で一時ディレクトリの権限差に当たりにくくするため、`tests/conftest.py` の `workspace_tmp` fixture でワークスペース内に一時フォルダを作ります。

生成される一時フォルダは `.gitignore` で除外しています。

既定 index 保存先を検証するテストでは、実ユーザーデータ領域に書き込まないよう `MDLENS_DATA_DIR` を `workspace_tmp` 配下へ向けます。

## Coverage Scope

coverage は `mdlens` パッケージを対象にしています。ただし、以下は除外しています。

- `src/mdlens/__main__.py`: CLI エントリポイントの薄い委譲
- `src/mdlens/ui.py`: HTML/CSS/JS の大きな定数

UI の HTML については、FastAPI の `/` が必要な要素を返すことを API テストで確認しています。
