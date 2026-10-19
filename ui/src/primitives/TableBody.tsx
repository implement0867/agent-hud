import { memo } from "react";

import { Anchor } from "~/feedback/Anchor";
import { AddRow } from "~/primitives/AddRow";
import { Cell } from "~/primitives/cells";
import { Author } from "~/protocol/schema";
import type { Column, ColumnType, Row, TableEl } from "~/protocol/schema";
import { useSend } from "~/store/socket";

const typeMark: Readonly<Record<ColumnType, string>> = {
  static: "",
  text: "✎",
  check: "☑",
  number: "#",
  select: "▾",
};

export const TableBody = memo(({ el }: { el: TableEl }) => {
  const send = useSend();
  return (
    <div className="table-body">
      <table className="grid">
        <thead>
          <tr>
            <th className="row-head">#</th>
            {el.columns.map((col) => (
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
          {el.rows.map((row, n) => (
            <TableRow key={row.id} el={el} row={row} n={n + 1} />
          ))}
        </tbody>
      </table>
      <AddRow
        label="Add row"
        allowEmpty
        onAdd={(value) => {
          send({ t: "add", id: el.id, value });
        }}
      />
    </div>
  );
});
TableBody.displayName = "TableBody";

type RowProps = { el: TableEl; row: Row; n: number };

const TableRow = memo(({ el, row, n }: RowProps) => {
  const send = useSend();
  return (
    <tr>
      <td className="row-head">
        <Anchor
          el={el}
          anchor={row.id}
          thread="popover"
          onRemove={() => {
            send({ t: "remove", id: el.id, anchor: row.id });
          }}
        >
          <span className="row-label">r{n}</span>
          {row.author === Author.enum.user ? (
            <span className="by-user">you</span>
          ) : null}
        </Anchor>
      </td>
      {el.columns.map((col) => (
        <TableCell key={col.key} el={el} row={row} column={col} />
      ))}
    </tr>
  );
});
TableRow.displayName = "TableRow";

type CellProps = { el: TableEl; row: Row; column: Column };

const TableCell = memo(({ el, row, column }: CellProps) => {
  const send = useSend();
  const anchor = `${row.id}:${column.key}`;
  return (
    <td className={column.type === "static" ? undefined : "col-input"}>
      <Anchor el={el} anchor={anchor} thread="popover">
        <Cell
          column={column}
          value={row.cells[column.key] ?? null}
          onChange={(value) => {
            send({ t: "edit", id: el.id, anchor, value });
          }}
        />
      </Anchor>
    </td>
  );
});
TableCell.displayName = "TableCell";
