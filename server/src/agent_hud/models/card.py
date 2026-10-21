from enum import StrEnum
from typing import Annotated, Self
from uuid import uuid4

from pydantic import Field, StringConstraints

from agent_hud.markdown import numbered_items
from agent_hud.models.base import Model

type TCardId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]


class Reaction(StrEnum):
    approve = "approve"
    reject = "reject"
    question = "question"


class Comment(Model):
    id: str = Field(default_factory=lambda: uuid4().hex)
    text: str


class Item(Model):
    id: str = Field(default_factory=lambda: uuid4().hex)
    md: str = Field(min_length=1)


class Card(Model):
    md: str = Field(min_length=1)
    items: list[Item] = Field(default_factory=list)
    reaction: Reaction | None = None
    comments: list[Comment] = Field(default_factory=list)

    @classmethod
    def from_md(cls, md: str) -> Self:
        """A new card of the markdown, with its items if the markdown is one numbered list."""
        return cls(md=md, items=[Item(md=item) for item in numbered_items(md)])
