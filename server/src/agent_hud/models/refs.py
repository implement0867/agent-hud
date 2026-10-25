from typing import NamedTuple, Self

from agent_hud.models.actions import Comment, Fill, Link, React, TBody, TCardId, TRef, Unreact


class Ref(NamedTuple):
    """
    A ref in its pieces: the card id, the number of a part in the card, and the column of a cell in a table row; a
    piece is "" where the ref stops, as for plan, plan/2 and plan/2/3. The board keys its feedback by the joined ref.
    """

    card: TCardId
    part: str = ""
    column: str = ""

    @classmethod
    def parse(cls, ref: TRef) -> Self:
        card, _, rest = ref.partition("/")
        part, _, column = rest.partition("/")
        return cls(card, part, column)

    @property
    def row(self) -> "Ref":
        """The ref of the part that a cell is in: its table row."""
        return self._replace(column="")

    def __str__(self) -> str:
        return "/".join(piece for piece in self if piece)


def card_of(ref: TRef) -> TCardId:
    """The id of the card that the ref is on."""
    return Ref.parse(ref).card


def named_refs(body: TBody) -> list[TRef]:
    """The parts whose text goes with the action: the part it names, the row of the cell it fills, or the ends of its arrow."""
    match body:
        case React(ref=ref) | Unreact(ref=ref) | Comment(ref=ref):
            return [ref]
        case Fill(ref=ref):
            return [str(Ref.parse(ref).row)]
        case Link(src=src, dst=dst):
            return [src, dst]
        case _:
            return []
