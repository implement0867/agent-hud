from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints

from agent_hud.models.base import Model

type TCardId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]


class Reaction(StrEnum):
    approve = "approve"
    reject = "reject"
    question = "question"


class Card(Model):
    md: str = Field(min_length=1)
    reaction: Reaction | None = None
    comments: list[str] = Field(default_factory=list)
