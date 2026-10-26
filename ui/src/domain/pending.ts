import { ActionKind } from "~/domain/actions";
import type { TBoard } from "~/domain/board";
import type { THeard } from "~/domain/events";
import { cardTitle, firstLine, short } from "~/domain/text";
import { assertNever } from "~/lib/assertNever";

/** What the page shows as pending: the cards with an unsent put, and the ids of the unsent actions. */
export type TUnsent = {
  cards: ReadonlySet<string>;
  ids: ReadonlySet<string>;
};

/** The card the action is on, or the card an arrow starts at; none for a message, a clear or an unlink. */
const cardOf = ({ body }: THeard): string | null => {
  switch (body.kind) {
    case ActionKind.enum.comment:
    case ActionKind.enum.link:
      return body.card;
    case ActionKind.enum.put:
    case "edit":
    case ActionKind.enum.remove:
    case ActionKind.enum.restore:
    case ActionKind.enum.move:
    case ActionKind.enum.resize:
    case ActionKind.enum.place:
      return body.id;
    case ActionKind.enum.unlink:
    case ActionKind.enum.say:
    case ActionKind.enum.clear:
    case ActionKind.enum.send:
      return null;
    default:
      return assertNever(body);
  }
};

export const unsentOf = (pending: THeard[]): TUnsent => ({
  cards: new Set(
    pending.flatMap(({ body }) =>
      body.kind === ActionKind.enum.put || body.kind === "edit"
        ? [body.id]
        : [],
    ),
  ),
  ids: new Set(pending.map(({ id }) => id)),
});

/** One unsent action as the user reads it: what changed, and where on the board; a click shows the card or the thread. */
export type TLine = {
  id: string;
  card: string | null;
  thread: string | null;
  what: string;
  where: string;
};

/** The unsent actions on one card, or the messages, or the arrows, in the order of the first of them. */
export type TGroup = {
  key: string;
  title: string;
  lines: TLine[];
};

const titleOf = (board: TBoard, card: string) => {
  const md = board.cards[card]?.md;
  return md === undefined ? card : cardTitle(md) || card;
};

const describe = (heard: THeard, board: TBoard): Omit<TLine, "id"> => {
  const { body } = heard;
  const at = (card: string, what: string, where = "") => ({
    card,
    thread: null,
    what,
    where,
  });
  switch (body.kind) {
    case ActionKind.enum.put:
      return at(body.id, "new note", firstLine(body.md));
    case "edit":
      return at(body.id, "edited");
    case ActionKind.enum.remove:
      return at(body.id, "removed");
    case ActionKind.enum.restore:
      return at(body.id, "restored");
    case ActionKind.enum.comment:
      return {
        card: body.card,
        thread:
          board.messages.find((said) => said.id === heard.id)?.thread ?? null,
        what: `“${body.text}”`,
        where: body.quote === "" ? "the card" : short(body.quote),
      };
    case ActionKind.enum.say:
      return { card: null, thread: null, what: body.text, where: "" };
    case ActionKind.enum.link:
      return at(
        body.card,
        `arrow to ${titleOf(board, body.dst)}${body.text === "" ? "" : ` “${body.text}”`}`,
        body.quote === "" ? "the card" : short(body.quote),
      );
    case ActionKind.enum.unlink:
      return { card: null, thread: null, what: "arrow removed", where: "" };
    case ActionKind.enum.move:
      return at(body.id, "moved");
    case ActionKind.enum.resize:
      return at(body.id, "resized");
    case ActionKind.enum.place:
      return at(body.id, "placed");
    case ActionKind.enum.clear:
      return { card: null, thread: null, what: "cleared", where: "" };
    case ActionKind.enum.send:
      return { card: null, thread: null, what: "sent", where: "" };
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
  const id = cardOf(heard) ?? "";
  return {
    key: id,
    title:
      heard.body.kind === ActionKind.enum.put && !Object.hasOwn(board.cards, id)
        ? id
        : heard.body.kind === ActionKind.enum.put
          ? cardTitle(heard.body.md)
          : titleOf(board, id),
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
