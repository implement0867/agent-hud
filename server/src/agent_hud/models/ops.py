from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Discriminator, Field

from agent_hud.models.base import Model
from agent_hud.models.card import CardId


class OpKind(StrEnum):
    put = "put"
    remove = "remove"


class PutOp(Model):
    op: Literal[OpKind.put]
    id: CardId = Field(description="Card id, such as plan")
    md: str = Field(min_length=1, description="Markdown shown on the card")


class RemoveOp(Model):
    op: Literal[OpKind.remove]
    id: CardId = Field(description="Card id")


type Op = Annotated[PutOp | RemoveOp, Discriminator("op")]
