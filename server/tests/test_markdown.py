import pytest

from agent_hud.markdown import (
    ColumnType,
    HeaderSpec,
    ListContent,
    MarkdownError,
    TableContent,
    TextContent,
    parse,
    parse_header,
    split_row,
)


@pytest.mark.parametrize(
    ("md", "title", "content"),
    [
        ("Hello **there**", None, TextContent()),
        ("# Why\nBecause.", "Why", TextContent()),
        ("1. a\n2. b", None, ListContent(ordered=True, items=["a", "b"])),
        ("- a\n- b", None, ListContent(ordered=False, items=["a", "b"])),
        ("## Plan\n\n1. a\n2. b", "Plan", ListContent(ordered=True, items=["a", "b"])),
        ("1. a\n   - sub\n2. b", None, ListContent(ordered=True, items=["a\n- sub", "b"])),
        ("1. a\n\n2. b", None, ListContent(ordered=True, items=["a", "b"])),
        ("1. a\nlazy line", None, ListContent(ordered=True, items=["a\nlazy line"])),
        ("1. a\n\nplain line", None, TextContent()),
        ("intro\n1. a", None, TextContent()),
        (
            "| A | B |\n|---|---|\n| 1 | 2 |",
            None,
            TableContent(headers=[HeaderSpec("A"), HeaderSpec("B")], rows=[["1", "2"]]),
        ),
        (
            "| A | B |\n|:--|--:|\n| 1 |",
            None,
            TableContent(headers=[HeaderSpec("A"), HeaderSpec("B")], rows=[["1", ""]]),
        ),
        ("", None, TextContent()),
    ],
    ids=[
        "text",
        "heading-text",
        "ordered",
        "bullets",
        "heading-list",
        "sub-points",
        "loose-list",
        "lazy-continuation",
        "list-then-text",
        "text-then-list",
        "table",
        "short-row",
        "empty",
    ],
)
def test_parse_infers_content(md: str, title: str | None, content: object) -> None:
    parsed = parse(md)
    assert parsed.title == title, f"title of {md!r}"
    assert parsed.content == content, f"content of {md!r}"


@pytest.mark.parametrize(
    ("md", "heading_is_title", "title", "body"),
    [
        ("# Why\nBecause.", True, "Why", "Because."),
        ("Why\n===\nBecause.", True, "Why", "Because."),
        ("# Why\nBecause.", False, None, "# Why\nBecause."),
        ("# Only a heading", True, None, "# Only a heading"),
    ],
    ids=["atx", "setext", "title-given", "heading-alone"],
)
def test_parse_splits_title_from_body(md: str, *, heading_is_title: bool, title: str | None, body: str) -> None:
    parsed = parse(md, heading_is_title=heading_is_title)
    assert (parsed.title, parsed.body) == (title, body)


@pytest.mark.parametrize(
    ("cell", "spec"),
    [
        ("Name", HeaderSpec("Name")),
        ("Pick {check}", HeaderSpec("Pick", ColumnType.CHECK)),
        ("Notes {TEXT}", HeaderSpec("Notes", ColumnType.TEXT)),
        ("Cost {number}", HeaderSpec("Cost", ColumnType.NUMBER)),
        ("Effort {low, med,high}", HeaderSpec("Effort", ColumnType.SELECT, ["low", "med", "high"])),
    ],
)
def test_parse_header(cell: str, spec: HeaderSpec) -> None:
    assert parse_header(cell) == spec


@pytest.mark.parametrize("cell", ["X {bogus}", "X {}", "X {only}"])
def test_parse_header_rejects_unknown_type(cell: str) -> None:
    with pytest.raises(MarkdownError):
        parse_header(cell)


@pytest.mark.parametrize(
    ("line", "cells"),
    [
        ("| a | b |", ["a", "b"]),
        ("a | b", ["a", "b"]),
        (r"| a \| b | c |", ["a | b", "c"]),
        ("| a |  |", ["a", ""]),
        ("| a | | b |", ["a", "", "b"]),
    ],
)
def test_split_row(line: str, cells: list[str]) -> None:
    assert split_row(line) == cells


def test_table_row_wider_than_header_is_an_error() -> None:
    with pytest.raises(MarkdownError, match="row 1"):
        parse("| A |\n|---|\n| 1 | 2 |")
