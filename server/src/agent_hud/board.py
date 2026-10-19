from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from agent_hud.card import Card, CardId
from agent_hud.ops import Op, PutOp, RemoveOp


class Board(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cards: dict[CardId, Card] = Field(default_factory=dict)

    def apply(self, ops: list[Op]) -> Self:
        """A new board with the ops applied in order. A failing op raises ValueError, and no op applies."""
        cards = dict(self.cards)
        for n, op in enumerate(ops, start=1):
            match op:
                case PutOp(id=card_id, md=md):
                    cards[card_id] = Card(md=md)
                case RemoveOp(id=card_id) if card_id in cards:
                    del cards[card_id]
                case RemoveOp(id=card_id):
                    raise ValueError(f"op {n} ({op.op}): no card '{card_id}'. Nothing was applied.")
        return self.model_copy(update={"cards": cards})

    def render(self) -> str:
        return "\n\n".join(f"{card_id}:\n{card.md}" for card_id, card in self.cards.items())
