# Testing

MdLens は pytest でテストします。

```powershell
uv run --python 3.12 --group dev pytest
```

`pyproject.toml` の pytest 設定で coverage を有効化し、`90%` 以上を要求しています。

## Test Layout

```text
tests/
  conftest.py                 # ワークスペース内一時ディレクトリ fixture
  test_cli.py                 # CLI、起動処理
  test_db.py                  # DB helper、plain search backend
  test_indexer_repository.py  # index 更新、検索 repository
  test_markdown.py            # Markdown 復号、タイトル抽出、asset URL
  test_repo_clone.py          # GitHub/GitLab URL parsing and temporary clone
  test_web.py                 # FastAPI endpoints
```

## Given / When / Then

各テストはコメントで以下を分かるようにしています。

- Given: 前提データやモックを準備する
- When: 対象処理を実行する
- Then: 期待結果を検証する

## Temporary Files

この環境では pytest 標準の `workspace_tmp` が Windows の一時ディレクトリ権限に当たることがあるため、`tests/conftest.py` の `workspace_tmp` fixture でワークスペース内に一時フォルダを作ります。

生成される一時フォルダは `.gitignore` で除外しています。

## Coverage Scope

coverage は `mdlens` パッケージを対象にしています。ただし、以下は除外しています。

- `src/mdlens/__main__.py`: CLI エントリポイントの薄い委譲
- `src/mdlens/ui.py`: HTML/CSS/JS の大きな定数

UI の HTML については、FastAPI の `/` が必要な要素を返すことを API テストで確認しています。
