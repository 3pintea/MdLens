from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


APP_NAME = "MdReader"
DEFAULT_INDEX_NAME = ".mdreader_index.sqlite3"
MARKDOWN_SUFFIX = ".md"
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".uv-cache",
    ".uv-python",
    "__pycache__",
    "node_modules",
    "venv",
}


class AppConfig(BaseModel):
    """アプリが現在参照している Markdown ライブラリの設定。

    Args:
        root: Markdown ファイルを探索するルートフォルダ。
        index_path: `root` に対応する SQLite index ファイル。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    root: Path
    index_path: Path


def resolve_root(path: str | Path) -> Path:
    """ユーザー入力のフォルダパスを絶対パスへ正規化する。

    Args:
        path: 相対パス、絶対パス、または `~` を含むパス。

    Returns:
        展開済みの絶対パス。
    """

    return Path(path).expanduser().resolve()


def default_index_path(root: Path) -> Path:
    return root / DEFAULT_INDEX_NAME
