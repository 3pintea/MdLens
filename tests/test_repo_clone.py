from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from mdlens.repo_clone import (
    RepositoryCloneError,
    RepositorySource,
    UnsupportedRepositoryError,
    cleanup_repository_workspace,
    clone_repository,
    looks_like_repository_url,
    parse_repository_source,
)


def test_parse_repository_source_normalizes_github_and_gitlab_urls() -> None:
    # Given: GitHub と GitLab のWeb URL。
    github_url = "github.com/acme/docs/tree/main"
    gitlab_url = "https://gitlab.com/group/sub/docs/-/blob/main/README.md"

    # When: clone 用リポジトリ情報へ変換する。
    github = parse_repository_source(github_url)
    gitlab = parse_repository_source(gitlab_url)

    # Then: 余分なWeb画面用パスを取り除いた HTTPS clone URL になる。
    assert github.url == "https://github.com/acme/docs.git"
    assert github.slug == "acme/docs"
    assert gitlab.url == "https://gitlab.com/group/sub/docs.git"
    assert gitlab.slug == "group/sub/docs"


def test_repository_url_detection_keeps_windows_paths_as_local_paths() -> None:
    # Given: Windows のローカルパスと未対応ホストのURL。
    windows_path = r"C:\notes"
    unsupported_url = "https://example.com/acme/docs"

    # When / Then: ローカルパスはURL扱いせず、未対応ホストは明示的に拒否する。
    assert not looks_like_repository_url(windows_path)
    assert looks_like_repository_url(unsupported_url)
    with pytest.raises(UnsupportedRepositoryError):
        parse_repository_source(unsupported_url)


def test_clone_repository_creates_shallow_clone_workspace(workspace_tmp: Path) -> None:
    # Given: clone 対象と git clone のモック。
    source = RepositorySource(
        url="https://github.com/acme/docs.git",
        host="github.com",
        slug="acme/docs",
    )
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    # When: 一時フォルダへ clone する。
    with patch("mdlens.repo_clone.subprocess.run", return_value=completed) as run:
        workspace = clone_repository(source, parent=workspace_tmp, timeout_seconds=10)

    # Then: shallow clone コマンドが実行され、作業領域は削除可能な一時フォルダ配下にある。
    command = run.call_args.args[0]
    assert command[:5] == ["git", "clone", "--depth", "1", "--single-branch"]
    assert command[5] == "https://github.com/acme/docs.git"
    assert workspace.root.name == "acme_docs"
    assert workspace.root.parent == workspace.temp_dir
    assert run.call_args.kwargs["timeout"] == 10

    cleanup_repository_workspace(workspace)
    assert not workspace.temp_dir.exists()


def test_clone_repository_cleans_temp_dir_when_git_is_missing(
    workspace_tmp: Path,
) -> None:
    # Given: git コマンドが存在しない環境。
    source = RepositorySource(
        url="https://github.com/acme/docs.git",
        host="github.com",
        slug="acme/docs",
    )

    # When / Then: 例外を返し、途中まで作った一時フォルダを残さない。
    with (
        patch("mdlens.repo_clone.subprocess.run", side_effect=FileNotFoundError),
        pytest.raises(RepositoryCloneError, match="Git command"),
    ):
        clone_repository(source, parent=workspace_tmp)

    assert not list(workspace_tmp.glob("mdlens-repo-*"))
