import re
from enum import StrEnum
from typing import Self

from pydantic import Field

from agent_hud.models.actions import TValue
from agent_hud.models.base import Model


class ColumnKind(StrEnum):
    static = "static"
    text = "text"
    check = "check"
    number = "number"
    select = "select"


class Column(Model):
    kind: ColumnKind
    name: str = ""
    options: tuple[str, ...] = ()

    @classmethod
    def from_header(cls, header: str) -> Self:
        """The column a header cell names: cost {number}, done {check}, note {text}, size {S, M, L}, or static without braces."""
        match re.fullmatch(r"(.*?)\{([^{}]*)\}\s*", header):
            case None:
                return cls(kind=ColumnKind.static, name=header.strip())
            case found:
                name, spec = found[1].strip(), found[2].strip()
        match spec:
            case ColumnKind.text | ColumnKind.check | ColumnKind.number:
                return cls(kind=ColumnKind(spec), name=name)
            case _:
                options = tuple(option.strip() for option in spec.split(",") if option.strip())
                if len(options) < 2:
                    raise ValueError(f"column '{header}' takes text, check, number or two or more options")
                return cls(kind=ColumnKind.select, name=name, options=options)

    @property
    def takes(self) -> str:
        """What the column takes, for an error on a value that it does not take."""
        match self.kind:
            case ColumnKind.select:
                return f"one of {', '.join(self.options)}"
            case ColumnKind.check:
                return "true or false"
            case ColumnKind.number:
                return "a number"
            case ColumnKind.text:
                return "text"
            case ColumnKind.static:
                return "no value"

    def fits(self, value: TValue) -> bool:
        match self.kind, value:
            case ColumnKind.static, _:
                return False
            case _, None:
                return True
            case ColumnKind.text, str():
                return True
            case ColumnKind.check, bool():
                return True
            case ColumnKind.number, bool():
                return False
            case ColumnKind.number, float() | int():
                return True
            case ColumnKind.select, str() as option:
                return option in self.options
            case _:
                return False


class Table(Model):
    """A table of a card, as write reports it: the numbers of its body rows as parts, and its input columns by number."""

    rows: list[str] = Field(description="The part number of each body row, in order")
    columns: dict[str, Column] = Field(
        description="The input columns by their number in the table, counted with the plain columns from 1"
    )
