"""Unit tests of the token aware chunker.

The tests build the extraction contracts by hand - no PDF is parsed and no
extractor is involved - so that the behaviour of the chunker is checked in
isolation.
"""

from __future__ import annotations

import json

import pytest

from app.core.enums import ChunkType
from app.ingestion.chunking import (
    Chunker,
    ChunkerConfig,
    TokenAwareChunker,
    count_tokens,
    render_table_chunk,
)
from app.ingestion.contracts import ExtractedDocument, ExtractedPage, ExtractedTable

pytestmark = pytest.mark.unit


def _words(count: int, prefix: str = "w") -> str:
    """Return *count* whitespace separated words, each a single token."""
    return " ".join(f"{prefix}{index}" for index in range(count))


def _document(*pages: ExtractedPage) -> ExtractedDocument:
    """Return a document that contains *pages*."""
    return ExtractedDocument(pages=pages, page_count=len(pages))


def _fingerprint(chunks):
    """Return a comparable representation of *chunks*."""
    return [
        (
            chunk.chunk_index,
            chunk.content,
            chunk.chunk_type,
            chunk.page_start,
            chunk.page_end,
            chunk.section_heading,
            chunk.token_count,
            dict(chunk.metadata),
        )
        for chunk in chunks
    ]


# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------


def test_count_tokens_on_known_string() -> None:
    assert count_tokens("Hello, world!") == 4
    assert count_tokens("") == 0
    assert count_tokens("   \n\t ") == 0
    assert count_tokens("A B") == 2
    assert count_tokens("Revenue 1,234") == 4
    assert count_tokens("word42") == 1
    assert count_tokens("don\u2019t") == 3


def test_count_tokens_matches_the_documented_pattern() -> None:
    import re

    text = "Item 7. Financial Statements (2024) - revenue: 1,234"
    assert count_tokens(text) == len(re.findall(r"\w+|[^\w\s]", text))


# ---------------------------------------------------------------------------
# ChunkerConfig validation
# ---------------------------------------------------------------------------


def test_chunker_config_defaults() -> None:
    config = ChunkerConfig()
    assert config.chunk_size_tokens == 512
    assert config.chunk_overlap_tokens == 64
    assert config.chunk_min_tokens == 32
    assert config.chunk_max_tokens == 1024


def test_chunker_config_rejects_overlap_not_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        ChunkerConfig(chunk_size_tokens=100, chunk_overlap_tokens=100)
    with pytest.raises(ValueError):
        ChunkerConfig(chunk_size_tokens=100, chunk_overlap_tokens=250)


def test_chunker_config_rejects_min_greater_than_size() -> None:
    with pytest.raises(ValueError):
        ChunkerConfig(chunk_size_tokens=100, chunk_min_tokens=101)


def test_chunker_config_rejects_max_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        ChunkerConfig(chunk_size_tokens=100, chunk_max_tokens=99)


def test_chunker_config_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError):
        ChunkerConfig(chunk_size_tokens=0)


def test_chunker_config_rejects_negative_overlap() -> None:
    with pytest.raises(ValueError):
        ChunkerConfig(chunk_size_tokens=100, chunk_overlap_tokens=-1)


def test_chunker_overrides_and_unknown_option() -> None:
    chunker = TokenAwareChunker(chunk_size_tokens=128)
    assert chunker.config.chunk_size_tokens == 128
    assert chunker.config.chunk_overlap_tokens == 64

    base = ChunkerConfig(chunk_size_tokens=128, chunk_overlap_tokens=16)
    chunker = TokenAwareChunker(base, chunk_min_tokens=8)
    assert chunker.config.chunk_size_tokens == 128
    assert chunker.config.chunk_overlap_tokens == 16
    assert chunker.config.chunk_min_tokens == 8

    with pytest.raises(TypeError):
        TokenAwareChunker(chunk_szie_tokens=128)


def test_chunker_satisfies_the_chunker_protocol() -> None:
    assert isinstance(TokenAwareChunker(), Chunker)


# ---------------------------------------------------------------------------
# windowing
# ---------------------------------------------------------------------------


def test_long_page_is_split_into_multiple_chunks() -> None:
    config = ChunkerConfig(
        chunk_size_tokens=50,
        chunk_overlap_tokens=10,
        chunk_min_tokens=5,
        chunk_max_tokens=200,
    )
    page = ExtractedPage(page_number=3, text=_words(200))
    chunks = TokenAwareChunker(config).chunk(_document(page))

    assert len(chunks) > 1
    for chunk in chunks:
        assert count_tokens(chunk.content) <= config.chunk_size_tokens
        assert chunk.token_count == count_tokens(chunk.content)
        assert chunk.page_start == 3
        assert chunk.page_end == 3
        assert chunk.chunk_type == ChunkType.TEXT.value
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_consecutive_windows_overlap() -> None:
    config = ChunkerConfig(
        chunk_size_tokens=50,
        chunk_overlap_tokens=10,
        chunk_min_tokens=5,
        chunk_max_tokens=200,
    )
    page = ExtractedPage(page_number=1, text=_words(120))
    chunks = TokenAwareChunker(config).chunk(_document(page))

    assert len(chunks) >= 2
    first = chunks[0].content.split()
    second = chunks[1].content.split()
    assert first[-10:] == second[:10]


def test_short_page_becomes_a_single_short_chunk() -> None:
    page = ExtractedPage(page_number=1, text="Only a few words here.")
    chunks = TokenAwareChunker().chunk(_document(page))

    assert len(chunks) == 1
    assert chunks[0].content == "Only a few words here."
    assert chunks[0].token_count == count_tokens(chunks[0].content)
    assert chunks[0].section_heading is None


def test_whitespace_only_page_produces_no_chunk() -> None:
    page = ExtractedPage(page_number=1, text="   \n\t  \n ")
    assert TokenAwareChunker().chunk(_document(page)) == []


def test_empty_document_produces_no_chunk() -> None:
    assert TokenAwareChunker().chunk(ExtractedDocument()) == []
    assert TokenAwareChunker().chunk(_document()) == []


def test_no_text_chunk_exceeds_the_maximum_token_budget() -> None:
    config = ChunkerConfig(
        chunk_size_tokens=60,
        chunk_overlap_tokens=10,
        chunk_min_tokens=20,
        chunk_max_tokens=120,
    )
    page = ExtractedPage(page_number=1, text=_words(500))
    chunks = TokenAwareChunker(config).chunk(_document(page))

    assert chunks
    for chunk in chunks:
        assert count_tokens(chunk.content) <= config.chunk_max_tokens

# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_chunking_is_deterministic() -> None:
    page_one = ExtractedPage(
        page_number=1,
        text="Item 1. Business\n" + _words(120, "alpha"),
        headings=("Item 1. Business",),
    )
    page_two = ExtractedPage(
        page_number=2,
        text="Item 1A. Risk Factors\n" + _words(80, "beta"),
        headings=("Item 1A. Risk Factors",),
    )
    document = _document(page_one, page_two)
    chunker = TokenAwareChunker(ChunkerConfig(chunk_size_tokens=60, chunk_overlap_tokens=8))

    first = chunker.chunk(document)
    second = chunker.chunk(document)

    assert _fingerprint(first) == _fingerprint(second)
    assert first is not second
    assert len(first) > 1


def test_chunking_is_deterministic_for_tables() -> None:
    table = ExtractedTable(
        page_number=4,
        table_index=0,
        header=("Revenue", "Cost"),
        rows=(("1,234", "890"), ("2,345", "901")),
        caption="Consolidated results",
        units="USD millions",
    )
    page = ExtractedPage(page_number=4, text=_words(40), tables=(table,))
    document = _document(page)
    chunker = TokenAwareChunker()

    assert _fingerprint(chunker.chunk(document)) == _fingerprint(chunker.chunk(document))


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------


def test_table_becomes_exactly_one_chunk() -> None:
    table = ExtractedTable(
        page_number=7,
        table_index=0,
        header=("Revenue", "Cost"),
        rows=(("1,234", "890"),),
    )
    page = ExtractedPage(page_number=7, text="", tables=(table,))
    chunks = TokenAwareChunker().chunk(_document(page))

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == ChunkType.TABLE.value
    assert chunk.chunk_type == "table"
    assert chunk.page_start == 7
    assert chunk.page_end == 7
    assert "Revenue" in chunk.content
    assert "Cost" in chunk.content
    assert "1,234" in chunk.content
    assert "890" in chunk.content
    assert chunk.metadata["has_table"] is True
    assert chunk.metadata["table_index"] == 0
    assert chunk.metadata["column_count"] == 2


def test_table_chunk_keeps_caption_units_and_every_row() -> None:
    table = ExtractedTable(
        page_number=2,
        table_index=1,
        header=("Revenue", "Cost of sales", "Gross profit"),
        rows=(("12,345", "6,789", "5,556"), ("10,000", "5,000", "5,000")),
        caption="Item 7. Financial Statements",
        units="USD millions",
    )
    content = render_table_chunk(table, section_heading="Item 7. Financial Statements")

    assert "Table on page 2" in content
    assert "Section: Item 7. Financial Statements" in content
    assert "Caption: Item 7. Financial Statements" in content
    assert "Units: USD millions" in content
    assert "Columns: Revenue | Cost of sales | Gross profit" in content
    assert "Revenue: 12,345 | Cost of sales: 6,789 | Gross profit: 5,556" in content
    assert "Revenue: 10,000 | Cost of sales: 5,000 | Gross profit: 5,000" in content
    assert "12,345" in content and "5,000" in content


def test_table_with_empty_header_cell_uses_a_positional_label() -> None:
    table = ExtractedTable(
        page_number=1,
        table_index=0,
        header=("Revenue", "", "Gross profit"),
        rows=(("1,234", "890", "344"),),
    )
    content = render_table_chunk(table)

    assert "Columns: Revenue | Column 2 | Gross profit" in content
    assert "Revenue: 1,234 | Column 2: 890 | Gross profit: 344" in content


def test_table_without_header_uses_positional_labels() -> None:
    table = ExtractedTable(page_number=1, table_index=0, rows=(("1,234", "890"),))
    content = render_table_chunk(table)

    assert "Columns: Column 1 | Column 2" in content
    assert "Column 1: 1,234 | Column 2: 890" in content


def test_table_chunk_is_never_merged_and_never_dropped() -> None:
    table = ExtractedTable(page_number=1, table_index=0, header=("A",), rows=(("1",),))
    page = ExtractedPage(page_number=1, text="tiny", tables=(table,))
    chunks = TokenAwareChunker().chunk(_document(page))

    assert [chunk.chunk_type for chunk in chunks] == ["text", "table"]
    table_chunks = [chunk for chunk in chunks if chunk.chunk_type == ChunkType.TABLE.value]
    assert len(table_chunks) == 1
    assert "A: 1" in table_chunks[0].content


def test_table_of_a_page_without_text_is_still_emitted() -> None:
    table = ExtractedTable(page_number=9, table_index=0, header=("A",), rows=(("1",),))
    page = ExtractedPage(page_number=9, text="   ", tables=(table,))
    chunks = TokenAwareChunker().chunk(_document(page))

    assert len(chunks) == 1
    assert chunks[0].chunk_type == ChunkType.TABLE.value
    assert chunks[0].page_start == 9
    assert chunks[0].page_end == 9


def test_tables_are_emitted_after_the_text_of_their_page() -> None:
    table = ExtractedTable(page_number=1, table_index=0, header=("A",), rows=(("1",),))
    page = ExtractedPage(page_number=1, text=_words(30), tables=(table,))
    chunks = TokenAwareChunker().chunk(_document(page))

    assert [chunk.chunk_type for chunk in chunks] == ["text", "table"]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


# ---------------------------------------------------------------------------
# page and section boundaries
# ---------------------------------------------------------------------------


def test_a_chunk_never_spans_two_pages() -> None:
    page_one = ExtractedPage(
        page_number=1,
        text="PAGESENTINEL1 " + _words(200, "alpha"),
    )
    page_two = ExtractedPage(
        page_number=2,
        text="PAGESENTINEL2 " + _words(200, "beta"),
    )
    chunks = TokenAwareChunker().chunk(_document(page_one, page_two))

    assert chunks
    for chunk in chunks:
        assert chunk.page_start == chunk.page_end
        assert not ("PAGESENTINEL1" in chunk.content and "PAGESENTINEL2" in chunk.content)

    first_page_chunks = [chunk for chunk in chunks if chunk.page_start == 1]
    second_page_chunks = [chunk for chunk in chunks if chunk.page_start == 2]
    assert first_page_chunks and second_page_chunks
    assert all("PAGESENTINEL1" in chunk.content for chunk in first_page_chunks)
    assert all("PAGESENTINEL2" in chunk.content for chunk in second_page_chunks)


def test_a_chunk_never_spans_two_sections() -> None:
    text = (
        "Overview of the fiscal year\n"
        + " ".join(f"sentinelA{index}" for index in range(20))
        + "\nRisk Factors\n"
        + " ".join(f"sentinelB{index}" for index in range(20))
        + "\n"
    )
    page = ExtractedPage(
        page_number=1,
        text=text,
        headings=("Overview of the fiscal year", "Risk Factors"),
    )
    config = ChunkerConfig(
        chunk_size_tokens=60,
        chunk_overlap_tokens=10,
        chunk_min_tokens=20,
        chunk_max_tokens=200,
    )
    chunks = TokenAwareChunker(config).chunk(_document(page))

    assert len(chunks) == 2
    for chunk in chunks:
        assert not ("sentinelA" in chunk.content and "sentinelB" in chunk.content)

    assert chunks[0].section_heading == "Overview of the fiscal year"
    assert chunks[1].section_heading == "Risk Factors"
    assert "sentinelA" in chunks[0].content
    assert "sentinelB" in chunks[1].content


def test_text_before_the_first_heading_is_a_leading_section() -> None:
    text = "Some preamble text.\nIntroduction\n" + _words(40, "body")
    page = ExtractedPage(
        page_number=1,
        text=text,
        headings=("Introduction",),
    )
    chunks = TokenAwareChunker().chunk(_document(page))

    assert len(chunks) == 2
    assert chunks[0].section_heading is None
    assert "Some preamble text." in chunks[0].content
    assert chunks[1].section_heading == "Introduction"
    assert "body0" in chunks[1].content


def test_a_page_without_headings_is_a_single_section() -> None:
    page = ExtractedPage(page_number=1, text=_words(40))
    chunks = TokenAwareChunker().chunk(_document(page))

    assert len(chunks) == 1
    assert chunks[0].section_heading is None


def test_headings_that_cannot_be_located_are_ignored() -> None:
    page = ExtractedPage(
        page_number=1,
        text=_words(40),
        headings=("A heading that is not in the text",),
    )
    chunks = TokenAwareChunker().chunk(_document(page))

    assert len(chunks) == 1
    assert chunks[0].section_heading is None


def test_headings_are_matched_case_insensitively() -> None:
    page = ExtractedPage(
        page_number=1,
        text="ITEM 7. FINANCIAL STATEMENTS\n" + _words(30, "body"),
        headings=("Item 7. Financial Statements",),
    )
    chunks = TokenAwareChunker().chunk(_document(page))

    assert len(chunks) == 1
    assert chunks[0].section_heading == "Item 7. Financial Statements"

# ---------------------------------------------------------------------------
# minimum size policy
# ---------------------------------------------------------------------------


def test_tiny_trailing_section_is_merged_into_the_previous_chunk() -> None:
    text = "Overview\n" + _words(60) + "\nRisk Factors\nSee Note 3."
    page = ExtractedPage(
        page_number=1,
        text=text,
        headings=("Overview", "Risk Factors"),
    )
    config = ChunkerConfig(
        chunk_size_tokens=100,
        chunk_overlap_tokens=10,
        chunk_min_tokens=32,
        chunk_max_tokens=512,
    )
    chunks = TokenAwareChunker(config).chunk(_document(page))

    assert len(chunks) == 1
    chunk = chunks[0]
    assert "w0" in chunk.content
    assert "See Note 3." in chunk.content
    assert chunk.token_count == count_tokens(chunk.content)
    assert chunk.section_heading == "Overview"
    assert chunk.metadata["merged_section_heading"] == "Risk Factors"


def test_a_chunk_that_does_not_fit_is_kept_instead_of_merged() -> None:
    config = ChunkerConfig(
        chunk_size_tokens=40,
        chunk_overlap_tokens=5,
        chunk_min_tokens=32,
        chunk_max_tokens=40,
    )
    page = ExtractedPage(page_number=1, text=_words(50))
    chunks = TokenAwareChunker(config).chunk(_document(page))

    assert len(chunks) == 2
    assert chunks[0].token_count == 40
    assert chunks[1].token_count == 15
    assert all(chunk.token_count <= config.chunk_max_tokens for chunk in chunks)


def test_a_merge_never_crosses_a_page_boundary() -> None:
    page_one = ExtractedPage(page_number=1, text=_words(60))
    page_two = ExtractedPage(page_number=2, text="tiny tail")
    chunks = TokenAwareChunker().chunk(_document(page_one, page_two))

    assert len(chunks) == 2
    assert chunks[0].page_start == 1
    assert chunks[1].page_start == 2
    assert chunks[1].content == "tiny tail"


# ---------------------------------------------------------------------------
# metadata and ordering
# ---------------------------------------------------------------------------


def test_metadata_is_json_serializable_and_flat() -> None:
    table = ExtractedTable(page_number=2, table_index=3, header=("A",), rows=(("1",),))
    page = ExtractedPage(
        page_number=2,
        text="Item 1. Business\n" + _words(40),
        headings=("Item 1. Business",),
        tables=(table,),
    )
    chunks = TokenAwareChunker().chunk(_document(page))

    assert chunks
    for chunk in chunks:
        metadata = dict(chunk.metadata)
        assert set(metadata) >= {
            "source",
            "page_number",
            "section_heading",
            "has_table",
        }
        assert metadata["source"] == "pdf_text"
        assert metadata["page_number"] == 2
        assert isinstance(metadata["has_table"], bool)
        assert json.loads(json.dumps(metadata)) == metadata
        for value in metadata.values():
            assert value is None or isinstance(value, (str, int, float, bool))


def test_table_metadata_carries_the_table_index_and_the_column_count() -> None:
    table = ExtractedTable(
        page_number=5,
        table_index=2,
        header=("A", "B", "C"),
        rows=(("1", "2", "3"),),
    )
    page = ExtractedPage(page_number=5, text="", tables=(table,))
    chunks = TokenAwareChunker().chunk(_document(page))

    assert len(chunks) == 1
    metadata = dict(chunks[0].metadata)
    assert metadata["table_index"] == 2
    assert metadata["column_count"] == 3
    assert metadata["has_table"] is True


def test_chunk_index_is_a_global_counter_in_document_order() -> None:
    config = ChunkerConfig(
        chunk_size_tokens=40,
        chunk_overlap_tokens=5,
        chunk_min_tokens=10,
        chunk_max_tokens=80,
    )
    table = ExtractedTable(page_number=2, table_index=0, header=("A",), rows=(("1",),))
    page_one = ExtractedPage(page_number=1, text=_words(60))
    page_two = ExtractedPage(page_number=2, text=_words(60), tables=(table,))
    chunks = TokenAwareChunker(config).chunk(_document(page_one, page_two))

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert [chunk.page_start for chunk in chunks] == [1, 1, 2, 2, 2]
    assert [chunk.chunk_type for chunk in chunks] == [
        "text",
        "text",
        "text",
        "text",
        "table",
    ]