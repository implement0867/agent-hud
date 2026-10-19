import { memo, useCallback, useState } from "react";
import type { ChangeEvent, KeyboardEvent } from "react";

import { assertNever } from "~/lib/assertNever";
import { Editable } from "~/primitives/Editable";
import { Markdown } from "~/primitives/Markdown";
import type { CellValue, ColumnType } from "~/protocol/schema";

export type ViewColumn = {
  key: string;
  title: string;
  type: ColumnType;
  options: readonly string[];
};

type CellProps = {
  column: ViewColumn;
  value: CellValue;
  onChange: (value: CellValue) => void;
};

const asText = (value: CellValue): string => {
  if (value === null) return "";
  if (typeof value === "boolean") return value ? "x" : "";
  return String(value);
};

const stop = (e: { stopPropagation: () => void }) => {
  e.stopPropagation();
};

/** The editor for one cell, chosen by column type. Add a case here to add a column type. */
export const Cell = memo(({ column, value, onChange }: CellProps) => {
  switch (column.type) {
    case "static":
      return <StaticCell value={asText(value)} onChange={onChange} />;
    case "text":
      return <TextCell value={asText(value)} onChange={onChange} />;
    case "check":
      return <CheckCell value={value === true} onChange={onChange} />;
    case "number":
      return (
        <NumberCell
          value={typeof value === "number" ? value : null}
          onChange={onChange}
        />
      );
    case "select":
      return (
        <SelectCell
          value={typeof value === "string" ? value : ""}
          options={column.options}
          onChange={onChange}
        />
      );
    default:
      return assertNever(column.type);
  }
});
Cell.displayName = "Cell";

type Commit<V> = { value: V; onChange: (value: CellValue) => void };

const StaticCell = ({ value, onChange }: Commit<string>) => (
  <Editable value={value} onCommit={onChange}>
    <Markdown text={value} inline />
  </Editable>
);

const TextCell = ({ value, onChange }: Commit<string>) => (
  <Editable
    value={value}
    onCommit={onChange}
    eager
    placeholder="—"
    className="cell-input"
  >
    <span>{value}</span>
  </Editable>
);

const CheckCell = ({ value, onChange }: Commit<boolean>) => {
  const toggle = useCallback(() => {
    onChange(!value);
  }, [value, onChange]);
  return (
    <input
      type="checkbox"
      className="cell-check"
      checked={value}
      onChange={toggle}
      onPointerDown={stop}
    />
  );
};

const NumberCell = ({ value, onChange }: Commit<number | null>) => {
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? (value === null ? "" : String(value));
  const edit = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setDraft(e.target.value);
  }, []);
  const commit = useCallback(() => {
    if (draft !== null) {
      const parsed = draft.trim() === "" ? null : Number(draft);
      if (parsed === null || Number.isFinite(parsed)) onChange(parsed);
    }
    setDraft(null);
  }, [draft, onChange]);
  const onKeyDown = useCallback((e: KeyboardEvent<HTMLInputElement>) => {
    e.stopPropagation();
    if (e.key === "Enter") e.currentTarget.blur();
    if (e.key === "Escape") setDraft(null);
  }, []);
  return (
    <input
      type="number"
      className="cell-number"
      value={shown}
      onChange={edit}
      onBlur={commit}
      onKeyDown={onKeyDown}
      onPointerDown={stop}
      placeholder="—"
    />
  );
};

type SelectProps = Commit<string> & { options: readonly string[] };

const SelectCell = ({ value, options, onChange }: SelectProps) => {
  const pick = useCallback(
    (e: ChangeEvent<HTMLSelectElement>) => {
      onChange(e.target.value === "" ? null : e.target.value);
    },
    [onChange],
  );
  return (
    <select
      className="cell-select"
      value={value}
      onChange={pick}
      onPointerDown={stop}
    >
      <option value="">—</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
};
