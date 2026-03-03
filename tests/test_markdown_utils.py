"""Tests for terradoc markdown utilities."""

from terradoc.markdown_utils import (
    assert_no_html,
    build_category_tree,
    build_markdown_renderer,
    generate_toc,
    html_to_text,
    process_wikilinks,
)
import pytest


def test_build_markdown_renderer():
    """Markdown renderer produces HTML."""
    md = build_markdown_renderer()
    result = md.render("# Hello")
    assert "<h1>" in result
    assert "Hello" in result


def test_html_to_text():
    """html_to_text strips tags and returns plain text."""
    assert html_to_text("<p>Hello <strong>world</strong></p>") == "Hello world"
    assert html_to_text("") == ""
    assert html_to_text(None) == ""


def test_assert_no_html_clean():
    """assert_no_html passes for clean markdown."""
    assert_no_html("This is **bold** markdown.", "test-id")


def test_assert_no_html_with_tags():
    """assert_no_html raises for HTML tags."""
    with pytest.raises(ValueError, match="contains HTML tags"):
        assert_no_html("This has <div>html</div> in it.", "test-id")


def test_process_wikilinks_valid():
    """Valid wikilinks become markdown links."""
    all_ids = {"target-page"}
    result = process_wikilinks("See [[target-page]].", all_ids)
    assert "[target-page](target-page.html)" in result


def test_process_wikilinks_piped():
    """Piped wikilinks use display text."""
    all_ids = {"target-page"}
    result = process_wikilinks("See [[target-page|Display Text]].", all_ids)
    assert "[Display Text](target-page.html)" in result


def test_process_wikilinks_broken():
    """Broken wikilinks get marked with broken-link class."""
    result = process_wikilinks("See [[nonexistent]].", set())
    assert 'class="broken-link"' in result


def test_build_category_tree():
    """Category tree is built correctly from hierarchical paths."""
    entries = [
        {"categories": ["a/b", "a/c"]},
        {"categories": ["a/b"]},
        {"categories": ["d"]},
    ]
    tree = build_category_tree(entries)
    assert tree["a"]["_count"] == 3
    assert tree["a"]["b"]["_count"] == 2
    assert tree["a"]["c"]["_count"] == 1
    assert tree["d"]["_count"] == 1


def test_build_category_tree_empty():
    """Empty entries produce empty tree."""
    assert build_category_tree([]) == {}
    assert build_category_tree([{"categories": None}]) == {}


def test_generate_toc_with_headings():
    """TOC is generated from multiple headings."""
    html = "<h3>Section A</h3><p>text</p><h3>Section B</h3>"
    toc, modified = generate_toc(html, "test")
    assert "Section A" in toc
    assert "Section B" in toc
    assert 'id="test-section-0"' in modified
    assert 'id="test-section-1"' in modified


def test_generate_toc_single_heading():
    """Single heading returns empty TOC."""
    html = "<h3>Only One</h3><p>text</p>"
    toc, modified = generate_toc(html, "test")
    assert toc == ""
    assert modified == html
