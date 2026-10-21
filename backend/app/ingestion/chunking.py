r"""Token-aware, deterministic chunking of extracted documents.

This module turns the immutable extraction contracts of
:mod:`app.ingestion.contracts` into the list of :class:`~app.ingestion.contracts.Chunk`
objects that the embedding and vector-store layers consume.

Design rules
------------
* **Deterministic.**  The same document and the same configuration always
  produce byte-identical chunks: same order, same ``chunk_index``, same
  content, same metadata.  There is no randomness and no reliance on the
  iteration order of sets or dictionaries.
* **Page boundaries are sacred.**  A chunk never spans two pages, so
  ``page_start == page_end == page_number`` always holds.
* **Section boundaries are sacred.**  A chunk never mixes the content of two
  sections, and every chunk carries the ``section_heading`` of the section it
  came from (``None`` for the leading, un-headed part of a page).
* **Tables are never shredded.**  Every :class:`~app.ingestion.contracts.ExtractedTable`
  becomes exactly one ``table`` chunk whose rendered content preserves the
  column header, every row, the caption and the units.
* **Nothing is dropped.**  A text chunk that is shorter than
  ``chunk_min_tokens`` is merged into the preceding chunk of the same page
  when the merged result still fits into ``chunk_max_tokens``; otherwise it
  is kept as-is.

Token model
-----------
:func:`count_tokens` counts the matches of ``re.findall(r"\w+|[^\w\s]", text)``:
a token is either a maximal run of word characters or a single non-word,
non-whitespace character.  This is an *approximation* of the token count of a
real language model - it is deliberately deterministic, dependency free and
identical on every machine, which is what the reproducibility guarantees of
this module require.  The embedding model applies its own tokenizer later, so
the numbers here only have to be a stable, monotonic proxy for text size.

Algorithm
---------
For every page of the document, in document order:

1. The page text is split into sections at the page's headings.  Each heading
   is located case-insensitively (``str.find`` on a lower-cased copy of the
   text, with the index mapped back to the original string); the text before
   the first heading becomes a leading section with ``section_heading=None``.
   Headings that cannot be located are ignored.
2. Every section is split into token windows of at most
   ``chunk_size_tokens`` tokens that overlap by ``chunk_overlap_tokens``
   tokens, so that no sentence is cut off without context.
3. Windows that are shorter than ``chunk_min_tokens`` are merged into the
   previous chunk of the same page when the result still fits into
   ``chunk_max_tokens``.
4. The resulting text chunks are emitted first, followed by the table chunks
   of the same page.  ``chunk_index`` is a global, 0-based counter over the
   whole document.

Documented exception
--------------------
The rule "a chunk never spans two sections" has exactly one documented
exception: the minimum-size merge of step 3 may absorb a very short trailing
section into the preceding chunk of the same page (a two-line section would
otherwise become a poor retrieval unit).  The merged chunk keeps the
``section_heading`` of the preceding chunk - the one that carries the bulk of
the text - and records the absorbed heading in
``metadata["merged_section_heading"]``.  Table chunks are never merged and
never dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from typing import Protocol, runtime_checkable

from app.core.enums import ChunkType
from app.ingestion.contracts import (
    Chunk,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
)

__all__ = [
    "Chunker",
    "ChunkerConfig",
    "TokenAwareChunker",
    "count_tokens",
    "render_table_chunk",
]

#: The regular expression that defines what a token is.  ``count_tokens`` is
#: the number of its matches; the very same pattern is used to locate the
#: token boundaries inside a text window.
_TOKEN_PATTERN = r"\w+|[^\w\s]"
_TOKEN_RE = re.compile(_TOKEN_PATTERN)


def count_tokens(text: str) -> int:
    r"""Return the number of tokens in *text*.

    A token is a maximal run of word characters (``\w+``) or a single
    character that is neither a word character nor whitespace
    (``[^\w\s]``).  The count is therefore the number of matches of
    ``re.findall(r"\w+|[^\w\s]", text)``.

    This is an **approximation** of the token count of a real language
    model: it is deterministic, dependency free and produces the same number
    on every machine and every run, which is what the reproducibility
    guarantees of this module need.  The embedding model applies its own
    tokenizer downstream.

    Parameters
    ----------
    text:
        The text to measure.  An empty string (or ``None``) counts as zero
        tokens.

    Returns
    -------
    int
        The number of tokens.
    """
    if not text:
        return 0
    return len(re.findall(_TOKEN_PATTERN, text))


@dataclass(frozen=True, slots=True)
class ChunkerConfig:
    """Configuration of the token aware chunker.

    The defaults mirror the ``CHUNK_*`` settings of
    :class:`app.core.config.Settings`.
    """

    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    chunk_min_tokens: int = 32
    chunk_max_tokens: int = 1024

    def __post_init__(self) -> None:
        """Validate the combination of the four token budgets.

        Raises
        ------
        ValueError
            If the size is not positive, if the overlap is negative or not
            smaller than the size, if the minimum is negative or larger than
            the size, or if the maximum is smaller than the size.
        """
        if self.chunk_size_tokens <= 0:
            raise ValueError("chunk_size_tokens must be positive")
        if self.chunk_overlap_tokens < 0:
            raise ValueError("chunk_overlap_tokens must not be negative")
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError(
                "chunk_overlap_tokens must be smaller than chunk_size_tokens"
            )
        if self.chunk_min_tokens < 0:
            raise ValueError("chunk_min_tokens must not be negative")
        if self.chunk_min_tokens > self.chunk_size_tokens:
            raise ValueError("chunk_min_tokens must not exceed chunk_size_tokens")
        if self.chunk_max_tokens < self.chunk_size_tokens:
            raise ValueError("chunk_max_tokens must not be smaller than chunk_size_tokens")

@runtime_checkable
class Chunker(Protocol):
    """Structural protocol of everything that can turn a document into chunks."""

    def chunk(self, document: ExtractedDocument) -> list[Chunk]:
        """Return the chunks of *document*."""
        ...


def _column_count(table: ExtractedTable) -> int:
    """Return the number of columns of *table*."""
    row_widths = [len(row) for row in table.rows]
    return max([len(table.header), *row_widths], default=0)


def render_table_chunk(table: ExtractedTable, *, section_heading: str | None = None) -> str:
    """Render *table* as the plain text content of a single chunk.

    The rendering is deliberately verbose: a reader (human or retrieval
    model) has to be able to map every value to its label without seeing the
    original page.  The column header is used as the label of every cell; an
    empty header cell falls back to the positional label ``Column <n>``
    (1-based).  The cell values themselves are kept **verbatim** - numbers
    are never reformatted.

    Parameters
    ----------
    table:
        The table to render.
    section_heading:
        Optional heading of the section the table belongs to.  It is rendered
        as a ``Section:`` line when given.

    Returns
    -------
    str
        The rendered text of the table.
    """
    lines: list[str] = [f"Table on page {table.page_number}"]
    if section_heading:
        lines.append(f"Section: {section_heading}")
    if table.caption:
        lines.append(f"Caption: {table.caption}")
    if table.units:
        lines.append(f"Units: {table.units}")

    column_count = _column_count(table)
    if column_count:
        labels = [
            table.header[index]
            if index < len(table.header) and table.header[index].strip()
            else f"Column {index + 1}"
            for index in range(column_count)
        ]
        lines.append("Columns: " + " | ".join(labels))
        for row in table.rows:
            cells = [
                f"{labels[index] if index < len(labels) else f'Column {index + 1}'}: {value}"
                for index, value in enumerate(row)
            ]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class _Section:
    """A slice of a page that belongs to a single section."""

    heading: str | None
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _PendingChunk:
    """A text chunk before it is merged and turned into a :class:`Chunk`."""

    content: str
    tokens: int
    heading: str | None
    section_index: int
    merged: bool = False
    merged_heading: str | None = None


def _lowered_with_index(text: str) -> tuple[str, list[int]]:
    """Return *text* lower-cased plus a map from lower-cased to original index.

    The map is needed because lower-casing a character can change its length
    (for example ``"\u0130".lower()`` is two characters long), so an index
    into the lower-cased string is not necessarily an index into the original
    one.
    """
    lowered: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(text):
        for lowered_char in char.lower():
            lowered.append(lowered_char)
            index_map.append(index)
    return "".join(lowered), index_map


def _find_case_insensitive(text: str, needle: str) -> int | None:
    """Return the index of *needle* inside *text*, ignoring case.

    ``None`` is returned when the needle cannot be located.
    """
    if not needle:
        return None
    lowered, index_map = _lowered_with_index(text)
    position = lowered.find(needle.lower())
    if position < 0:
        return None
    return index_map[position]


def _split_page_sections(page: ExtractedPage) -> list[_Section]:
    """Split the text of *page* into sections at the page's headings."""
    text = page.text or ""
    if not text.strip():
        return []

    located: list[tuple[int, str]] = []
    seen_positions: set[int] = set()
    for heading in page.headings:
        if not (heading or "").strip():
            continue
        position = _find_case_insensitive(text, heading.strip())
        if position is None or position in seen_positions:
            continue
        seen_positions.add(position)
        located.append((position, heading))
    located.sort(key=lambda item: item[0])

    sections: list[_Section] = []
    if located:
        first_position = located[0][0]
        if first_position > 0:
            leading = text[:first_position]
            if leading.strip():
                sections.append(_Section(None, leading, 0, first_position))
        for index, (start, heading) in enumerate(located):
            end = located[index + 1][0] if index + 1 < len(located) else len(text)
            body = text[start:end]
            if body.strip():
                sections.append(_Section(heading, body, start, end))
    else:
        sections.append(_Section(None, text, 0, len(text)))
    return sections


def _iter_windows(text: str, size: int, overlap: int) -> list[tuple[str, int]]:
    """Split *text* into overlapping token windows.

    Returns
    -------
    list[tuple[str, int]]
        One ``(content, token_count)`` pair per window.  Every window holds
        at most *size* tokens and consecutive windows share *overlap* tokens.
    """
    spans = [(match.start(), match.end()) for match in _TOKEN_RE.finditer(text)]
    if not spans:
        return []

    windows: list[tuple[str, int]] = []
    total = len(spans)
    start = 0
    while True:
        end = min(start + size, total)
        content = text[spans[start][0] : spans[end - 1][1]].strip()
        if content:
            windows.append((content, end - start))
        if end >= total:
            break
        start = end - overlap
    return windows


def _merge_short_chunks(
    items: list[_PendingChunk], min_tokens: int, max_tokens: int
) -> list[_PendingChunk]:
    """Merge chunks below *min_tokens* into their predecessor.

    A chunk is only merged when the merged content still fits into
    *max_tokens*; otherwise it is kept as-is so that no content is lost.
    """
    merged_items: list[_PendingChunk] = []
    for item in items:
        if item.tokens < min_tokens and merged_items:
            previous = merged_items[-1]
            content = f"{previous.content}\n{item.content}"
            tokens = count_tokens(content)
            if tokens <= max_tokens:
                merged_items[-1] = _PendingChunk(
                    content=content,
                    tokens=tokens,
                    heading=previous.heading,
                    section_index=previous.section_index,
                    merged=True,
                    merged_heading=item.heading,
                )
                continue
        merged_items.append(item)
    return merged_items


def _table_section_heading(
    page: ExtractedPage, sections: list[_Section], table: ExtractedTable
) -> str | None:
    """Return the heading of the section the table of *page* belongs to.

    The caption of the table is looked up in the page text to find the
    section it sits in.  When the caption cannot be located the first
    heading of the page is used, and ``None`` when the page has no headings.
    """
    caption = (table.caption or "").strip()
    if caption and page.text:
        position = _find_case_insensitive(page.text, caption)
        if position is not None:
            for section in sections:
                if section.start <= position < section.end:
                    return section.heading
    for heading in page.headings:
        if (heading or "").strip():
            return heading
    return None

class TokenAwareChunker:
    """Chunk documents into token bounded, page and section aware chunks.

    The chunker is stateless and deterministic: it can be reused for any
    number of documents and the same input always produces the same output.
    """

    def __init__(self, config: ChunkerConfig | None = None, **overrides: int) -> None:
        """Create a chunker.

        Parameters
        ----------
        config:
            Optional configuration.  When omitted the defaults of
            :class:`ChunkerConfig` are used.
        **overrides:
            Individual configuration values that override *config*, for
            example ``TokenAwareChunker(chunk_size_tokens=256)``.

        Raises
        ------
        TypeError
            If an unknown configuration option is passed.
        ValueError
            If the resulting configuration is invalid.
        """
        self.config = self._resolve_config(config, overrides)

    @staticmethod
    def _resolve_config(
        config: ChunkerConfig | None, overrides: dict[str, int]
    ) -> ChunkerConfig:
        """Return the effective configuration for *config* and *overrides*."""
        base = config if config is not None else ChunkerConfig()
        if not overrides:
            return base
        names = tuple(field.name for field in fields(ChunkerConfig))
        unknown = sorted(name for name in overrides if name not in names)
        if unknown:
            raise TypeError(f"Unknown chunker option(s): {', '.join(unknown)}")
        values = {name: getattr(base, name) for name in names}
        values.update(overrides)
        return ChunkerConfig(**values)

    def chunk(self, document: ExtractedDocument) -> list[Chunk]:
        """Return the chunks of *document* in document order.

        Parameters
        ----------
        document:
            The extracted document to split.

        Returns
        -------
        list[Chunk]
            The chunks of the document.  The list is empty for an empty
            document.
        """
        config = self.config
        chunks: list[Chunk] = []
        chunk_index = 0

        for page in document.pages:
            sections = _split_page_sections(page)
            pending: list[_PendingChunk] = []
            for section_index, section in enumerate(sections):
                for content, tokens in _iter_windows(
                    section.text,
                    config.chunk_size_tokens,
                    config.chunk_overlap_tokens,
                ):
                    pending.append(
                        _PendingChunk(
                            content=content,
                            tokens=tokens,
                            heading=section.heading,
                            section_index=section_index,
                        )
                    )

            for item in _merge_short_chunks(
                pending, config.chunk_min_tokens, config.chunk_max_tokens
            ):
                token_count = count_tokens(item.content)
                assert token_count <= config.chunk_max_tokens, (
                    "text chunk exceeds chunk_max_tokens: "
                    f"{token_count} > {config.chunk_max_tokens}"
                )
                metadata: dict[str, object] = {
                    "source": page.extraction_method,
                    "page_number": int(page.page_number),
                    "section_heading": item.heading,
                    "has_table": False,
                    "page_has_table": bool(page.tables),
                    "section_index": int(item.section_index),
                }
                if item.merged:
                    metadata["merged_section_heading"] = item.merged_heading
                chunks.append(
                    Chunk(
                        chunk_index=chunk_index,
                        content=item.content,
                        chunk_type=ChunkType.TEXT.value,
                        page_start=int(page.page_number),
                        page_end=int(page.page_number),
                        section_heading=item.heading,
                        token_count=token_count,
                        metadata=metadata,
                    )
                )
                chunk_index += 1

            for table in page.tables:
                heading = _table_section_heading(page, sections, table)
                content = render_table_chunk(table, section_heading=heading)
                metadata = {
                    "source": page.extraction_method,
                    "page_number": int(page.page_number),
                    "section_heading": heading,
                    "has_table": True,
                    "page_has_table": bool(page.tables),
                    "table_index": int(table.table_index),
                    "column_count": int(_column_count(table)),
                }
                chunks.append(
                    Chunk(
                        chunk_index=chunk_index,
                        content=content,
                        chunk_type=ChunkType.TABLE.value,
                        page_start=int(page.page_number),
                        page_end=int(page.page_number),
                        section_heading=heading,
                        token_count=count_tokens(content),
                        metadata=metadata,
                    )
                )
                chunk_index += 1

        return chunks