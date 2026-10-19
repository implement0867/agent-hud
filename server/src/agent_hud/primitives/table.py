import re
from dataclasses import dataclass
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from agent_hud.markdown import ColumnType, MarkdownError, TableContent, split_row
from agent_hud.primitives.base import (
    Author,
    BoxBase,
    CellValue,
    ElementBase,
    ElementKind,
    IdSource,
    LabelOf,
    Part,
    PathError,
    cell_text,
)


class Column(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    key: str
    title: str
    type: ColumnType = ColumnType.STATIC
    options: list[str] = Field(default_factory=list)

    def spec(self) -> str:
        """The header cell as the agent writes it."""
        match self.type:
            case ColumnType.STATIC:
                return self.title
            case ColumnType.SELECT:
                return f"{self.title} {{{','.join(self.options)}}}"
            case other:
                return f"{self.title} {{{other}}}"


class Row(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    id: str
    author: Author
    cells: dict[str, CellValue]


@dataclass(frozen=True, slots=True)
class TableRef:
    pass


@dataclass(frozen=True, slots=True)
class ColumnRef:
    key: str


@dataclass(frozen=True, slots=True)
class RowRef:
    row_id: str


@dataclass(frozen=True, slots=True)
class CellRef:
    row_id: str
    key: str


def column_keys(titles: list[str]) -> list[str]:
    """Unique keys that are safe in labels such as `opts.r2.ops_cost`."""
    keys: list[str] = []
    for n, title in enumerate(titles, start=1):
        base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:24] or f"c{n}"
        if base[0].isdigit() or re.fullmatch(r"r\d+", base):
            base = f"c_{base}"
        key, dup = base, 2
        while key in keys:
            key, dup = f"{base}_{dup}", dup + 1
        keys.append(key)
    return keys


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


def coerce(column: Column, value: CellValue) -> CellValue:
    match column.type:
        case ColumnType.STATIC | ColumnType.TEXT:
            return cell_text(value).strip()
        case ColumnType.CHECK:
            return _check(value)
        case ColumnType.NUMBER:
            return _number(value)
        case ColumnType.SELECT:
            text = cell_text(value).strip()
            if not text:
                return None
            choice = next((o for o in column.options if o.lower() == text.lower()), None)
            if choice is None:
                raise PathError(f"'{text}' is not one of {', '.join(column.options)}")
            return choice


class TableEl(BoxBase):
    """Columns typed other than `static` take user input."""

    kind: Literal[ElementKind.TABLE] = ElementKind.TABLE
    columns: list[Column]
    rows: list[Row]

    @classmethod
    def from_content(cls, *, id: str, title: str, content: TableContent, ids: IdSource, author: Author) -> Self:
        keys = column_keys([h.title for h in content.headers])
        columns = [
            Column(key=key, title=h.title, type=h.type, options=list(h.options))
            for h, key in zip(content.headers, keys, strict=True)
        ]
        table = cls(id=id, author=author, title=title, columns=columns, rows=[])
        table.rows = [table.make_row(cells, ids("k"), author) for cells in content.rows]
        return table

    def make_row(self, cells: list[str], row_id: str, author: Author) -> Row:
        if len(cells) > len(self.columns):
            raise MarkdownError(f"{self.id} has {len(self.columns)} columns, got {len(cells)} cells")
        padded = cells + [""] * (len(self.columns) - len(cells))
        values = {col.key: coerce(col, raw) for col, raw in zip(self.columns, padded, strict=True)}
        return Row(id=row_id, author=author, cells=values)

    def adopt(self, old: ElementBase) -> None:
        """Keep the rows whose first cell survives, with the user's input in typed columns."""
        match old:
            case TableEl(columns=[old_first, *_] as old_columns, rows=old_rows) if self.columns:
                by_key = {cell_text(row.cells[old_first.key]): row for row in old_rows}
            case _:
                return
        first = self.columns[0].key
        typed_kept = {c.key for c in old_columns} & {c.key for c in self.columns if c.type != ColumnType.STATIC}
        for row in self.rows:
            if (kept := by_key.pop(cell_text(row.cells[first]), None)) is None:
                continue
            row.id, row.author = kept.id, kept.author
            for key in typed_kept:
                if not row.cells[key]:
                    row.cells[key] = kept.cells[key]

    def parts(self) -> list[Part]:
        numbered = list(enumerate(self.rows, start=1))
        columns = [Part(f"col:{c.key}", c.key, c.title) for c in self.columns]
        rows = [Part(r.id, f"r{n}", self._row_text(r)) for n, r in numbered]
        cells = [
            Part(f"{r.id}:{c.key}", f"r{n}.{c.key}", cell_text(r.cells[c.key]))
            for n, r in numbered
            for c in self.columns
        ]
        return [Part("", "", self.title), *columns, *rows, *cells]

    def _row_text(self, row: Row) -> str:
        return " | ".join(cell_text(row.cells[c.key]) for c in self.columns)

    def _target(self, anchor: str) -> TableRef | ColumnRef | RowRef | CellRef:
        match anchor.split(":"):
            case [""]:
                return TableRef()
            case ["col", key]:
                return ColumnRef(key)
            case [row_id]:
                return RowRef(row_id)
            case [row_id, key]:
                return CellRef(row_id, key)
            case _:
                raise PathError(f"{self.id} has no part '{anchor}'")

    def _row(self, row_id: str) -> Row:
        row = next((r for r in self.rows if r.id == row_id), None)
        if row is None:
            raise PathError(f"{self.id} has no row '{row_id}'")
        return row

    def _column(self, key: str) -> Column:
        column = next((c for c in self.columns if c.key == key), None)
        if column is None:
            raise PathError(f"{self.id} has columns {', '.join(c.key for c in self.columns)}, not '{key}'")
        return column

    def set_value(self, anchor: str, value: CellValue) -> None:
        match self._target(anchor), value:
            case CellRef(row_id=row_id, key=key), _:
                self._row(row_id).cells[key] = coerce(self._column(key), value)
            case RowRef(row_id=row_id), str() as line:
                row = self._row(row_id)
                row.cells = self.make_row(split_row(line), row.id, row.author).cells
            case _:
                raise PathError(f"{self.label(anchor)}: set a row (`r2`, value `a | b`) or a cell (`r2.key`)")

    def insert(self, at: str, value: str, new_id: str, author: Author) -> None:
        match self._target(at):
            case TableRef():
                position = len(self.rows)
            case RowRef(row_id=row_id):
                position = self.rows.index(self._row(row_id))
            case _:
                raise PathError(f"{self.id}: insert before a row, such as `r2`")
        self.rows.insert(position, self.make_row(split_row(value) if value.strip() else [], new_id, author))

    def remove(self, anchor: str) -> str:
        match self._target(anchor):
            case RowRef(row_id=row_id):
                row = self._row(row_id)
                self.rows.remove(row)
                return self._row_text(row)
            case _:
                raise PathError(f"{self.label(anchor)}: only rows can be removed")

    def render(self, label_of: LabelOf) -> str:
        lines = [
            self.header(self.kind),
            "| # | " + " | ".join(c.spec() for c in self.columns) + " |",
            "|---" * (len(self.columns) + 1) + "|",
        ]
        for n, row in enumerate(self.rows, start=1):
            cells = (cell_text(row.cells[c.key]).replace("|", "\\|") for c in self.columns)
            by = " (user)" if row.author == Author.USER else ""
            lines.append(f"| r{n}{by} | " + " | ".join(cells) + " |")
        notes = [f"{p.label}{note}" for p in self.parts()[1:] if (note := self.feedback_note(p.anchor))]
        return "\n".join(lines + notes)
