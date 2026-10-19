from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, StringConstraints

from agent_hud.primitives import BoxKind
from agent_hud.primitives.base import ElementId


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
    op: Literal[OpKind.PUT] = Field(description="Create or replace an element")
    id: ElementId = Field(description="Element id")
    md: str = Field(description="Markdown body")
    title: str | None = Field(default=None, description="Card title; default is a leading heading")
    kind: BoxKind | None = Field(default=None, description="Force a kind; default infers")


class SetOp(OpBase):
    op: Literal[OpKind.SET] = Field(description="Replace the text of a part")
    at: Label = Field(description="Label of an item, row, cell or text element")
    value: str = Field(description="New text; a row takes `a | b`; a check cell takes x or empty")


class InsertOp(OpBase):
    op: Literal[OpKind.INSERT] = Field(description="Insert an item or row")
    at: Label = Field(description="`plan.3` inserts before item 3; `plan` appends")
    value: str = Field(description="Item text, or a row as `a | b`")


class RemoveOp(OpBase):
    op: Literal[OpKind.REMOVE] = Field(description="Remove an element, item or row")
    at: Label = Field(description="`plan` removes the element; `plan.3` one item")


class ReplyOp(OpBase):
    op: Literal[OpKind.REPLY] = Field(description="Comment on a part, such as an answer")
    at: Label = Field(description="Label of the part")
    text: str = Field(min_length=1, description="Comment")


class LinkOp(OpBase):
    op: Literal[OpKind.LINK] = Field(description="Draw an arrow between parts")
    src: Label = Field(description="Arrow tail")
    dst: Label = Field(description="Arrow head")
    text: str | None = Field(default=None, description="Arrow text")
    id: ElementId | None = Field(default=None, description="Arrow id; default generated")


class ClearOp(OpBase):
    op: Literal[OpKind.CLEAR] = Field(description="Remove every element")


type Op = Annotated[PutOp | SetOp | InsertOp | RemoveOp | ReplyOp | LinkOp | ClearOp, Discriminator("op")]
