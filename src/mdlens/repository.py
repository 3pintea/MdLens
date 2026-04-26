from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .db import get_meta_value
from .models import FileRecord
from .schemas import FileItem


def file_item_from_record(record: FileRecord) -> FileItem:
    return FileItem.model_validate(record)


def list_files(session: Session) -> list[FileItem]:
    records = session.scalars(select(FileRecord).order_by(FileRecord.rel_path.collate("NOCASE"))).all()
    return [file_item_from_record(record) for record in records]


def count_files(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(FileRecord)) or 0)


def get_file_record(session: Session, file_id: int) -> FileRecord | None:
    return session.get(FileRecord, file_id)


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def quote_fts(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def search_files(session: Session, query: str, limit: int = 120) -> list[FileItem]:
    """index から Markdown ファイルを検索する。

    Args:
        session: index DB に接続した SQLAlchemy session。
        query: 検索文字列。
        limit: 最大取得件数。

    Returns:
        検索に一致したファイル情報のリスト。
    """

    query = query.strip()
    if not query:
        return []

    backend = get_meta_value(session, "search_backend", "plain")
    like = f"%{escape_like(query)}%"
    like_params = {"like": like, "limit": limit}

    if backend == "plain":
        rows = session.execute(
            text(
                """
                SELECT f.id, f.rel_path, f.name, f.parent, f.title, f.size, f.mtime_ns
                FROM file_search s
                JOIN files f ON f.id = s.file_id
                WHERE s.content LIKE :like ESCAPE '\\'
                   OR f.title LIKE :like ESCAPE '\\'
                   OR f.rel_path LIKE :like ESCAPE '\\'
                ORDER BY f.rel_path COLLATE NOCASE
                LIMIT :limit
                """
            ),
            like_params,
        ).mappings()
        return [FileItem.model_validate(dict(row)) for row in rows]

    if backend == "trigram" and len(query) < 3:
        rows = session.execute(
            text(
                """
                SELECT f.id, f.rel_path, f.name, f.parent, f.title, f.size, f.mtime_ns
                FROM file_search
                JOIN files f ON f.id = file_search.rowid
                WHERE file_search.content LIKE :like ESCAPE '\\'
                   OR f.title LIKE :like ESCAPE '\\'
                   OR f.rel_path LIKE :like ESCAPE '\\'
                ORDER BY f.rel_path COLLATE NOCASE
                LIMIT :limit
                """
            ),
            like_params,
        ).mappings()
        return [FileItem.model_validate(dict(row)) for row in rows]

    try:
        rows = session.execute(
            text(
                """
                SELECT f.id, f.rel_path, f.name, f.parent, f.title, f.size, f.mtime_ns,
                       bm25(file_search) AS rank
                FROM file_search
                JOIN files f ON f.id = file_search.rowid
                WHERE file_search MATCH :query
                ORDER BY rank, f.rel_path COLLATE NOCASE
                LIMIT :limit
                """
            ),
            {"query": quote_fts(query), "limit": limit},
        ).mappings()
        return [FileItem.model_validate(dict(row)) for row in rows]
    except Exception:
        rows = session.execute(
            text(
                """
                SELECT f.id, f.rel_path, f.name, f.parent, f.title, f.size, f.mtime_ns
                FROM file_search
                JOIN files f ON f.id = file_search.rowid
                WHERE file_search.content LIKE :like ESCAPE '\\'
                   OR f.title LIKE :like ESCAPE '\\'
                   OR f.rel_path LIKE :like ESCAPE '\\'
                ORDER BY f.rel_path COLLATE NOCASE
                LIMIT :limit
                """
            ),
            like_params,
        ).mappings()
        return [FileItem.model_validate(dict(row)) for row in rows]
