from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .models import Base


class SqlExecutor(Protocol):
    def execute(self, statement, parameters=None, *args, **kwargs): ...


def sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path.as_posix()}"


def create_engine_for_index(index_path: Path) -> Engine:
    """index 用 SQLite engine を作成する。

    Args:
        index_path: SQLite index ファイルの保存先。

    Returns:
        MdLens の index 操作用に PRAGMA を設定した SQLAlchemy engine。
    """

    index_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        sqlite_url(index_path),
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

    return engine


def table_exists(executor: SqlExecutor, name: str) -> bool:
    row = executor.execute(
        text("SELECT 1 FROM sqlite_master WHERE name = :name LIMIT 1"),
        {"name": name},
    ).first()
    return row is not None


def get_meta_value(executor: SqlExecutor, key: str, default: str = "") -> str:
    if not table_exists(executor, "meta"):
        return default
    value = executor.execute(
        text("SELECT value FROM meta WHERE key = :key"),
        {"key": key},
    ).scalar_one_or_none()
    return str(value) if value is not None else default


def set_meta_value(executor: SqlExecutor, key: str, value: str) -> None:
    executor.execute(
        text(
            """
            INSERT INTO meta(key, value)
            VALUES(:key, :value)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        ),
        {"key": key, "value": value},
    )


def create_search_table(executor: SqlExecutor) -> str:
    """利用可能な検索 backend を選んで検索テーブルを作成する。

    Args:
        executor: SQLAlchemy の `Connection` または `Session`。

    Returns:
        作成した検索 backend 名。通常は `trigram`、未対応環境では `unicode61`、
        FTS5 自体が使えない場合は `plain`。
    """

    for tokenizer in ("trigram", "unicode61"):
        try:
            executor.execute(text("DROP TABLE IF EXISTS file_search"))
            executor.execute(
                text(
                    "CREATE VIRTUAL TABLE file_search "
                    f"USING fts5(content, tokenize='{tokenizer}')"
                )
            )
            return tokenizer
        except SQLAlchemyError:
            continue

    executor.execute(text("DROP TABLE IF EXISTS file_search"))
    executor.execute(
        text(
            """
            CREATE TABLE file_search(
                file_id INTEGER PRIMARY KEY,
                content TEXT NOT NULL
            )
            """
        )
    )
    return "plain"


def ensure_schema(engine: Engine) -> str:
    """通常テーブルと全文検索テーブルを作成または確認する。

    Args:
        engine: index 用 SQLite engine。

    Returns:
        現在の検索 backend 名。
    """

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        backend = get_meta_value(conn, "search_backend")
        if not table_exists(conn, "file_search"):
            backend = create_search_table(conn)
            set_meta_value(conn, "search_backend", backend)
        elif not backend:
            backend = "plain"
            set_meta_value(conn, "search_backend", backend)
    return backend


def replace_search_content(
    executor: SqlExecutor,
    backend: str,
    file_id: int,
    content: str,
) -> None:
    if backend == "plain":
        executor.execute(
            text(
                """
                INSERT INTO file_search(file_id, content)
                VALUES(:file_id, :content)
                ON CONFLICT(file_id) DO UPDATE SET content = excluded.content
                """
            ),
            {"file_id": file_id, "content": content},
        )
        return

    executor.execute(
        text("DELETE FROM file_search WHERE rowid = :file_id"), {"file_id": file_id}
    )
    executor.execute(
        text("INSERT INTO file_search(rowid, content) VALUES(:file_id, :content)"),
        {"file_id": file_id, "content": content},
    )


def delete_search_content(executor: SqlExecutor, backend: str, file_id: int) -> None:
    if backend == "plain":
        executor.execute(
            text("DELETE FROM file_search WHERE file_id = :file_id"),
            {"file_id": file_id},
        )
        return

    executor.execute(
        text("DELETE FROM file_search WHERE rowid = :file_id"), {"file_id": file_id}
    )
