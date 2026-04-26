from __future__ import annotations

from pathlib import Path

from mdreader.markdown import (
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
