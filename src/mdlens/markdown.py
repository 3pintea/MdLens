from __future__ import annotations

import html
import posixpath
import re
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple

from markdown_it import MarkdownIt

MARKDOWN_LINK_SUFFIX = ".md"


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


def normalize_link_key(value: str) -> str:
    return value.strip().replace("\\", "/").strip("/").casefold()


def slugify_heading(value: str) -> str:
    slug = urllib.parse.unquote(value).strip().casefold()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^\w\-]+", "", slug, flags=re.UNICODE)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "heading"


def unique_heading_anchor(value: str, counts: dict[str, int]) -> str:
    base = slugify_heading(value)
    count = counts.get(base, 0)
    counts[base] = count + 1
    return base if count == 0 else f"{base}-{count + 1}"


def normalize_relative_target(current_rel_path: str, target_path: str) -> str | None:
    target_path = target_path.replace("\\", "/")
    if target_path.startswith("/"):
        normalized = posixpath.normpath(target_path.lstrip("/"))
    else:
        base = posixpath.dirname(current_rel_path.replace("\\", "/"))
        normalized = posixpath.normpath(posixpath.join(base, target_path))
    if normalized in {"", "."} or normalized.startswith("../") or normalized == "..":
        return None
    return normalized


def internal_file_url(file_id: int, fragment: str = "") -> str:
    url = f"/?id={file_id}"
    if fragment:
        url = f"{url}#{urllib.parse.quote(fragment, safe='-_.~')}"
    return url


class ResolvedLink(NamedTuple):
    file_id: int
    fragment: str = ""


def resolve_markdown_link(
    raw_url: str,
    current_rel_path: str,
    link_index: Mapping[str, int],
) -> ResolvedLink | None:
    parsed = urllib.parse.urlsplit(raw_url)
    if parsed.scheme or parsed.netloc or raw_url.startswith("#"):
        return None

    target_path = urllib.parse.unquote(parsed.path)
    if not target_path.casefold().endswith(MARKDOWN_LINK_SUFFIX):
        return None

    normalized = normalize_relative_target(current_rel_path, target_path)
    if normalized is None:
        return None
    file_id = link_index.get(normalize_link_key(normalized))
    if file_id is None:
        return None

    fragment = slugify_heading(parsed.fragment) if parsed.fragment else ""
    return ResolvedLink(file_id=file_id, fragment=fragment)


def resolve_wikilink(
    target: str,
    fragment: str,
    current_file_id: int,
    link_index: Mapping[str, int],
) -> ResolvedLink | None:
    target = target.strip()
    if target:
        file_id = link_index.get(normalize_link_key(target))
        if file_id is None and not target.casefold().endswith(MARKDOWN_LINK_SUFFIX):
            file_id = link_index.get(
                normalize_link_key(f"{target}{MARKDOWN_LINK_SUFFIX}")
            )
    else:
        file_id = current_file_id

    if file_id is None:
        return None
    return ResolvedLink(
        file_id=file_id,
        fragment=slugify_heading(fragment) if fragment else "",
    )


def parse_wikilink(value: str) -> tuple[str, str, str]:
    target_text, separator, alias = value.partition("|")
    target, _, fragment = target_text.strip().partition("#")
    label = alias.strip() if separator else ""
    if not label:
        label_source = target.strip() or fragment.strip() or target_text.strip()
        label = Path(label_source.replace("\\", "/")).name
        if label.casefold().endswith(MARKDOWN_LINK_SUFFIX):
            label = label[: -len(MARKDOWN_LINK_SUFFIX)]
    return target.strip(), fragment.strip(), label or value.strip()


def local_asset_url(file_id: int, raw_url: str) -> str:
    parsed = urllib.parse.urlsplit(raw_url)
    if parsed.scheme or parsed.netloc or raw_url.startswith("#"):
        return raw_url
    asset_path = urllib.parse.unquote(parsed.path)
    return "/asset?file={}&path={}".format(file_id, urllib.parse.quote(asset_path))


def set_internal_link_attrs(token: Any, link: ResolvedLink) -> None:
    token.attrSet("href", internal_file_url(link.file_id, link.fragment))
    token.attrSet("data-mdlens-file-id", str(link.file_id))
    if link.fragment:
        token.attrSet("data-mdlens-fragment", link.fragment)


def make_markdown() -> MarkdownIt:
    """MdLens 用の Markdown レンダラーを作成する。

    Returns:
        ローカル画像を `/asset` へ、Markdown 内リンクをアプリ内遷移へ差し替える
        MarkdownIt インスタンス。
    """

    markdown = MarkdownIt("commonmark", {"html": False})
    default_image = markdown.renderer.rules.get("image")
    default_link_open = markdown.renderer.rules.get("link_open")
    default_heading_open = markdown.renderer.rules.get("heading_open")

    def wikilink_rule(state: Any, silent: bool) -> bool:
        start = state.pos
        if state.src.startswith("![[", start) or not state.src.startswith("[[", start):
            return False
        close = state.src.find("]]", start + 2)
        if close < 0:
            return False
        content = state.src[start + 2 : close]
        if "\n" in content:
            return False
        if not silent:
            token = state.push("wikilink", "", 0)
            token.content = content
        state.pos = close + 2
        return True

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
            elif href.startswith("#"):
                token.attrSet(
                    "href",
                    f"#{urllib.parse.quote(slugify_heading(href[1:]), safe='-_.~')}",
                )
            elif not parsed.scheme and not parsed.netloc:
                link = resolve_markdown_link(
                    href,
                    str(env.get("current_path", "")),
                    env.get("link_index", {}),
                )
                if link:
                    set_internal_link_attrs(token, link)
                else:
                    token.attrSet("href", local_asset_url(file_id, href))
        if default_link_open:
            return default_link_open(tokens, idx, options, env)
        return markdown.renderer.renderToken(tokens, idx, options, env)

    def heading_open_rule(
        tokens: Any, idx: int, options: Any, env: dict[str, Any]
    ) -> str:
        token = tokens[idx]
        if not token.attrGet("id") and idx + 1 < len(tokens):
            inline_token = tokens[idx + 1]
            if inline_token.type == "inline":
                counts = env.setdefault("heading_counts", {})
                token.attrSet(
                    "id", unique_heading_anchor(inline_token.content, counts)
                )
        if default_heading_open:
            return default_heading_open(tokens, idx, options, env)
        return markdown.renderer.renderToken(tokens, idx, options, env)

    def wikilink_render_rule(
        tokens: Any, idx: int, _options: Any, env: dict[str, Any]
    ) -> str:
        target, fragment, label = parse_wikilink(tokens[idx].content)
        link = resolve_wikilink(
            target,
            fragment,
            int(env.get("file_id", 0)),
            env.get("link_index", {}),
        )
        escaped_label = html.escape(label, quote=False)
        if link is None:
            return f'<span class="missing-link">{escaped_label}</span>'

        attrs = [
            'href="{}"'.format(
                html.escape(internal_file_url(link.file_id, link.fragment), quote=True)
            ),
            f'data-mdlens-file-id="{link.file_id}"',
        ]
        if link.fragment:
            attrs.append(
                f'data-mdlens-fragment="{html.escape(link.fragment, quote=True)}"'
            )
        return f"<a {' '.join(attrs)}>{escaped_label}</a>"

    markdown.inline.ruler.before("emphasis", "wikilink", wikilink_rule)
    markdown.renderer.rules["image"] = image_rule
    markdown.renderer.rules["link_open"] = link_open_rule
    markdown.renderer.rules["heading_open"] = heading_open_rule
    markdown.renderer.rules["wikilink"] = wikilink_render_rule
    return markdown


MARKDOWN = make_markdown()


def render_markdown(
    text: str,
    file_id: int,
    current_path: str = "",
    link_index: Mapping[str, int] | None = None,
) -> str:
    return MARKDOWN.render(
        text,
        {
            "file_id": file_id,
            "current_path": current_path,
            "link_index": link_index or {},
            "heading_counts": {},
        },
    )
