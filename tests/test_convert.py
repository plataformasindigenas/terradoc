"""Tests for terradoc converters."""

import json

from terradoc.convert import (
    _format_citation,
    _normalize_records,
    _resolve_references,
    CONVERTERS,
)


def test_converters_registry_has_all_modules():
    """CONVERTERS registry contains all 5 module converters."""
    expected = {"dictionary", "fauna", "encyclopedia", "bibliography", "recordings"}
    assert set(CONVERTERS.keys()) == expected


def test_normalize_records_dicts():
    """_normalize_records handles plain dicts."""
    records = [{"a": 1, "b": 2}]
    result = _normalize_records(records)
    assert result == [{"a": 1, "b": 2}]


def test_format_citation_article():
    """_format_citation formats article type correctly."""
    entry = {
        "ENTRYTYPE": "article",
        "author": "Smith, J.",
        "year": "2020",
        "title": "A Study",
        "journal": "Nature",
        "volume": "10",
        "pages": "1-5",
        "doi": "10.1234/test",
    }
    result = _format_citation(entry)
    assert "Smith, J." in result
    assert "(2020)" in result
    assert "*A Study*" in result
    assert "Nature" in result
    assert "10" in result
    assert "1-5" in result
    assert "doi:10.1234/test" in result


def test_format_citation_book():
    """_format_citation formats book type correctly."""
    entry = {
        "ENTRYTYPE": "book",
        "author": "Doe, A.",
        "year": "2019",
        "title": "My Book",
        "publisher": "Press",
        "address": "City",
    }
    result = _format_citation(entry)
    assert "Doe, A." in result
    assert "(2019)" in result
    assert "*My Book*" in result
    assert "Press" in result
    assert "City" in result


def test_format_citation_phdthesis():
    """_format_citation formats phdthesis type correctly."""
    entry = {
        "ENTRYTYPE": "phdthesis",
        "author": "Lee, B.",
        "year": "2021",
        "title": "Thesis Title",
        "school": "University",
    }
    result = _format_citation(entry)
    assert "PhD thesis" in result
    assert "University" in result


def test_format_citation_misc():
    """_format_citation handles unknown types gracefully."""
    entry = {
        "ENTRYTYPE": "misc",
        "author": "Author",
        "year": "2022",
        "title": "Something",
    }
    result = _format_citation(entry)
    assert "Author" in result
    assert "(2022)" in result
    assert "*Something*" in result


def test_resolve_references_found():
    """_resolve_references resolves known BibTeX keys."""
    bib_data = {
        "key1": {
            "ENTRYTYPE": "book",
            "author": "Auth",
            "year": "2020",
            "title": "Title",
        }
    }
    result = _resolve_references(["key1"], bib_data)
    assert len(result) == 1
    assert result[0]["key"] == "key1"
    assert "Auth" in result[0]["formatted"]
    assert result[0]["author"] == "Auth"


def test_resolve_references_not_found():
    """_resolve_references marks missing keys with error."""
    result = _resolve_references(["missing-key"], {})
    assert len(result) == 1
    assert result[0]["key"] == "missing-key"
    assert result[0]["error"] is True
    assert "not found" in result[0]["formatted"]
