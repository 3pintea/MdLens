from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from mdlens.config import AppConfig
from mdlens.indexer import refresh_index
from mdlens.repo_clone import RepositoryWorkspace
from mdlens.web import create_app


def make_library(root: Path, title: str = "Home") -> None:
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "image.png").write_bytes(b"png")
    (root / "docs" / "home.md").write_text(
        f"# {title}\n\nSearchable body.\n\n![pic](image.png)",
        encoding="utf-8",
    )


def test_fastapi_routes_return_tree_file_search_asset_and_refresh(
    workspace_tmp: Path,
) -> None:
    # Given: index 済みの Markdown ライブラリと FastAPI TestClient。
    root = workspace_tmp / "library"
    root.mkdir()
    make_library(root)
    index_path = root / ".mdlens_index.sqlite3"
    refresh_index(root, index_path)
    app = create_app(AppConfig(root=root, index_path=index_path))

    with TestClient(app) as client:
        # When: 画面、ツリー、ファイル、検索、asset、refresh API を呼び出す。
        html = client.get("/")
        tree = client.get("/api/tree")
        file_id = tree.json()["files"][0]["id"]
        file_response = client.get(f"/api/file?id={file_id}")
        search_response = client.get("/api/search?q=Searchable")
        asset_response = client.get(f"/asset?file={file_id}&path=image.png")
        refresh_response = client.post("/api/refresh")

        # Then: UI HTML と各 API が期待するデータを返す。
        assert html.status_code == 200
        assert "MdLens" in html.text
        assert tree.status_code == 200
        assert tree.json()["file_count"] == 1
        assert file_response.status_code == 200
        assert "Home" in file_response.json()["html"]
        assert search_response.json()["results"][0]["rel_path"] == "docs/home.md"
        assert asset_response.status_code == 200
        assert asset_response.content == b"png"
        assert refresh_response.json()["seen"] == 1


def test_fastapi_folder_switches_library_and_rejects_invalid_path(
    workspace_tmp: Path,
) -> None:
    # Given: 起動時ライブラリと、画面から切り替える別ライブラリ。
    root = workspace_tmp / "library"
    other = workspace_tmp / "other"
    root.mkdir()
    other.mkdir()
    make_library(root, "First")
    make_library(other, "Second")
    index_path = root / ".mdlens_index.sqlite3"
    refresh_index(root, index_path)
    app = create_app(AppConfig(root=root, index_path=index_path))

    with TestClient(app) as client:
        # When: 別フォルダへ切り替える。
        switched = client.post("/api/folder", json={"folder": str(other)})
        switched_file_id = switched.json()["files"][0]["id"]
        switched_file = client.get(f"/api/file?id={switched_file_id}")
        invalid = client.post(
            "/api/folder", json={"folder": str(workspace_tmp / "missing")}
        )

        # Then: 新しい index が自動作成され、以後の API は切替先を参照する。
        assert switched.status_code == 200
        assert switched.json()["root"] == str(other.resolve())
        assert (other / ".mdlens_index.sqlite3").exists()
        assert "Second" in switched_file.json()["html"]
        assert invalid.status_code == 400


def test_fastapi_folder_switch_clones_repository_url_and_cleans_previous_clone(
    workspace_tmp: Path,
) -> None:
    # Given: 起動時ライブラリ、clone 済みとして扱うリポジトリ、一時 clone 後に戻るローカルフォルダ。
    root = workspace_tmp / "library"
    repo_temp = workspace_tmp / "repo-temp"
    repo_root = repo_temp / "acme_docs"
    local = workspace_tmp / "local"
    root.mkdir()
    repo_root.mkdir(parents=True)
    local.mkdir()
    make_library(root, "First")
    make_library(repo_root, "Repository")
    make_library(local, "Local")
    index_path = root / ".mdlens_index.sqlite3"
    refresh_index(root, index_path)
    app = create_app(AppConfig(root=root, index_path=index_path))
    workspace = RepositoryWorkspace(
        source_url="https://github.com/acme/docs.git",
        display_name="acme/docs",
        root=repo_root,
        temp_dir=repo_temp,
    )

    with TestClient(app) as client:
        # When: GitHub URLへ切り替え、その後ローカルフォルダへ戻す。
        with patch(
            "mdlens.web.clone_repository", return_value=workspace
        ) as clone_repository:
            switched = client.post(
                "/api/folder", json={"folder": "https://github.com/acme/docs"}
            )
        switched_file_id = switched.json()["files"][0]["id"]
        switched_file = client.get(f"/api/file?id={switched_file_id}")
        back_to_local = client.post("/api/folder", json={"folder": str(local)})

        # Then: clone 先が表示対象になり、戻した時点で前の一時フォルダは削除される。
        assert switched.status_code == 200
        assert switched.json()["root"] == str(repo_root.resolve())
        assert "Repository" in switched_file.json()["html"]
        assert back_to_local.status_code == 200
        assert back_to_local.json()["root"] == str(local.resolve())
        assert not repo_temp.exists()
        clone_repository.assert_called_once()
        assert (
            clone_repository.call_args.args[0].url == "https://github.com/acme/docs.git"
        )


def test_fastapi_folder_rejects_unsupported_repository_url(workspace_tmp: Path) -> None:
    # Given: 起動済みアプリ。
    root = workspace_tmp / "library"
    root.mkdir()
    make_library(root)
    index_path = root / ".mdlens_index.sqlite3"
    refresh_index(root, index_path)
    app = create_app(AppConfig(root=root, index_path=index_path))

    with TestClient(app) as client:
        # When: GitHub/GitLab以外のURLを指定する。
        response = client.post(
            "/api/folder", json={"folder": "https://example.com/acme/docs"}
        )

        # Then: 未対応URLとして拒否される。
        assert response.status_code == 400
        assert "GitHub and GitLab" in response.json()["detail"]


def test_fastapi_returns_404_for_missing_file_and_asset(workspace_tmp: Path) -> None:
    # Given: asset が存在しない Markdown ライブラリ。
    root = workspace_tmp / "library"
    root.mkdir()
    (root / "note.md").write_text("# Note\n\n![missing](missing.png)", encoding="utf-8")
    index_path = root / ".mdlens_index.sqlite3"
    refresh_index(root, index_path)
    app = create_app(AppConfig(root=root, index_path=index_path))

    with TestClient(app) as client:
        # When: 存在しない file id と asset をリクエストする。
        file_response = client.get("/api/file?id=999")
        file_id = client.get("/api/tree").json()["files"][0]["id"]
        asset_response = client.get(f"/asset?file={file_id}&path=missing.png")

        # Then: 読み取り不能な対象は 404 になる。
        assert file_response.status_code == 404
        assert asset_response.status_code == 404
