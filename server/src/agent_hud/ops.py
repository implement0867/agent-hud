from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field

from agent_hud.card import CardId


class OpKind(StrEnum):
    put = "put"
    remove = "remove"


class PutOp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    op: Literal[OpKind.put]
    id: CardId = Field(description="Card id, such as plan")
    md: str = Field(min_length=1, description="Markdown shown on the card")


class RemoveOp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    op: Literal[OpKind.remove]
    id: CardId = Field(description="Card id")


type Op = Annotated[PutOp | RemoveOp, Discriminator("op")]
