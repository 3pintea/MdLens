from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mdlens import cli
from mdlens.config import AppConfig, default_index_path
from mdlens.schemas import IndexStats


def test_paths_from_args_resolves_folder_and_default_index(
    workspace_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: 存在する対象フォルダを指す CLI 引数。
    data_dir = workspace_tmp.parent / f"{workspace_tmp.name}-data"
    monkeypatch.setenv("MDLENS_DATA_DIR", str(data_dir))
    args = argparse.Namespace(folder=str(workspace_tmp), index_path=None)

    # When: CLI 用パス解決を行う。
    root, index_path = cli.paths_from_args(args)

    # Then: root と既定 index パスが絶対パスになり、対象フォルダ外に置かれる。
    assert root == workspace_tmp.resolve()
    assert index_path == default_index_path(root)
    assert index_path.name == ".mdlens_index.sqlite3"
    assert index_path.is_relative_to(data_dir.resolve())
    assert not index_path.is_relative_to(root)


def test_paths_from_args_rejects_missing_folder(workspace_tmp: Path) -> None:
    # Given: 存在しないフォルダを指す CLI 引数。
    args = argparse.Namespace(folder=str(workspace_tmp / "missing"), index_path=None)

    # When / Then: SystemExit で失敗する。
    with pytest.raises(SystemExit):
        cli.paths_from_args(args)


def test_find_available_port_falls_back_when_port_is_in_use() -> None:
    # Given: すでに利用中のローカルポート。
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        used_port = sock.getsockname()[1]

        # When: 同じポートで起動先を探す。
        available_port = cli.find_available_port("127.0.0.1", used_port)

    # Then: 別の利用可能ポートにフォールバックする。
    assert available_port != used_port
    assert isinstance(available_port, int)


def test_main_index_calls_refresh_index(
    workspace_tmp: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: index コマンドと refresh_index のモック。
    stats = IndexStats(
        root=str(workspace_tmp),
        index=str(workspace_tmp / ".mdlens_index.sqlite3"),
        seen=2,
    )

    # When: CLI の index コマンドを実行する。
    with patch.object(cli, "refresh_index", return_value=stats) as refresh_index:
        exit_code = cli.main(["index", str(workspace_tmp)])

    # Then: index 更新処理が呼ばれ、結果が標準出力される。
    assert exit_code == 0
    refresh_index.assert_called_once()
    assert "Seen: 2" in capsys.readouterr().out


def test_print_index_stats_outputs_errors(capsys: pytest.CaptureFixture[str]) -> None:
    # Given: エラーを含む index 更新結果。
    stats = IndexStats(root="root", index="index.sqlite3", errors=["broken.md"])

    # When: CLI 表示を行う。
    cli.print_index_stats(stats)

    # Then: Errors セクションが出力される。
    output = capsys.readouterr().out
    assert "Errors:" in output
    assert "broken.md" in output


def test_main_app_refreshes_missing_index_and_runs_app(workspace_tmp: Path) -> None:
    # Given: index が存在しないフォルダと、外部起動処理のモック。
    stats = IndexStats(
        root=str(workspace_tmp),
        index=str(workspace_tmp / ".mdlens_index.sqlite3"),
    )

    # When: app コマンドを実行する。
    with (
        patch.object(cli, "refresh_index", return_value=stats) as refresh_index,
        patch.object(cli, "run_app") as run_app,
    ):
        exit_code = cli.main(["app", str(workspace_tmp), "--no-browser"])

    # Then: 初回起動として index 更新後にアプリ起動へ進む。
    assert exit_code == 0
    refresh_index.assert_called_once()
    run_app.assert_called_once()
    config = run_app.call_args.args[0]
    assert isinstance(config, AppConfig)
    assert config.root == workspace_tmp.resolve()


def test_main_defaults_to_app_command(workspace_tmp: Path) -> None:
    # Given: コマンド未指定時の既定起動に必要な外部依存をモックする。
    with (
        patch.object(
            cli,
            "paths_from_args",
            return_value=(workspace_tmp, workspace_tmp / "index.sqlite3"),
        ),
        patch.object(
            cli,
            "refresh_index",
            return_value=IndexStats(root=str(workspace_tmp), index="index"),
        ),
        patch.object(cli, "run_app") as run_app,
    ):
        # When: 引数なしで main を呼ぶ。
        exit_code = cli.main([])

    # Then: app コマンドとして扱われる。
    assert exit_code == 0
    run_app.assert_called_once()


def test_run_app_creates_app_and_invokes_uvicorn() -> None:
    # Given: run_app の外部依存をすべてモックする。
    config = AppConfig(root=Path.cwd(), index_path=Path.cwd() / "index.sqlite3")
    fake_app = MagicMock()

    # When: アプリ起動関数を呼び出す。
    with (
        patch.object(cli, "find_available_port", return_value=9876),
        patch.object(cli, "create_app", return_value=fake_app) as create_app,
        patch.object(cli.uvicorn, "run") as uvicorn_run,
        patch.object(cli.webbrowser, "open") as browser_open,
    ):
        cli.run_app(config, "127.0.0.1", 8765, open_browser=True)

    # Then: FastAPI app が作成され、ブラウザと uvicorn が起動される。
    create_app.assert_called_once_with(config)
    browser_open.assert_called_once_with("http://127.0.0.1:9876/")
    uvicorn_run.assert_called_once_with(
        fake_app, host="127.0.0.1", port=9876, log_level="warning"
    )
