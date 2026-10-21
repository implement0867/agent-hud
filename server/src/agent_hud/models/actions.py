from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Discriminator, Field, StringConstraints

from agent_hud.models.base import Model

type TCardId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]
type TRef = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}(/[1-9][0-9]*)?$")]
type TActionId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
type TMessage = Annotated[str, StringConstraints(pattern=r"\S")]


class Author(StrEnum):
    agent = "agent"
    user = "user"


class Reaction(StrEnum):
    approve = "approve"
    reject = "reject"
    question = "question"


class ActionKind(StrEnum):
    put = "put"
    remove = "remove"
    react = "react"
    unreact = "unreact"
    comment = "comment"
    say = "say"


class Put(Model):
    kind: Literal[ActionKind.put]
    id: TCardId = Field(description="Card id, such as plan")
    md: str = Field(min_length=1, description="Markdown shown on the card")


class Remove(Model):
    kind: Literal[ActionKind.remove]
    id: TCardId


class React(Model):
    kind: Literal[ActionKind.react]
    ref: TRef = Field(
        description="A card id, or a card id and the number of a list item or table row in it, such as plan/2"
    )
    reaction: Reaction


class Unreact(Model):
    kind: Literal[ActionKind.unreact]
    ref: TRef


class Comment(Model):
    kind: Literal[ActionKind.comment]
    ref: TRef
    text: TMessage


class Say(Model):
    kind: Literal[ActionKind.say]
    text: TMessage


type TBody = Annotated[Put | Remove | React | Unreact | Comment | Say, Discriminator("kind")]


class Action(Model):
    id: TActionId
    author: Author
    body: TBody
