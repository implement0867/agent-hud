from typing import assert_never

from pydantic import ConfigDict, Field

from agent_hud.models.base import Model
from agent_hud.models.card import Card, Comment, Reaction, TCardId, TItemNumber
from agent_hud.models.ops import PutOp, RemoveOp, TOp


class Board(Model):
    model_config = ConfigDict(frozen=False)

    cards: dict[TCardId, Card] = Field(default_factory=dict)

    def apply(self, ops: list[TOp]) -> None:
        """Apply the ops in order. A failing op raises ValueError, and no op applies."""
        cards = dict(self.cards)
        for n, op in enumerate(ops, start=1):
            match op:
                case PutOp(id=card_id, md=md):
                    cards[card_id] = Card.from_md(md)
                case RemoveOp(id=card_id) if card_id in cards:
                    del cards[card_id]
                case RemoveOp(id=card_id):
                    raise ValueError(f"op {n} ({op.op}): no card '{card_id}'. Nothing was applied.")
                case _:
                    assert_never(op)
        self.cards = cards

    def react(self, card_id: TCardId, reaction: Reaction | None) -> None:
        """Set the user's reaction on the card. KeyError for a missing card."""
        self.cards[card_id] = self.cards[card_id].model_copy(update={"reaction": reaction})

    def react_to_item(self, card_id: TCardId, number: TItemNumber, reaction: Reaction | None) -> None:
        """Set the user's reaction on the card's item of that number. KeyError for a missing card, IndexError for a missing item."""
        card = self.cards[card_id]
        items = list(card.items)
        items[number - 1] = items[number - 1].model_copy(update={"reaction": reaction})
        self.cards[card_id] = card.model_copy(update={"items": items})

    def comment(self, card_id: TCardId, text: str) -> None:
        """Add the user's comment to the card. KeyError for a missing card."""
        card = self.cards[card_id]
        self.cards[card_id] = card.model_copy(update={"comments": [*card.comments, Comment(text=text)]})
