import { memo, useCallback, useMemo } from "react";

import { Anchor } from "~/feedback/Anchor";
import { AddRow } from "~/primitives/AddRow";
import { Cell } from "~/primitives/cells";
import type { ViewColumn } from "~/primitives/cells";
import type {
  CellValue,
  ColumnType,
  ITableEl,
  TableEl,
} from "~/protocol/schema";
import { useSend } from "~/store/socket";

type ViewRow = {
  id: string;
  author: "agent" | "user";
  cells: Readonly<Record<string, CellValue>>;
};

const typeMark: Readonly<Record<ColumnType, string>> = {
  static: "",
  text: "✎",
  check: "☑",
  number: "#",
  select: "▾",
};

/**
 * Static and interactive tables share this view. A static table is an interactive table
 * whose columns are all `static`; typed columns get editors from `cells.tsx`.
 */
export const TableBody = memo(({ el }: { el: TableEl | ITableEl }) => {
  const send = useSend();
  const columns = useMemo<readonly ViewColumn[]>(
    () =>
      el.kind === "itable"
        ? el.columns
        : el.columns.map((c) => ({
            ...c,
            type: "static" as const,
            options: [],
          })),
    [el],
  );
  const rows: readonly ViewRow[] = el.rows;
  const add = useCallback(
    (value: string) => {
      send({ t: "add", id: el.id, value });
    },
    [send, el.id],
  );
  return (
    <div className="table-body">
      <table className="grid">
        <thead>
          <tr>
            <th className="row-head">#</th>
            {columns.map((col) => (
              <th
                key={col.key}
                className={col.type === "static" ? undefined : "col-input"}
              >
                <Anchor el={el} anchor={`col:${col.key}`} thread="popover">
                  <span className="col-title">{col.title}</span>
                  {col.type === "static" ? null : (
                    <span className="col-type">{typeMark[col.type]}</span>
                  )}
                </Anchor>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, n) => (
            <Row key={row.id} el={el} row={row} n={n + 1} columns={columns} />
          ))}
        </tbody>
      </table>
      <AddRow label="Add row" onAdd={add} allowEmpty />
    </div>
  );
});
TableBody.displayName = "TableBody";

type RowProps = {
  el: TableEl | ITableEl;
  row: ViewRow;
  n: number;
  columns: readonly ViewColumn[];
};

const Row = memo(({ el, row, n, columns }: RowProps) => {
  const send = useSend();
  const remove = useCallback(() => {
    send({ t: "remove", id: el.id, anchor: row.id });
  }, [send, el.id, row.id]);
  return (
    <tr>
      <td className="row-head">
        <Anchor el={el} anchor={row.id} thread="popover" onRemove={remove}>
          <span className="row-label">r{n}</span>
          {row.author === "user" ? <span className="by-user">you</span> : null}
        </Anchor>
      </td>
      {columns.map((col) => (
        <RowCell
          key={col.key}
          el={el}
          rowId={row.id}
          column={col}
          value={row.cells[col.key] ?? null}
        />
      ))}
    </tr>
  );
});
Row.displayName = "Row";

type RowCellProps = {
  el: TableEl | ITableEl;
  rowId: string;
  column: ViewColumn;
  value: CellValue;
};

const RowCell = memo(({ el, rowId, column, value }: RowCellProps) => {
  const send = useSend();
  const anchor = `${rowId}:${column.key}`;
  const change = useCallback(
    (next: CellValue) => {
      send({ t: "edit", id: el.id, anchor, value: next });
    },
    [send, el.id, anchor],
  );
  return (
    <td className={column.type === "static" ? undefined : "col-input"}>
      <Anchor el={el} anchor={anchor} thread="popover">
        <Cell column={column} value={value} onChange={change} />
      </Anchor>
    </td>
  );
});
RowCell.displayName = "RowCell";
