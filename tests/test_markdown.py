from __future__ import annotations

from pathlib import Path

from mdlens.markdown import (
    decode_markdown,
    is_within_root,
    read_markdown,
    render_markdown,
    title_from_markdown,
)


def test_markdown_helpers_decode_title_and_asset_links(workspace_tmp: Path) -> None:
    # Given: BOM 付き UTF-8、CP932、相対画像リンクを含む Markdown。
    utf8_bom = b"\xef\xbb\xbf# Title\nbody"
    cp932 = "本文".encode("cp932")
    markdown = (
        "# Main\n\n"
        "![alt](images/pic.png)\n\n"
        "![remote](https://example.com/pic.png)\n\n"
        "[site](https://example.com)\n\n"
        "[local](docs/next.md)"
    )

    # When: 本文の復号、タイトル抽出、HTML レンダリングを行う。
    decoded_utf8 = decode_markdown(utf8_bom)
    decoded_cp932 = decode_markdown(cp932)
    title = title_from_markdown(markdown, "fallback")
    html = render_markdown(markdown, file_id=7)

    # Then: 日本語復号、見出しタイトル、ローカル asset URL が期待通りになる。
    assert decoded_utf8.startswith("# Title")
    assert decoded_cp932 == "本文"
    assert title == "Main"
    assert "/asset?file=7&amp;path=images/pic.png" in html
    assert 'target="_blank"' in html
    assert 'src="https://example.com/pic.png"' in html
    assert 'href="/asset?file=7&amp;path=docs/next.md"' in html
    assert title_from_markdown("body only", "fallback") == "fallback"
    assert render_markdown("[anchor](#top)", file_id=7).count("#top") == 1

    # Given: root 配下と root 外のパス。
    root = workspace_tmp / "root"
    child = root / "note.md"
    outside = workspace_tmp / "outside.md"
    root.mkdir()
    child.write_text("# From file", encoding="utf-8")

    # When / Then: root 配下判定が安全側に働く。
    assert is_within_root(child, root)
    assert not is_within_root(outside, root)
    assert read_markdown(child).startswith("# From")


def test_markdown_renders_internal_markdown_and_wikilinks() -> None:
    # Given: 相対 Markdown リンクと Obsidian 形式 WikiLink を含む本文。
    markdown = (
        "# Main Title\n\n"
        "[Next](next.md#Details)\n\n"
        "[[Next Note|Read next]]\n\n"
        "[[#Main Title]]\n\n"
        "[[Missing Note]]"
    )
    link_index = {
        "docs/next.md": 8,
        "next note": 9,
    }

    # When: 現在ファイルの位置とリンク索引を渡して HTML 化する。
    html = render_markdown(
        markdown,
        file_id=7,
        current_path="docs/home.md",
        link_index=link_index,
    )

    # Then: 内部リンクは file id 付きのアプリ内リンクとして描画される。
    assert 'id="main-title"' in html
    assert 'href="/?id=8#details"' in html
    assert 'data-mdlens-file-id="8"' in html
    assert 'href="/?id=9"' in html
    assert "Read next" in html
    assert 'href="/?id=7#main-title"' in html
    assert '<span class="missing-link">Missing Note</span>' in html


def test_markdown_handles_link_edge_cases() -> None:
    # Given: 重複見出し、root 相対リンク、asset リンクを含む Markdown。
    markdown = (
        "# Same\n\n"
        "## Same\n\n"
        "[Local heading](#Same)\n\n"
        "[Root](/root.md)\n\n"
        "[Asset](manual.pdf)\n\n"
        "![Embed stays text](/image.png)"
    )

    # When: root 相対 Markdown リンクだけが link index に存在する。
    html = render_markdown(
        markdown,
        file_id=4,
        current_path="docs/home.md",
        link_index={"root.md": 10},
    )

    # Then: 見出しIDは重複回避され、Markdown 以外の相対リンクは asset 扱いになる。
    assert 'id="same"' in html
    assert 'id="same-2"' in html
    assert 'href="#same"' in html
    assert 'href="/?id=10"' in html
    assert 'href="/asset?file=4&amp;path=manual.pdf"' in html
    assert 'src="/asset?file=4&amp;path=/image.png"' in html
