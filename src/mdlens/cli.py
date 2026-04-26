from __future__ import annotations

import argparse
import socket
import webbrowser
from pathlib import Path

import uvicorn

from .config import (
    APP_NAME,
    DATA_DIR_ENV,
    DEFAULT_INDEX_NAME,
    AppConfig,
    default_index_path,
    resolve_root,
)
from .indexer import refresh_index
from .schemas import IndexStats
from .web import create_app


def find_available_port(host: str, port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            sock.bind((host, 0))
        return int(sock.getsockname()[1])


def print_index_stats(stats: IndexStats) -> None:
    print(f"Root: {stats.root}")
    print(f"Index: {stats.index}")
    print(f"Seen: {stats.seen}")
    print(f"Updated: {stats.updated}")
    print(f"Unchanged: {stats.unchanged}")
    print(f"Deleted: {stats.deleted}")
    if stats.errors:
        print("Errors:")
        for error in stats.errors:
            print(f"  - {error}")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="Markdown folder. Defaults to the current folder.",
    )
    parser.add_argument(
        "--index",
        dest="index_path",
        default=None,
        help=(
            f"Index path. Defaults to MdLens user data under {DATA_DIR_ENV}, "
            f"or the platform user data directory, using {DEFAULT_INDEX_NAME}."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdlens", description="Read-only Markdown reader."
    )
    subparsers = parser.add_subparsers(dest="command")

    index_parser = subparsers.add_parser("index", help="Update the Markdown index.")
    add_common_args(index_parser)

    app_parser = subparsers.add_parser("app", help="Start the reader app.")
    add_common_args(app_parser)
    app_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    app_parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    app_parser.add_argument(
        "--refresh", action="store_true", help="Refresh index before starting."
    )
    app_parser.add_argument(
        "--no-browser", action="store_true", help="Do not open a browser."
    )

    return parser


def paths_from_args(args: argparse.Namespace) -> tuple[Path, Path]:
    root = resolve_root(args.folder)
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Folder not found: {root}")
    index_path = (
        Path(args.index_path).expanduser().resolve()
        if args.index_path
        else default_index_path(root)
    )
    return root, index_path


def run_app(config: AppConfig, host: str, port: int, open_browser: bool) -> None:
    port = find_available_port(host, port)
    url = f"http://{host}:{port}/"
    app = create_app(config)
    print(f"{APP_NAME} running at {url}")
    print(f"Root: {config.root}")
    print(f"Index: {config.index_path}")
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "app"
        args.folder = "."
        args.index_path = None
        args.host = "127.0.0.1"
        args.port = 8765
        args.refresh = False
        args.no_browser = False

    root, index_path = paths_from_args(args)

    if args.command == "index":
        print_index_stats(refresh_index(root, index_path))
        return 0

    if args.command == "app":
        if args.refresh or not index_path.exists():
            print("Index is missing or refresh was requested. Updating index...")
            print_index_stats(refresh_index(root, index_path))
        run_app(
            AppConfig(root=root, index_path=index_path),
            args.host,
            args.port,
            not args.no_browser,
        )
        return 0

    parser.print_help()
    return 1
