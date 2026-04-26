from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt


def decode_markdown(data: bytes) -> str:
    """Markdown ファイルの bytes を文字列へ変換する。

    Args:
        data: ファイルから読み込んだ bytes。

    Returns:
        UTF-8 BOM 付き、通常 UTF-8、または CP932 として復号した文字列。
    """

    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp932", errors="replace")


def read_markdown(path: Path) -> str:
    return decode_markdown(path.read_bytes())


def title_from_markdown(text: str, fallback: str) -> str:
    """Markdown の先頭付近から最初の見出しをタイトルとして抽出する。

    Args:
        text: Markdown 本文。
        fallback: 見出しが見つからない場合のタイトル。

    Returns:
        抽出したタイトル、または fallback。
    """

    for line in text.splitlines()[:120]:
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            title = re.sub(r"\s+", " ", match.group(1)).strip()
            if title:
                return title
    return fallback


def is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def make_markdown() -> MarkdownIt:
    """MdLens 用の Markdown レンダラーを作成する。

    Returns:
        ローカル画像とリンクを `/asset` へ差し替える MarkdownIt インスタンス。
    """

    markdown = MarkdownIt("commonmark", {"html": False})
    default_image = markdown.renderer.rules.get("image")
    default_link_open = markdown.renderer.rules.get("link_open")

    def local_asset_url(file_id: int, raw_url: str) -> str:
        parsed = urllib.parse.urlsplit(raw_url)
        if parsed.scheme or parsed.netloc or raw_url.startswith("#"):
            return raw_url
        asset_path = urllib.parse.unquote(parsed.path)
        return "/asset?file={}&path={}".format(file_id, urllib.parse.quote(asset_path))

    def image_rule(tokens: Any, idx: int, options: Any, env: dict[str, Any]) -> str:
        token = tokens[idx]
        file_id = int(env.get("file_id", 0))
        src = token.attrGet("src")
        if src and file_id:
            token.attrSet("src", local_asset_url(file_id, src))
        token.attrSet("loading", "lazy")
        token.attrSet("decoding", "async")
        if default_image:
            return default_image(tokens, idx, options, env)
        return markdown.renderer.renderToken(tokens, idx, options, env)

    def link_open_rule(tokens: Any, idx: int, options: Any, env: dict[str, Any]) -> str:
        token = tokens[idx]
        file_id = int(env.get("file_id", 0))
        href = token.attrGet("href")
        if href and file_id:
            parsed = urllib.parse.urlsplit(href)
            if parsed.scheme in {"http", "https"}:
                token.attrSet("target", "_blank")
                token.attrSet("rel", "noreferrer")
            elif not parsed.scheme and not parsed.netloc and not href.startswith("#"):
                token.attrSet("href", local_asset_url(file_id, href))
        if default_link_open:
            return default_link_open(tokens, idx, options, env)
        return markdown.renderer.renderToken(tokens, idx, options, env)

    markdown.renderer.rules["image"] = image_rule
    markdown.renderer.rules["link_open"] = link_open_rule
    return markdown


MARKDOWN = make_markdown()


def render_markdown(text: str, file_id: int) -> str:
    return MARKDOWN.render(text, {"file_id": file_id})
