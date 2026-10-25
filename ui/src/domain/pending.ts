import { ActionKind } from "~/domain/actions";
import type { TValue } from "~/domain/actions";
import type { TBoard } from "~/domain/board";
import type { THeard } from "~/domain/events";
import { cardTitle, columnsOf, firstLine, rowName } from "~/domain/parts";
import { cardOf, rowOf } from "~/domain/ref";
import { assertNever } from "~/lib/assertNever";

/** What the page shows as pending: the refs with an unsent action on them, parts, cells, cards and arrows, and the ids of the unsent actions. */
export type TUnsent = {
  refs: ReadonlySet<string>;
  ids: ReadonlySet<string>;
};

/** The ref the action is on: the part or cell it names, or the card or arrow it is about; none for a message or a clear. */
const refOf = ({ body }: THeard): string | null => {
  switch (body.kind) {
    case ActionKind.enum.react:
    case ActionKind.enum.unreact:
    case ActionKind.enum.comment:
    case ActionKind.enum.fill:
      return body.ref;
    case ActionKind.enum.put:
    case "edit":
    case ActionKind.enum.remove:
    case ActionKind.enum.restore:
    case ActionKind.enum.move:
    case ActionKind.enum.resize:
    case ActionKind.enum.place:
    case ActionKind.enum.link:
    case ActionKind.enum.unlink:
      return body.id;
    case ActionKind.enum.say:
    case ActionKind.enum.clear:
    case ActionKind.enum.send:
      return null;
    default:
      return assertNever(body);
  }
};

export const unsentOf = (pending: THeard[]): TUnsent => ({
  refs: new Set(
    pending.flatMap((heard) => {
      const ref = refOf(heard);
      return ref === null ? [] : [ref];
    }),
  ),
  ids: new Set(pending.map(({ id }) => id)),
});

/** One unsent action as the user reads it: what changed, and where on the board; a click shows the ref when it has one. */
export type TLine = {
  id: string;
  ref: string | null;
  what: string;
  where: string;
};

/** The unsent actions on one card, or the messages, or the arrows, in the order of the first of them. */
export type TGroup = {
  key: string;
  title: string;
  lines: TLine[];
};

const nameOfValue = (value: TValue): string => {
  switch (value) {
    case null:
      return "cleared";
    case true:
      return "yes";
    case false:
      return "no";
    default:
      return String(value);
  }
};

const describe = (heard: THeard, board: TBoard): Omit<TLine, "id"> => {
  const { body, parts } = heard;
  const partText = (ref: string) => parts[ref] ?? ref;
  switch (body.kind) {
    case ActionKind.enum.put:
      return { ref: body.id, what: "new note", where: firstLine(body.md) };
    case "edit":
      return { ref: body.id, what: "edited", where: "" };
    case ActionKind.enum.remove:
      return { ref: body.id, what: "removed", where: "" };
    case ActionKind.enum.restore:
      return { ref: body.id, what: "restored", where: "" };
    case ActionKind.enum.react:
      return { ref: body.ref, what: body.reaction, where: partText(body.ref) };
    case ActionKind.enum.unreact:
      return { ref: body.ref, what: "no reaction", where: partText(body.ref) };
    case ActionKind.enum.comment:
      return {
        ref: body.ref,
        what: `“${body.text}”`,
        where: partText(body.ref),
      };
    case ActionKind.enum.say:
      return { ref: null, what: body.text, where: "" };
    case ActionKind.enum.fill: {
      const row = rowOf(body.ref);
      const column = Number(body.ref.slice(row.length + 1));
      const title = columnsOf(board.cards[cardOf(row)]?.md ?? "")[column - 1];
      return {
        ref: row,
        what: `${title === undefined || title === "" ? `column ${String(column)}` : title}: ${nameOfValue(body.value)}`,
        where: parts[row] === undefined ? row : rowName(partText(row)),
      };
    }
    case ActionKind.enum.link:
      return {
        ref: body.src,
        what: `arrow to ${partText(body.dst)}${body.text === "" ? "" : ` “${body.text}”`}`,
        where: partText(body.src),
      };
    case ActionKind.enum.unlink:
      return { ref: null, what: "arrow removed", where: "" };
    case ActionKind.enum.move:
      return { ref: body.id, what: "moved", where: "" };
    case ActionKind.enum.resize:
      return { ref: body.id, what: "resized", where: "" };
    case ActionKind.enum.place:
      return { ref: body.id, what: "placed", where: "" };
    case ActionKind.enum.clear:
      return { ref: null, what: "cleared", where: "" };
    case ActionKind.enum.send:
      return { ref: null, what: "sent", where: "" };
    default:
      return assertNever(body);
  }
};

/** The group an action lists under: its card, by id; or the chat, the arrows or the board. */
const groupOf = (
  heard: THeard,
  board: TBoard,
): { key: string; title: string } => {
  const apart: Partial<Record<string, { key: string; title: string }>> = {
    [ActionKind.enum.say]: { key: "chat", title: "Chat" },
    [ActionKind.enum.unlink]: { key: "arrows", title: "Arrows" },
    [ActionKind.enum.clear]: { key: "board", title: "The board" },
  };
  const found = apart[heard.body.kind];
  if (found !== undefined) return found;
  const ref = refOf(heard) ?? "";
  const id = cardOf(
    heard.body.kind === ActionKind.enum.link ? heard.body.src : ref,
  );
  const md = board.cards[id]?.md;
  return {
    key: id,
    title:
      md === undefined
        ? id
        : heard.body.kind === ActionKind.enum.put
          ? cardTitle(heard.body.md)
          : cardTitle(md),
  };
};

/** The unsent actions as the user reads them, one line each, grouped by card in the order of the first action on each. */
export const groupPending = (pending: THeard[], board: TBoard): TGroup[] =>
  pending.reduce<TGroup[]>((groups, heard) => {
    const { key, title } = groupOf(heard, board);
    const line = { id: heard.id, ...describe(heard, board) };
    const group = groups.find((candidate) => candidate.key === key);
    if (group === undefined) return [...groups, { key, title, lines: [line] }];
    return groups.map((candidate) =>
      candidate === group
        ? { ...candidate, lines: [...candidate.lines, line] }
        : candidate,
    );
  }, []);
