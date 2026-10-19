from typing import Literal, Self

from pydantic import Field

from agent_hud.markdown import ColumnType, HeaderSpec
from agent_hud.primitives.base import Author, CellValue, ElementKind, PathError
from agent_hud.primitives.table import Column, Row, TableBase

type ICell = str | float | bool | None


class IColumn(Column):
    """A column with an input type. `static` columns hold agent text; the others take user input."""

    type: ColumnType = Field(description="Input the user gets in this column", examples=[ColumnType.CHECK])
    options: list[str] = Field(description="Choices for `select` columns", examples=[["low", "med", "high"]])

    @classmethod
    def from_spec(cls, spec: HeaderSpec, key: str) -> Self:
        return cls(key=key, title=spec.title, type=spec.type, options=list(spec.options))

    def spec(self) -> str:
        match self.type:
            case ColumnType.STATIC:
                return self.title
            case ColumnType.SELECT:
                return f"{self.title} {{{','.join(self.options)}}}"
            case other:
                return f"{self.title} {{{other}}}"


def _check(value: CellValue) -> bool:
    match value:
        case bool() as flag:
            return flag
        case None:
            return False
        case int() | float() as number:
            return number != 0
        case str() as text if text.strip().lower() in {"x", "[x]", "yes", "y", "true", "1", "✓", "✔", "done"}:
            return True
        case str() as text if text.strip().lower() in {"", "[ ]", "no", "n", "false", "0", "-"}:
            return False
        case _:
            raise PathError(f"'{value}' is not a check value; use x or empty")


def _number(value: CellValue) -> float | None:
    match value:
        case None:
            return None
        case bool():
            raise PathError("expected a number, got a boolean")
        case int() | float() as number:
            return float(number)
        case str() as text if not text.strip():
            return None
        case str() as text:
            try:
                return float(text.strip().replace(",", ""))
            except ValueError:
                raise PathError(f"'{text}' is not a number") from None


class ITableEl(TableBase[IColumn, ICell]):
    """A table whose typed columns take user input: checkboxes, choices, numbers and free text."""

    kind: Literal[ElementKind.ITABLE] = Field(
        default=ElementKind.ITABLE, description="Discriminator", examples=[ElementKind.ITABLE]
    )

    def kind_name(self) -> str:
        return "itable"

    @classmethod
    def make_column(cls, spec: HeaderSpec, key: str) -> IColumn:
        return IColumn.from_spec(spec, key)

    def new_row(self, *, id: str, author: Author, cells: dict[str, ICell]) -> Row[ICell]:
        return Row[ICell](id=id, author=author, cells=cells)

    def coerce(self, column: IColumn, value: CellValue) -> ICell:
        match column.type:
            case ColumnType.STATIC | ColumnType.TEXT:
                return "" if value is None else str(value).strip()
            case ColumnType.CHECK:
                return _check(value)
            case ColumnType.NUMBER:
                return _number(value)
            case ColumnType.SELECT:
                text = "" if value is None else str(value).strip()
                if not text:
                    return None
                choice = next((o for o in column.options if o.lower() == text.lower()), None)
                if choice is None:
                    raise PathError(f"'{text}' is not one of {', '.join(column.options)}")
                return choice

    def format_cell(self, column: IColumn, value: ICell) -> str:
        match value:
            case None:
                return ""
            case bool() as flag:
                return "x" if flag else ""
            case int() | float() as number:
                return f"{number:g}"
            case str() as text:
                return text

    def keeps_user_input(self, column: IColumn) -> bool:
        return column.type != ColumnType.STATIC
