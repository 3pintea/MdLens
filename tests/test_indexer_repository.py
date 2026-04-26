from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mdlens.db import create_engine_for_index, ensure_schema, get_meta_value
from mdlens.indexer import iter_markdown_files, parent_path, refresh_index
from mdlens.repository import build_link_index, count_files, list_files, search_files
from sqlalchemy.orm import Session


def test_refresh_index_tracks_files_search_and_deletions(workspace_tmp: Path) -> None:
    # Given: Markdown、非 Markdown、除外ディレクトリを含むライブラリ。
    root = workspace_tmp / "library"
    docs = root / "docs"
    skipped = root / ".venv"
    docs.mkdir(parents=True)
    skipped.mkdir()
    note = docs / "note.md"
    note.write_text("# Note Title\n\nSQLite and uv are here.", encoding="utf-8")
    (root / "ignore.txt").write_text("not markdown", encoding="utf-8")
    (skipped / "skip.md").write_text("# Skip", encoding="utf-8")
    index_path = root / ".mdlens_index.sqlite3"

    # When: 初回 index 更新を実行する。
    stats = refresh_index(root, index_path)

    # Then: Markdown だけが登録され、検索対象にもなる。
    assert stats.seen == 1
    assert stats.updated == 1
    assert stats.errors == []
    assert [rel for _, rel in iter_markdown_files(root)] == ["docs/note.md"]
    assert parent_path("docs/note.md") == "docs"
    assert parent_path("note.md") == ""

    engine = create_engine_for_index(index_path)
    ensure_schema(engine)
    with Session(engine) as session:
        files = list_files(session)
        assert count_files(session) == 1
        assert files[0].title == "Note Title"
        assert search_files(session, "SQLite")[0].rel_path == "docs/note.md"
        assert search_files(session, "uv")[0].rel_path == "docs/note.md"
        assert search_files(session, "") == []
        assert get_meta_value(session, "root") == str(root)

    # Given: ファイル内容が変わり、さらにファイルが削除される。
    note.write_text("# New Title\n\nchanged content", encoding="utf-8")

    # When: 更新後に再 index する。
    changed_stats = refresh_index(root, index_path)

    # Then: 既存レコードが更新される。
    assert changed_stats.updated == 1
    with Session(engine) as session:
        assert list_files(session)[0].title == "New Title"

    # When: Markdown ファイルを削除して再 index する。
    note.unlink()
    deleted_stats = refresh_index(root, index_path)

    # Then: stale なレコードと検索本文が削除される。
    assert deleted_stats.deleted == 1
    with Session(engine) as session:
        assert count_files(session) == 0
        assert search_files(session, "changed") == []
    engine.dispose()


def test_refresh_index_marks_unchanged_files(workspace_tmp: Path) -> None:
    # Given: 既に index 済みの Markdown ファイル。
    root = workspace_tmp / "library"
    root.mkdir()
    (root / "note.md").write_text("# Stable\n\nsame", encoding="utf-8")
    index_path = root / ".mdlens_index.sqlite3"
    refresh_index(root, index_path)

    # When: ファイルを変更せずに再 index する。
    stats = refresh_index(root, index_path)

    # Then: 本文の読み直しは不要として unchanged 扱いになる。
    assert stats.updated == 0
    assert stats.unchanged == 1


def test_refresh_index_keeps_existing_record_when_read_fails(
    workspace_tmp: Path,
) -> None:
    # Given: 既に index 済みの Markdown ファイル。
    root = workspace_tmp / "library"
    root.mkdir()
    note = root / "note.md"
    note.write_text("# Stable\n\nsame", encoding="utf-8")
    index_path = root / ".mdlens_index.sqlite3"
    refresh_index(root, index_path)
    note.write_text("# Changed\n\nsame", encoding="utf-8")

    # When: 更新走査中に読み込みだけ失敗する。
    with patch("mdlens.indexer.read_markdown", side_effect=OSError("locked")):
        stats = refresh_index(root, index_path)

    # Then: 既存レコードは stale 扱いで削除されない。
    engine = create_engine_for_index(index_path)
    ensure_schema(engine)
    with Session(engine) as session:
        assert stats.deleted == 0
        assert stats.unchanged == 1
        assert stats.errors
        assert count_files(session) == 1
    engine.dispose()


def test_build_link_index_omits_ambiguous_titles(workspace_tmp: Path) -> None:
    # Given: 同じタイトルを持つ複数の Markdown ファイル。
    root = workspace_tmp / "library"
    root.mkdir()
    (root / "a.md").write_text("# Same\n\nA", encoding="utf-8")
    (root / "b.md").write_text("# Same\n\nB", encoding="utf-8")
    index_path = root / ".mdlens_index.sqlite3"
    refresh_index(root, index_path)

    # When: WikiLink 解決用の索引を作る。
    engine = create_engine_for_index(index_path)
    ensure_schema(engine)
    with Session(engine) as session:
        link_index = build_link_index(session)

    # Then: 一意なパスは解決でき、曖昧なタイトルは誤解決しない。
    assert "a.md" in link_index
    assert "b.md" in link_index
    assert "same" not in link_index
    engine.dispose()
