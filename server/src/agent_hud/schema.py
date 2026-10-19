from typing import Any

type Json = dict[str, Any] | list[Any] | str | float | bool | None


def compact(node: Json) -> Json:
    """Drop titles and regex patterns from a tool input schema. Pydantic still validates the arguments."""
    match node:
        case dict():
            return {key: compact(value) for key, value in node.items() if key not in {"title", "pattern"}}
        case list():
            return [compact(item) for item in node]
        case _:
            return node
