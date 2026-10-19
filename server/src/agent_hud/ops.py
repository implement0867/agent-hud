"""Agent write operations: the input of the `write` tool."""

from enum import StrEnum
from functools import cache
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, StringConstraints, TypeAdapter

from agent_hud.primitives.base import BoxKind, ElementId


class OpKind(StrEnum):
    PUT = "put"
    SET = "set"
    INSERT = "insert"
    REMOVE = "remove"
    REPLY = "reply"
    LINK = "link"
    CLEAR = "clear"


type Label = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}(\.[A-Za-z0-9_]+){0,2}$")]


class OpBase(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)


class PutOp(OpBase):
    op: Literal[OpKind.PUT] = Field(description="Create or replace an element", examples=[OpKind.PUT])
    id: ElementId = Field(description="Element id", examples=["plan"])
    md: str = Field(description="Markdown body", examples=["## Plan\n1. Add cache\n2. Load test"])
    title: str | None = Field(default=None, description="Card title; default is a leading heading", examples=["Plan"])
    kind: BoxKind | None = Field(default=None, description="Force a kind; default infers", examples=[BoxKind.TEXT])


class SetOp(OpBase):
    op: Literal[OpKind.SET] = Field(description="Replace the text of a part", examples=[OpKind.SET])
    at: Label = Field(description="Label of an item, row, cell or text element", examples=["plan.2"])
    value: str = Field(description="New text; a row takes `a | b`; a check cell takes x or empty", examples=["x"])


class InsertOp(OpBase):
    op: Literal[OpKind.INSERT] = Field(description="Insert an item or row", examples=[OpKind.INSERT])
    at: Label = Field(description="`plan.3` inserts before item 3; `plan` appends", examples=["plan.3"])
    value: str = Field(description="Item text, or a row as `a | b`", examples=["Write docs"])


class RemoveOp(OpBase):
    op: Literal[OpKind.REMOVE] = Field(description="Remove an element, item or row", examples=[OpKind.REMOVE])
    at: Label = Field(description="`plan` removes the element; `plan.3` one item", examples=["opts.r2"])


class ReplyOp(OpBase):
    op: Literal[OpKind.REPLY] = Field(description="Comment on a part, such as an answer", examples=[OpKind.REPLY])
    at: Label = Field(description="Label of the part", examples=["plan.2"])
    text: str = Field(min_length=1, description="Comment", examples=["Reworded; see item 2"])


class LinkOp(OpBase):
    op: Literal[OpKind.LINK] = Field(description="Draw an arrow between parts", examples=[OpKind.LINK])
    src: Label = Field(description="Arrow tail", examples=["plan.6"])
    dst: Label = Field(description="Arrow head", examples=["plan.1"])
    text: str | None = Field(default=None, description="Arrow text", examples=["depends on"])
    id: ElementId | None = Field(default=None, description="Arrow id; default generated", examples=["dep1"])


class ClearOp(OpBase):
    op: Literal[OpKind.CLEAR] = Field(description="Remove every element", examples=[OpKind.CLEAR])


type Op = Annotated[PutOp | SetOp | InsertOp | RemoveOp | ReplyOp | LinkOp | ClearOp, Discriminator("op")]


@cache
def op_list() -> TypeAdapter[list[Op]]:
    return TypeAdapter(list[Op])
