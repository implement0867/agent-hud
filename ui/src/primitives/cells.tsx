import { memo, useState } from "react";

import { assertNever } from "~/lib/assertNever";
import { stop } from "~/lib/dom";
import { Editable } from "~/primitives/Editable";
import { Markdown } from "~/primitives/Markdown";
import type { CellValue, Column } from "~/protocol/schema";

type CellProps = {
  column: Column;
  value: CellValue;
  onChange: (value: CellValue) => void;
};

const cellText = (value: CellValue): string => {
  if (value === null) return "";
  if (typeof value === "boolean") return value ? "x" : "";
  return String(value);
};

/** The editor for one cell, chosen by column type. */
export const Cell = memo(({ column, value, onChange }: CellProps) => {
  switch (column.type) {
    case "static":
      return (
        <Editable value={cellText(value)} onCommit={onChange}>
          <Markdown text={cellText(value)} inline />
        </Editable>
      );
    case "text":
      return (
        <Editable
          value={cellText(value)}
          onCommit={onChange}
          eager
          placeholder="—"
          className="cell-input"
        >
          <span>{cellText(value)}</span>
        </Editable>
      );
    case "check":
      return (
        <input
          type="checkbox"
          className="cell-check"
          checked={value === true}
          onChange={() => {
            onChange(value !== true);
          }}
          onPointerDown={stop}
        />
      );
    case "number":
      return (
        <NumberCell
          value={typeof value === "number" ? value : null}
          onChange={onChange}
        />
      );
    case "select":
      return (
        <select
          className="cell-select"
          value={typeof value === "string" ? value : ""}
          onChange={(e) => {
            onChange(e.target.value === "" ? null : e.target.value);
          }}
          onPointerDown={stop}
        >
          <option value="">—</option>
          {column.options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      );
    default:
      return assertNever(column.type);
  }
});
Cell.displayName = "Cell";

type NumberProps = {
  value: number | null;
  onChange: (value: CellValue) => void;
};

const NumberCell = ({ value, onChange }: NumberProps) => {
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    if (draft !== null) {
      const parsed = draft.trim() === "" ? null : Number(draft);
      if (parsed === null || Number.isFinite(parsed)) onChange(parsed);
    }
    setDraft(null);
  };
  return (
    <input
      type="number"
      className="cell-number"
      value={draft ?? (value === null ? "" : String(value))}
      onChange={(e) => {
        setDraft(e.target.value);
      }}
      onBlur={commit}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape") setDraft(null);
      }}
      onPointerDown={stop}
      placeholder="—"
    />
  );
};
