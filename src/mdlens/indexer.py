from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .config import MARKDOWN_SUFFIX, SKIP_DIRS
from .db import (
    create_engine_for_index,
    delete_search_content,
    ensure_schema,
    replace_search_content,
    set_meta_value,
)
from .markdown import read_markdown, title_from_markdown
from .models import FileRecord
from .schemas import IndexStats


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iter_markdown_files(root: Path) -> Iterator[tuple[Path, str]]:
    """index 対象の Markdown ファイルを安定した順序で列挙する。

    Args:
        root: 探索を開始するルートフォルダ。

    Yields:
        実ファイルパスと、ルートからの POSIX 形式の相対パス。
    """

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for filename in sorted(filenames):
            if not filename.lower().endswith(MARKDOWN_SUFFIX):
                continue
            path = Path(dirpath) / filename
            yield path, path.relative_to(root).as_posix()


def parent_path(rel_path: str) -> str:
    parent = Path(rel_path).parent.as_posix()
    return "" if parent == "." else parent


def refresh_index(root: Path, index_path: Path, engine: Engine | None = None) -> IndexStats:
    """Markdown フォルダを走査し、SQLite index を最新状態へ更新する。

    Args:
        root: Markdown ファイルを探索するルートフォルダ。
        index_path: 更新する SQLite index ファイル。
        engine: 既存の SQLAlchemy engine。未指定時はこの関数内で作成する。

    Returns:
        走査件数、更新件数、削除件数などを含む更新結果。
    """

    owns_engine = engine is None
    engine = engine or create_engine_for_index(index_path)
    backend = ensure_schema(engine)
    scan_id = time.time_ns()
    stats = {
        "root": str(root),
        "index": str(index_path),
        "seen": 0,
        "updated": 0,
        "unchanged": 0,
        "deleted": 0,
        "errors": [],
    }

    try:
        with Session(engine) as session:
            with session.begin():
                set_meta_value(session, "root", str(root))
                set_meta_value(session, "updated_at", utc_now())

                for path, rel_path in iter_markdown_files(root):
                    stats["seen"] += 1
                    try:
                        file_stat = path.stat()
                    except OSError as exc:
                        stats["errors"].append(f"{rel_path}: {exc}")
                        continue

                    record = session.scalar(
                        select(FileRecord).where(FileRecord.rel_path == rel_path)
                    )
                    if (
                        record
                        and record.size == file_stat.st_size
                        and record.mtime_ns == file_stat.st_mtime_ns
                    ):
                        record.seen_scan = scan_id
                        stats["unchanged"] += 1
                        continue

                    try:
                        text_content = read_markdown(path)
                    except OSError as exc:
                        stats["errors"].append(f"{rel_path}: {exc}")
                        continue

                    title = title_from_markdown(text_content, path.stem)
                    indexed_at = utc_now()
                    if record is None:
                        record = FileRecord(
                            rel_path=rel_path,
                            name=path.name,
                            parent=parent_path(rel_path),
                            title=title,
                            size=file_stat.st_size,
                            mtime_ns=file_stat.st_mtime_ns,
                            seen_scan=scan_id,
                            indexed_at=indexed_at,
                        )
                        session.add(record)
                        session.flush()
                    else:
                        record.name = path.name
                        record.parent = parent_path(rel_path)
                        record.title = title
                        record.size = file_stat.st_size
                        record.mtime_ns = file_stat.st_mtime_ns
                        record.seen_scan = scan_id
                        record.indexed_at = indexed_at

                    # 検索は本文だけでなく、タイトルとパスにもヒットさせる。
                    search_text = f"{title}\n{rel_path}\n{text_content}"
                    replace_search_content(session, backend, record.id, search_text)
                    stats["updated"] += 1

                stale_records = session.scalars(
                    select(FileRecord).where(FileRecord.seen_scan != scan_id)
                ).all()
                for stale in stale_records:
                    delete_search_content(session, backend, stale.id)
                    session.delete(stale)
                    stats["deleted"] += 1

                file_count = session.scalar(select(func.count()).select_from(FileRecord)) or 0
                set_meta_value(session, "file_count", str(file_count))
                set_meta_value(session, "search_backend", backend)

            if backend != "plain":
                try:
                    session.execute(text("INSERT INTO file_search(file_search) VALUES('optimize')"))
                    session.commit()
                except Exception:
                    session.rollback()
    finally:
        if owns_engine:
            engine.dispose()

    return IndexStats(**stats)
