"""Trim tool input schemas: the model reads them on every turn."""

from typing import Any

type Json = dict[str, Any] | list[Any] | str | float | bool | None


def compact(node: Json, *, inside_any_of: bool = False) -> Json:
    """Drop examples, titles and regex patterns, plus descriptions repeated on union branches.

    Arguments are still validated by Pydantic on the server, so nothing here loosens checking.
    """
    match node:
        case dict():
            return {
                key: compact(value, inside_any_of=key == "anyOf")
                for key, value in node.items()
                if key not in {"examples", "title", "pattern"} and not (inside_any_of and key == "description")
            }
        case list():
            return [compact(item, inside_any_of=inside_any_of) for item in node]
        case _:
            return node


def compact_object(schema: dict[str, Any]) -> dict[str, Any]:
    match compact(schema):
        case dict() as trimmed:
            return trimmed
        case _:
            raise TypeError("schema must stay an object")
