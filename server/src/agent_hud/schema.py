from typing import Any

from fastmcp.utilities.json_schema import dereference_refs


def find_shared_keywords(schemas: list[dict[str, Any]]) -> dict[str, Any]:
    """The keywords that all the schemas give the same value."""
    first, *rest = schemas
    return {key: value for key, value in first.items() if all(key in other and other[key] == value for other in rest)}


def merge_variants(variants: list[dict[str, Any]]) -> dict[str, Any]:
    """
    One object with the fields of all the variants, so that it accepts each value that one of the variants accepts.
    A field keeps the keywords that the variants with that field agree on.
    """
    names = dict.fromkeys(name for variant in variants for name in variant["properties"] if name != "kind")
    fields = {
        name: find_shared_keywords(
            [variant["properties"][name] for variant in variants if name in variant["properties"]]
        )
        for name in names
    }
    kinds = [variant["properties"]["kind"]["const"] for variant in variants]
    return {"type": "object", "properties": {"kind": {"enum": kinds}, **fields}, "required": ["kind"]}


def make_variant_signature(variant: dict[str, Any]) -> str:
    """The kind of the variant and its fields, such as put {id, md}, with ? after an optional field."""
    required = variant.get("required", [])
    names = [name if name in required else f"{name}?" for name in variant["properties"] if name != "kind"]
    return variant["properties"]["kind"]["const"] + (f" {{{', '.join(names)}}}" if names else "")


def compact_actions_schema(parameters: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    The parameters of a tool that takes a list of actions, with one object for all kinds of action in place of a oneOf
    of an object for each kind, and the signature of each kind for the tool's description.
    The listed schema then costs the agent fewer tokens. The tool still validates each action against its own model.
    """
    inline = dereference_refs(parameters)
    actions = inline["properties"]["actions"]
    variants = actions["items"]["oneOf"]
    properties = inline["properties"] | {"actions": actions | {"items": merge_variants(variants)}}
    return inline | {"properties": properties}, ", ".join(make_variant_signature(variant) for variant in variants)
