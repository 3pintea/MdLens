from __future__ import annotations

import mimetypes
import uuid
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
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
from .repo_clone import (
    RepositoryCloneError,
    RepositoryWorkspace,
    UnsupportedRepositoryError,
    cleanup_repository_workspace,
    clone_repository,
    looks_like_repository_url,
    parse_repository_source,
)
from .repository import (
    build_link_index,
    count_files,
    get_file_record,
    list_files,
    search_files,
)
from .schemas import (
    FolderSwitchRequest,
    IndexStats,
    JobStatusResponse,
    MarkdownFileResponse,
    SearchResponse,
    TreeResponse,
)
from .ui import INDEX_HTML


@dataclass(frozen=True)
class RequestState:
    config: AppConfig
    session: Session


def get_request_state(request: Request) -> Iterator[RequestState]:
    with request.app.state.lock:
        config = request.app.state.config
        engine = request.app.state.engine
        session = Session(engine)
        session.connection()
    try:
        yield RequestState(config=config, session=session)
    finally:
        session.close()


def prepare_source_config(
    source_text: str,
) -> tuple[AppConfig, Engine, RepositoryWorkspace | None]:
    """入力値から表示対象の root、index engine、一時 clone 情報を準備する。

    Args:
        source_text: 画面の入力欄から送られたフォルダパス、またはGitHub/GitLab URL。

    Returns:
        切り替え先の設定、SQLAlchemy engine、一時 clone 情報。

    Raises:
        HTTPException: フォルダが存在しない、またはcloneに失敗した場合。
    """

    workspace: RepositoryWorkspace | None = None
    if looks_like_repository_url(source_text):
        try:
            workspace = clone_repository(parse_repository_source(source_text))
        except UnsupportedRepositoryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RepositoryCloneError as exc:
            raise HTTPException(
                status_code=502, detail=f"Repository clone failed: {exc}"
            ) from exc
        root = workspace.root
    else:
        root = resolve_root(source_text)
        if not root.exists() or not root.is_dir():
            raise HTTPException(status_code=400, detail=f"Folder not found: {root}")

    index_path = default_index_path(root)
    should_refresh = not index_path.exists()
    new_engine = create_engine_for_index(index_path)
    try:
        ensure_schema(new_engine)
        if should_refresh:
            refresh_index(root, index_path, new_engine)
    except Exception:
        new_engine.dispose()
        cleanup_repository_workspace(workspace)
        raise

    return AppConfig(root=root, index_path=index_path), new_engine, workspace


def tree_response(config: AppConfig, session: Session) -> TreeResponse:
    """現在のアプリ状態からファイルツリー API のレスポンスを作る。

    Args:
        config: 現在の表示対象設定。
        session: 現在の index DB session。

    Returns:
        画面の左ペインを描画するためのファイル一覧。
    """

    return TreeResponse(
        root=str(config.root),
        index=str(config.index_path),
        updated_at=get_meta_value(session, "updated_at"),
        file_count=count_files(session),
        files=list_files(session),
    )


def switch_source(
    request: Request,
    source_text: str,
) -> TreeResponse:
    with request.app.state.operation_lock:
        new_config, new_engine, new_workspace = prepare_source_config(source_text)

        with request.app.state.lock:
            old_engine = request.app.state.engine
            old_workspace = request.app.state.repo_workspace
            request.app.state.config = new_config
            request.app.state.engine = new_engine
            request.app.state.repo_workspace = new_workspace
            old_engine.dispose()
            cleanup_repository_workspace(old_workspace)
            with Session(new_engine) as session:
                return tree_response(new_config, session)


def refresh_current_index(request: Request) -> IndexStats:
    with request.app.state.operation_lock:
        with request.app.state.lock:
            config = request.app.state.config
            engine = request.app.state.engine
        return refresh_index(config.root, config.index_path, engine)


def update_job(request: Request, job_id: str, **values: object) -> None:
    with request.app.state.jobs_lock:
        job = request.app.state.jobs[job_id]
        job.update(values)


def start_job(request: Request, kind: str, work) -> JobStatusResponse:
    job_id = uuid.uuid4().hex
    with request.app.state.jobs_lock:
        if len(request.app.state.jobs) > 50:
            for stale_id in list(request.app.state.jobs)[:10]:
                del request.app.state.jobs[stale_id]
        request.app.state.jobs[job_id] = {
            "id": job_id,
            "kind": kind,
            "status": "pending",
            "message": "Queued",
            "result": None,
            "error": "",
        }

    def run() -> None:
        update_job(request, job_id, status="running", message="Running")
        try:
            result = work()
        except HTTPException as exc:
            update_job(
                request,
                job_id,
                status="failed",
                message="Failed",
                error=str(exc.detail),
            )
        except Exception as exc:
            update_job(
                request,
                job_id,
                status="failed",
                message="Failed",
                error=str(exc),
            )
        else:
            update_job(
                request,
                job_id,
                status="succeeded",
                message="Done",
                result=result.model_dump(),
            )

    request.app.state.executor.submit(run)
    return JobStatusResponse(**request.app.state.jobs[job_id])


def create_app(config: AppConfig, engine: Engine | None = None) -> FastAPI:
    """MdLens の FastAPI アプリを作成する。

    Args:
        config: 起動時の対象フォルダと index パス。
        engine: テストや外部起動で共有したい SQLAlchemy engine。

    Returns:
        API と HTML UI を提供する FastAPI アプリ。
    """

    engine = engine or create_engine_for_index(config.index_path)
    ensure_schema(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            app.state.executor.shutdown(wait=False, cancel_futures=True)
            cleanup_repository_workspace(app.state.repo_workspace)

    app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.config = config
    app.state.engine = engine
    app.state.lock = RLock()
    app.state.operation_lock = RLock()
    app.state.jobs_lock = RLock()
    app.state.jobs = {}
    app.state.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mdlens")
    app.state.repo_workspace = None

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/tree", response_model=TreeResponse)
    def tree(state: RequestState = Depends(get_request_state)) -> TreeResponse:
        return tree_response(state.config, state.session)

    @app.get("/api/file", response_model=MarkdownFileResponse)
    def file(
        id: int = Query(..., ge=1),
        state: RequestState = Depends(get_request_state),
    ) -> MarkdownFileResponse:
        record = get_file_record(state.session, id)
        if record is None:
            raise HTTPException(status_code=404, detail="File not found")

        target = (state.config.root / record.rel_path).resolve()
        if not is_within_root(target, state.config.root) or not target.is_file():
            raise HTTPException(status_code=404, detail="File is not readable")

        text_content = read_markdown(target)
        return MarkdownFileResponse(
            id=record.id,
            path=record.rel_path,
            name=record.name,
            title=record.title,
            size=record.size,
            mtime_ns=record.mtime_ns,
            html=render_markdown(
                text_content,
                record.id,
                record.rel_path,
                build_link_index(state.session),
            ),
        )

    @app.get("/api/search", response_model=SearchResponse)
    def search(
        q: str = Query("", max_length=400),
        state: RequestState = Depends(get_request_state),
    ) -> SearchResponse:
        return SearchResponse(query=q, results=search_files(state.session, q))

    @app.post("/api/refresh", response_model=IndexStats)
    def refresh(request: Request) -> IndexStats:
        return refresh_current_index(request)

    @app.post("/api/jobs/refresh", response_model=JobStatusResponse)
    def refresh_job(request: Request) -> JobStatusResponse:
        return start_job(request, "refresh", lambda: refresh_current_index(request))

    @app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
    def job_status(job_id: str, request: Request) -> JobStatusResponse:
        with request.app.state.jobs_lock:
            job = request.app.state.jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job not found")
            return JobStatusResponse(**job)

    @app.post("/api/folder", response_model=TreeResponse)
    def switch_folder(payload: FolderSwitchRequest, request: Request) -> TreeResponse:
        return switch_source(request, payload.folder.strip())

    @app.post("/api/jobs/folder", response_model=JobStatusResponse)
    def switch_folder_job(
        payload: FolderSwitchRequest, request: Request
    ) -> JobStatusResponse:
        return start_job(
            request,
            "folder",
            lambda: switch_source(request, payload.folder.strip()),
        )

    @app.get("/asset")
    def asset(
        file: int = Query(..., ge=1),
        path: str = Query(..., min_length=1),
        state: RequestState = Depends(get_request_state),
    ) -> FileResponse:
        record = get_file_record(state.session, file)
        if record is None:
            raise HTTPException(status_code=404, detail="File not found")

        base = (state.config.root / record.rel_path).resolve().parent
        asset_path = Path(path)
        if asset_path.is_absolute() or path.startswith(("/", "\\")):
            target = (state.config.root / path.lstrip("/\\")).resolve()
        else:
            target = (base / asset_path).resolve()
        if not is_within_root(target, state.config.root) or not target.is_file():
            raise HTTPException(status_code=404, detail="Asset not found")

        media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return FileResponse(target, media_type=media_type, filename=target.name)

    return app
