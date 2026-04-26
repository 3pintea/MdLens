from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, ConfigDict, Field

SUPPORTED_REPO_HOSTS = {
    "github.com": "github.com",
    "www.github.com": "github.com",
    "gitlab.com": "gitlab.com",
    "www.gitlab.com": "gitlab.com",
}
CLONE_TIMEOUT_SECONDS = 300


class UnsupportedRepositoryError(ValueError):
    """対応外のリポジトリURLを受け取ったときの例外。"""


class RepositoryCloneError(RuntimeError):
    """git clone に失敗したときの例外。"""


class RepositorySource(BaseModel):
    """clone 対象のリポジトリ情報。

    Args:
        url: git clone に渡す正規化済み URL。
        host: 対応済みのホスト名。
        slug: 画面や一時フォルダ名に使う `owner/repo` 形式の名前。
    """

    url: str = Field(min_length=1)
    host: str = Field(min_length=1)
    slug: str = Field(min_length=1)


class RepositoryWorkspace(BaseModel):
    """一時フォルダ上に clone されたリポジトリの作業領域。

    Args:
        source_url: clone 元の URL。
        display_name: 利用者向けに表示できるリポジトリ名。
        root: Markdown 探索対象として扱う clone 先フォルダ。
        temp_dir: cleanup 時に削除する一時フォルダ。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_url: str
    display_name: str
    root: Path
    temp_dir: Path


def normalize_repository_input(value: str) -> str:
    """省略形の GitHub/GitLab URL を HTTPS URL に正規化する。"""

    candidate = value.strip()
    lower = candidate.lower()
    for host in SUPPORTED_REPO_HOSTS:
        if lower.startswith(f"{host}/"):
            return f"https://{candidate}"
    return candidate


def looks_like_repository_url(value: str) -> bool:
    """入力値がリポジトリURLとして処理されるべきか判定する。"""

    parsed = urlparse(normalize_repository_input(value))
    return parsed.scheme in {"http", "https"}


def parse_repository_source(value: str) -> RepositorySource:
    """GitHub/GitLab のWeb URLからclone可能なURLを作る。

    Args:
        value: 画面から入力された URL。`github.com/owner/repo` の省略形も許可する。

    Returns:
        正規化済みのリポジトリ情報。

    Raises:
        UnsupportedRepositoryError: HTTPSではない、またはGitHub/GitLab以外の場合。
    """

    candidate = normalize_repository_input(value)
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise UnsupportedRepositoryError("Repository URL must use http or https.")

    host = SUPPORTED_REPO_HOSTS.get((parsed.hostname or "").lower())
    if host is None:
        raise UnsupportedRepositoryError(
            "Only GitHub and GitLab repository URLs are supported."
        )

    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    repo_parts = _repository_path_parts(host, path_parts)
    if len(repo_parts) < 2:
        raise UnsupportedRepositoryError(
            "Repository URL must include owner/group and repository name."
        )

    repo_parts[-1] = repo_parts[-1].removesuffix(".git")
    if not all(_is_safe_path_part(part) for part in repo_parts):
        raise UnsupportedRepositoryError(
            "Repository URL contains an unsupported path segment."
        )

    clone_path = "/" + "/".join(repo_parts) + ".git"
    clone_url = urlunparse(("https", host, clone_path, "", "", ""))
    return RepositorySource(url=clone_url, host=host, slug="/".join(repo_parts))


def clone_repository(
    source: RepositorySource,
    *,
    parent: Path | None = None,
    timeout_seconds: int = CLONE_TIMEOUT_SECONDS,
) -> RepositoryWorkspace:
    """リポジトリを一時フォルダに shallow clone する。

    Args:
        source: clone 対象のリポジトリ情報。
        parent: テストなどで一時フォルダの親を固定したい場合の親フォルダ。
        timeout_seconds: `git clone` の最大待機秒数。

    Returns:
        clone 後の作業領域。

    Raises:
        RepositoryCloneError: git コマンドがない、タイムアウト、clone 失敗のいずれか。
    """

    try:
        temp_dir = _make_temp_dir(parent)
    except OSError as exc:
        raise RepositoryCloneError(
            "Could not create a temporary repository directory."
        ) from exc
    checkout_root = temp_dir / _checkout_dir_name(source)
    command = [
        "git",
        "clone",
        "--depth",
        "1",
        "--single-branch",
        source.url,
        str(checkout_root),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        _remove_temp_dir(temp_dir)
        raise RepositoryCloneError(
            "Git command was not found. Install Git for Windows and try again."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        _remove_temp_dir(temp_dir)
        raise RepositoryCloneError("Repository clone timed out.") from exc
    except subprocess.CalledProcessError as exc:
        _remove_temp_dir(temp_dir)
        detail = (exc.stderr or exc.stdout or "git clone failed.").strip()
        raise RepositoryCloneError(detail[-1000:]) from exc

    return RepositoryWorkspace(
        source_url=source.url,
        display_name=source.slug,
        root=checkout_root.resolve(),
        temp_dir=temp_dir.resolve(),
    )


def cleanup_repository_workspace(workspace: RepositoryWorkspace | None) -> None:
    """利用しなくなった clone 用一時フォルダを削除する。"""

    if workspace is not None:
        _remove_temp_dir(workspace.temp_dir)


def _repository_path_parts(host: str, path_parts: list[str]) -> list[str]:
    if host == "github.com":
        return path_parts[:2]
    if "-" in path_parts:
        return path_parts[: path_parts.index("-")]
    return path_parts


def _is_safe_path_part(part: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", part))


def _checkout_dir_name(source: RepositorySource) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", source.slug).strip("._") or "repository"


def _make_temp_dir(parent: Path | None) -> Path:
    base_dir = parent if parent is not None else Path(tempfile.gettempdir())
    base_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(100):
        path = base_dir / f"mdlens-repo-{uuid.uuid4().hex[:12]}"
        try:
            path.mkdir()
        except FileExistsError:
            continue
        return path
    raise FileExistsError("Could not allocate a unique temporary repository directory.")


def _remove_temp_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
