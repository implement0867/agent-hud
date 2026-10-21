import re
from enum import StrEnum
from typing import Self

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
    options: tuple[str, ...] = ()

    @classmethod
    def from_header(cls, header: str) -> Self:
        """The column a header cell names: cost {number}, done {check}, note {text}, size {S, M, L}, or static without braces."""
        match re.fullmatch(r".*?\{([^{}]*)\}\s*", header):
            case None:
                return cls(kind=ColumnKind.static)
            case found:
                spec = found[1].strip()
        match spec:
            case ColumnKind.text | ColumnKind.check | ColumnKind.number:
                return cls(kind=ColumnKind(spec))
            case _:
                options = tuple(option.strip() for option in spec.split(",") if option.strip())
                if len(options) < 2:
                    raise ValueError(f"column '{header}' takes text, check, number or two or more options")
                return cls(kind=ColumnKind.select, options=options)

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
