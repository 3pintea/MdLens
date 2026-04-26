from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FileItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rel_path: str
    name: str
    parent: str
    title: str
    size: int
    mtime_ns: int


class TreeResponse(BaseModel):
    root: str
    index: str
    updated_at: str
    file_count: int
    files: list[FileItem]


class MarkdownFileResponse(BaseModel):
    id: int
    path: str
    name: str
    title: str
    size: int
    mtime_ns: int
    html: str


class SearchResponse(BaseModel):
    query: str
    results: list[FileItem]


class FolderSwitchRequest(BaseModel):
    folder: str = Field(min_length=1, max_length=1000)


class IndexStats(BaseModel):
    root: str
    index: str
    seen: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    errors: list[str] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    id: str
    kind: str
    status: str
    message: str = ""
    result: dict[str, Any] | None = None
    error: str = ""
