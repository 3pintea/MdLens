from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from mdreader.db import (
    create_engine_for_index,
    delete_search_content,
    ensure_schema,
    get_meta_value,
    replace_search_content,
    set_meta_value,
    sqlite_url,
)
from mdreader.models import FileRecord
from mdreader.repository import search_files


def test_plain_search_backend_replaces_search_content(workspace_tmp) -> None:
    # Given: FTS を使わない plain backend の検索テーブル。
    index_path = workspace_tmp / "plain.sqlite3"
    engine = create_engine_for_index(index_path)
    ensure_schema(engine)
    assert sqlite_url(index_path).startswith("sqlite+pysqlite:///")

    with Session(engine) as session:
        with session.begin():
            session.execute(text("DROP TABLE IF EXISTS file_search"))
            session.execute(
                text(
                    "CREATE TABLE file_search(file_id INTEGER PRIMARY KEY, content TEXT NOT NULL)"
                )
            )
            set_meta_value(session, "search_backend", "plain")
            record = FileRecord(
                rel_path="note.md",
                name="note.md",
                parent="",
                title="Plain Note",
                size=10,
                mtime_ns=1,
                seen_scan=1,
                indexed_at="now",
            )
            session.add(record)
            session.flush()
            replace_search_content(session, "plain", record.id, "Plain body")
            file_id = record.id

        # When: plain backend で検索する。
        results = search_files(session, "Plain")

        # Then: LIKE 検索で対象ファイルが返る。
        assert get_meta_value(session, "search_backend") == "plain"
        assert [item.rel_path for item in results] == ["note.md"]

        # When: 検索本文を削除する。
        session.rollback()
        with session.begin():
            delete_search_content(session, "plain", file_id)

        # Then: 検索にヒットしなくなる。
        assert search_files(session, "Plain") == []
    engine.dispose()
