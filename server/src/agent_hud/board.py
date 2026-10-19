from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Discriminator, Field, StringConstraints

type CardId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]


class OpError(ValueError):
    pass


class FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class Card(FrozenModel):
    md: str = Field(min_length=1)


class OpKind(StrEnum):
    PUT = "put"
    REMOVE = "remove"


class PutOp(FrozenModel):
    op: Literal[OpKind.PUT]
    id: CardId = Field(description="Card id, such as plan")
    md: str = Field(min_length=1, description="Markdown shown on the card")


class RemoveOp(FrozenModel):
    op: Literal[OpKind.REMOVE]
    id: CardId = Field(description="Card id")


type Op = Annotated[PutOp | RemoveOp, Discriminator("op")]


class Board(FrozenModel):
    cards: dict[CardId, Card] = Field(default_factory=dict)

    def apply(self, ops: list[Op]) -> Self:
        """A new board with the ops applied in order, or OpError and no change."""
        cards = dict(self.cards)
        for n, op in enumerate(ops, start=1):
            match op:
                case PutOp(id=card_id, md=md):
                    cards[card_id] = Card(md=md)
                case RemoveOp(id=card_id) if card_id in cards:
                    del cards[card_id]
                case RemoveOp(id=card_id):
                    raise OpError(f"op {n} ({op.op}): no card '{card_id}'. Nothing was applied.")
        return self.model_copy(update={"cards": cards})

    def render(self) -> str:
        if not self.cards:
            return "no cards"
        return "\n\n".join(f"{card_id}:\n{card.md}" for card_id, card in self.cards.items())
