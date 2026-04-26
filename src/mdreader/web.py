from __future__ import annotations

import mimetypes
from pathlib import Path
from threading import RLock
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .config import APP_NAME, AppConfig, default_index_path, resolve_root
from .db import create_engine_for_index, ensure_schema, get_meta_value
from .indexer import refresh_index
from .markdown import is_within_root, read_markdown, render_markdown
from .repository import count_files, get_file_record, list_files, search_files
from .schemas import (
    FolderSwitchRequest,
    IndexStats,
    MarkdownFileResponse,
    SearchResponse,
    TreeResponse,
)
from .ui import INDEX_HTML


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.lock:
        with Session(request.app.state.engine) as session:
            yield session


def current_config(request: Request) -> AppConfig:
    return request.app.state.config


def tree_response(request: Request, session: Session) -> TreeResponse:
    """現在のアプリ状態からファイルツリー API のレスポンスを作る。

    Args:
        request: FastAPI request。
        session: 現在の index DB session。

    Returns:
        画面の左ペインを描画するためのファイル一覧。
    """

    config = current_config(request)
    return TreeResponse(
        root=str(config.root),
        index=str(config.index_path),
        updated_at=get_meta_value(session, "updated_at"),
        file_count=count_files(session),
        files=list_files(session),
    )


def create_app(config: AppConfig, engine: Engine | None = None) -> FastAPI:
    """MdReader の FastAPI アプリを作成する。

    Args:
        config: 起動時の対象フォルダと index パス。
        engine: テストや外部起動で共有したい SQLAlchemy engine。

    Returns:
        API と HTML UI を提供する FastAPI アプリ。
    """

    engine = engine or create_engine_for_index(config.index_path)
    ensure_schema(engine)

    app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None)
    app.state.config = config
    app.state.engine = engine
    app.state.lock = RLock()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/tree", response_model=TreeResponse)
    def tree(request: Request, session: Session = Depends(get_session)) -> TreeResponse:
        return tree_response(request, session)

    @app.get("/api/file", response_model=MarkdownFileResponse)
    def file(
        request: Request,
        id: int = Query(..., ge=1),
        session: Session = Depends(get_session),
    ) -> MarkdownFileResponse:
        config = current_config(request)
        record = get_file_record(session, id)
        if record is None:
            raise HTTPException(status_code=404, detail="File not found")

        target = (config.root / record.rel_path).resolve()
        if not is_within_root(target, config.root) or not target.is_file():
            raise HTTPException(status_code=404, detail="File is not readable")

        text_content = read_markdown(target)
        return MarkdownFileResponse(
            id=record.id,
            path=record.rel_path,
            name=record.name,
            title=record.title,
            size=record.size,
            mtime_ns=record.mtime_ns,
            html=render_markdown(text_content, record.id),
        )

    @app.get("/api/search", response_model=SearchResponse)
    def search(
        q: str = Query("", max_length=400),
        session: Session = Depends(get_session),
    ) -> SearchResponse:
        return SearchResponse(query=q, results=search_files(session, q))

    @app.post("/api/refresh", response_model=IndexStats)
    def refresh(request: Request) -> IndexStats:
        with request.app.state.lock:
            config = current_config(request)
            return refresh_index(config.root, config.index_path, request.app.state.engine)

    @app.post("/api/folder", response_model=TreeResponse)
    def switch_folder(payload: FolderSwitchRequest, request: Request) -> TreeResponse:
        root = resolve_root(payload.folder.strip())
        if not root.exists() or not root.is_dir():
            raise HTTPException(status_code=400, detail=f"Folder not found: {root}")

        index_path = default_index_path(root)
        should_refresh = not index_path.exists()
        new_engine = create_engine_for_index(index_path)
        ensure_schema(new_engine)
        if should_refresh:
            refresh_index(root, index_path, new_engine)

        with request.app.state.lock:
            old_engine = request.app.state.engine
            request.app.state.config = AppConfig(root=root, index_path=index_path)
            request.app.state.engine = new_engine
            old_engine.dispose()
            with Session(new_engine) as session:
                return tree_response(request, session)

    @app.get("/asset")
    def asset(
        request: Request,
        file: int = Query(..., ge=1),
        path: str = Query(..., min_length=1),
        session: Session = Depends(get_session),
    ) -> FileResponse:
        config = current_config(request)
        record = get_file_record(session, file)
        if record is None:
            raise HTTPException(status_code=404, detail="File not found")

        base = (config.root / record.rel_path).resolve().parent
        target = (base / Path(path)).resolve()
        if not is_within_root(target, config.root) or not target.is_file():
            raise HTTPException(status_code=404, detail="Asset not found")

        media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return FileResponse(target, media_type=media_type, filename=target.name)

    return app
