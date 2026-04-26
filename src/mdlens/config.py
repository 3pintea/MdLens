from __future__ import annotations

import hashlib
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

APP_NAME = "MdLens"
DATA_DIR_ENV = "MDLENS_DATA_DIR"
DEFAULT_INDEX_NAME = ".mdlens_index.sqlite3"
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


def user_data_dir() -> Path:
    """MdLens の index などを置くユーザーデータディレクトリを返す。"""

    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or str(Path.home() / "AppData" / "Local")
        )
        return Path(base).expanduser().resolve() / APP_NAME

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser().resolve() / APP_NAME

    return Path.home().expanduser().resolve() / ".local" / "share" / APP_NAME


def safe_index_dir_name(root: Path) -> str:
    normalized_root = os.path.normcase(str(root))
    digest = hashlib.sha256(normalized_root.encode("utf-8")).hexdigest()[:16]
    label = "".join(
        char if char.isalnum() or char in "._-" else "_"
        for char in (root.name or "root")
    ).strip("._")
    return f"{label or 'root'}-{digest}"


def default_index_path(root: Path) -> Path:
    root = root.expanduser().resolve()
    return user_data_dir() / "indexes" / safe_index_dir_name(root) / DEFAULT_INDEX_NAME
