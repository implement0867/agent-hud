import re
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from agent_hud.markdown import HeaderSpec, MarkdownError, TableContent, split_row
from agent_hud.primitives.base import Author, BoxBase, CellValue, ElementBase, ElementKind, IdSource, PathError, quote


class Column(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    key: str = Field(description="Column key used in labels such as `r2.price`", examples=["price"])
    title: str = Field(description="Header text", examples=["Price"])

    @classmethod
    def from_spec(cls, spec: HeaderSpec, key: str) -> Self:
        return cls(key=key, title=spec.title)

    def spec(self) -> str:
        """Header cell as the agent writes it."""
        return self.title


class Row[V: str | float | bool | None](BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", use_enum_values=True)

    id: str = Field(description="Stable anchor key of the row", examples=["k9"])
    author: Author = Field(description="Who added the row", examples=[Author.AGENT])
    cells: dict[str, V] = Field(description="Cell values keyed by column key", examples=[{"price": "$5"}])


def column_keys(titles: list[str]) -> list[str]:
    """Short, unique, label-safe keys derived from header titles."""
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


class TableBase[C: Column, V: str | float | bool | None](BoxBase):
    """Rows, columns and cells are anchors: labels `r2`, `price`, `r2.price`."""

    columns: list[C] = Field(description="Columns in display order", examples=[[]])
    rows: list[Row[V]] = Field(description="Rows in display order", examples=[[]])

    # -- hooks for subclasses ----------------------------------------------------------------

    @classmethod
    def make_column(cls, spec: HeaderSpec, key: str) -> C:
        raise NotImplementedError

    def coerce(self, column: C, value: CellValue) -> V:
        """Validate a cell value for the column."""
        raise NotImplementedError

    def new_row(self, *, id: str, author: Author, cells: dict[str, V]) -> Row[V]:
        """A row of the concrete cell type; generic parameters are erased at runtime."""
        raise NotImplementedError

    def format_cell(self, column: C, value: V) -> str:
        return "" if value is None else str(value)

    def keeps_user_input(self, column: C) -> bool:
        """Whether a re-put leaves a user's non-empty value in this column alone."""
        return False

    # -- construction ------------------------------------------------------------------------

    @classmethod
    def from_content(cls, *, id: str, title: str | None, content: TableContent, ids: IdSource, author: Author) -> Self:
        keys = column_keys([h.title for h in content.headers])
        columns = [cls.make_column(spec, key) for spec, key in zip(content.headers, keys, strict=True)]
        table = cls(id=id, author=author, title=title, columns=columns, rows=[])
        for cells in content.rows:
            table.rows.append(table.make_row(cells, ids, author))
        return table

    def make_row(self, cells: list[str], ids: IdSource, author: Author) -> Row[V]:
        if len(cells) > len(self.columns):
            raise MarkdownError(f"{self.id} has {len(self.columns)} columns, got {len(cells)} cells")
        padded = cells + [""] * (len(self.columns) - len(cells))
        values = {col.key: self.coerce(col, raw) for col, raw in zip(self.columns, padded, strict=True)}
        return self.new_row(id=ids("k"), author=author, cells=values)

    def adopt(self, old: ElementBase) -> None:
        """Keep row anchors, feedback and user input of rows whose first cell survives a re-put."""
        if not isinstance(old, type(self)) or not self.columns or not old.columns:
            return
        first = self.columns[0].key
        by_key = {str(row.cells.get(old.columns[0].key)): row for row in old.rows}
        old_cols = {col.key for col in old.columns}
        for row in self.rows:
            if (kept := by_key.pop(str(row.cells.get(first)), None)) is None:
                continue
            row.id, row.author = kept.id, kept.author
            for col in self.columns:
                if col.key in old_cols and self.keeps_user_input(col) and not row.cells.get(col.key):
                    row.cells[col.key] = self.coerce(col, kept.cells.get(col.key))

    # -- anchors -----------------------------------------------------------------------------

    def anchor_keys(self) -> list[str]:
        cols = [f"col:{c.key}" for c in self.columns]
        rows = [r.id for r in self.rows]
        cells = [f"{r.id}:{c.key}" for r in self.rows for c in self.columns]
        return ["", *cols, *rows, *cells]

    def _row_no(self, row_id: str) -> int | None:
        return next((n for n, row in enumerate(self.rows, start=1) if row.id == row_id), None)

    def suffix(self, anchor: str) -> str | None:
        keys = {c.key for c in self.columns}
        match anchor.split(":"):
            case [""]:
                return ""
            case ["col", key] if key in keys:
                return key
            case [row_id] if (n := self._row_no(row_id)) is not None:
                return f"r{n}"
            case [row_id, key] if key in keys and (n := self._row_no(row_id)) is not None:
                return f"r{n}.{key}"
            case _:
                return None

    def _row_index(self, part: str, *, allow_end: bool = False) -> int:
        limit = len(self.rows) + (1 if allow_end else 0)
        m = re.fullmatch(r"r(\d+)", part)
        if m is None or not 1 <= int(m.group(1)) <= limit:
            raise PathError(f"{self.id} has rows r1..r{len(self.rows)}, not '{part}'")
        return int(m.group(1)) - 1

    def _column(self, key: str) -> C:
        col = next((c for c in self.columns if c.key == key), None)
        if col is None:
            raise PathError(f"{self.id} has columns {', '.join(c.key for c in self.columns)}, not '{key}'")
        return col

    def resolve(self, suffix: str) -> str:
        match suffix.split("."):
            case [""]:
                return ""
            case [part] if re.fullmatch(r"r\d+", part):
                return self.rows[self._row_index(part)].id
            case [key]:
                return f"col:{self._column(key).key}"
            case [part, key]:
                return f"{self.rows[self._row_index(part)].id}:{self._column(key).key}"
            case _:
                raise PathError(f"{self.id} has no part '{suffix}'")

    def _row(self, row_id: str) -> Row[V]:
        row = next((r for r in self.rows if r.id == row_id), None)
        if row is None:
            raise PathError(f"{self.id} has no row '{row_id}'")
        return row

    def anchor_text(self, anchor: str) -> str | None:
        match anchor.split(":"):
            case ["col", key]:
                return next((c.title for c in self.columns if c.key == key), None)
            case [row_id, key] if (row := next((r for r in self.rows if r.id == row_id), None)) is not None:
                return next((self.format_cell(c, row.cells[c.key]) for c in self.columns if c.key == key), None)
            case [row_id] if row_id and (row := next((r for r in self.rows if r.id == row_id), None)) is not None:
                return " | ".join(self.format_cell(c, row.cells[c.key]) for c in self.columns)
            case _:
                return None

    def value_text(self, anchor: str) -> str:
        match anchor.split(":"):
            case [row_id, key] if row_id != "col" and (row := next((r for r in self.rows if r.id == row_id), None)):
                return describe_value(row.cells.get(key))
            case _:
                return super().value_text(anchor)

    # -- mutations ---------------------------------------------------------------------------

    def set_value(self, anchor: str, value: CellValue) -> None:
        match anchor.split(":"), value:
            case [row_id, key], _ if row_id != "col":
                self._row(row_id).cells[key] = self.coerce(self._column(key), value)
            case [row_id], str() as line if row_id:
                row = self._row(row_id)
                row.cells = self.make_row(split_row(line), lambda _: row.id, row.author).cells
            case _:
                raise PathError(
                    f"{self.label(anchor) or self.id}: set a row (`r2`, value `a | b`) or a cell (`r2.key`)"
                )

    def insert(self, at: str, value: str, ids: IdSource, author: Author) -> str:
        position = len(self.rows) if at == "" else self._row_index(at, allow_end=True)
        row = self.make_row(split_row(value) if value.strip() else [], ids, author)
        self.rows.insert(position, row)
        return row.id

    def remove(self, anchor: str) -> str:
        row = self._row(anchor)
        text = self.anchor_text(anchor) or ""
        self.rows.remove(row)
        return text

    # -- rendering ---------------------------------------------------------------------------

    def render(self) -> str:
        lines = [
            self.header(),
            "| # | " + " | ".join(c.spec() for c in self.columns) + " |",
            "|---" * (len(self.columns) + 1) + "|",
        ]
        for n, row in enumerate(self.rows, start=1):
            cells = (self.format_cell(c, row.cells[c.key]).replace("|", "\\|") for c in self.columns)
            by = " (user)" if row.author == Author.USER else ""
            lines.append(f"| r{n}{by} | " + " | ".join(cells) + " |")
        notes = [
            f"{suffix}{note}"
            for anchor in self.anchor_keys()[1:]
            if (note := self.feedback_note(anchor)) and (suffix := self.suffix(anchor)) is not None
        ]
        return "\n".join(lines + notes)


class TableEl(TableBase[Column, str]):
    """A static markdown table."""

    kind: Literal[ElementKind.TABLE] = Field(
        default=ElementKind.TABLE, description="Discriminator", examples=[ElementKind.TABLE]
    )

    def kind_name(self) -> str:
        return "table"

    @classmethod
    def make_column(cls, spec: HeaderSpec, key: str) -> Column:
        return Column.from_spec(spec, key)

    def new_row(self, *, id: str, author: Author, cells: dict[str, str]) -> Row[str]:
        return Row[str](id=id, author=author, cells=cells)

    def coerce(self, column: Column, value: CellValue) -> str:
        match value:
            case None:
                return ""
            case bool() as flag:
                return "x" if flag else ""
            case int() | float() as number:
                return f"{number:g}"
            case str() as text:
                return text.strip()


def describe_value(value: CellValue) -> str:
    """A cell value as the agent reads it in reports."""
    match value:
        case None:
            return "empty"
        case bool() as flag:
            return "yes" if flag else "no"
        case int() | float() as number:
            return f"{number:g}"
        case str() as text:
            return quote(text) if text else "empty"
