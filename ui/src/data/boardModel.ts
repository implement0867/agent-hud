import { Author } from "~/domain/actions";
import type { TArrow, TBoard, TCard, TPoint } from "~/domain/board";
import { versionsOf } from "~/domain/board";
import type { TAgentState, THeard, TSnapshot } from "~/domain/events";
import { unsentOf } from "~/domain/pending";
import type { TUnsent } from "~/domain/pending";
import { invariant } from "~/lib/invariant";

/** One card as its frame renders it. */
export type TCardView = {
  id: string;
  card: TCard;
  /** Where the card shows: the drag in progress, else a drop the server has not confirmed, else the server's place, else the place the page gave it; null until the page places it. */
  at: TPoint | null;
  /** The width the user or the agent set; null makes the card as wide as its content needs, up to a column. */
  width: number | null;
  /** The height the user or the agent set; null makes the card as tall as its text, and a shorter card scrolls. */
  height: number | null;
  /** The number of earlier versions. */
  versions: number;
  /** The card's layer from 1: a higher one shows over the cards it crosses. */
  layer: number;
};

/** The page's own state of the cards, which the server does not keep. */
export type TLocal = {
  /** The cards in the order that the user or the agent last touched them; the last shows on top where cards cross. */
  touched: string[];
  /** The cards that arrived since the page first saw the board, until the view shows each. */
  fresh: string[];
  /** The card that the user drags, and where to. */
  dragging: { id: string; at: TPoint } | null;
  /** Where the user dropped cards, until the server has them there. */
  dropped: Record<string, TPoint>;
  /** The places that the page gave cards that had none, until the server has them. */
  placed: Record<string, TPoint>;
  /** The markdown of each card before the changes it shows, until the user hides them or edits the card. */
  changed: Record<string, string>;
  /** The user's arrows that the agent removed, until the user dismisses each or puts it back. */
  lostArrows: { id: string; arrow: TArrow }[];
  /** The cards the user put and the arrows the user removed from this page, whose next change is no news. */
  expected: string[];
};

export const emptyLocal: TLocal = {
  touched: [],
  fresh: [],
  dragging: null,
  dropped: {},
  placed: {},
  changed: {},
  lostArrows: [],
  expected: [],
};

/** The snapshot in the shape that the page renders. */
export type TBoardModel = {
  board: TBoard;
  agent: TAgentState;
  pending: THeard[];
  /** The refs and the action ids that the pending actions are on, which the page marks as unsent until the send. */
  unsent: TUnsent;
  waiting: number;
  cards: TCardView[];
  fresh: string[];
  changed: Record<string, string>;
  lostArrows: { id: string; arrow: TArrow }[];
};

/** The cards that joined, left, got a new version or changed place from one board to the next, and the arrows that went. */
export type TBoardChange = {
  arrived: string[];
  left: string[];
  revised: string[];
  moved: string[];
  lost: { id: string; arrow: TArrow }[];
};

const samePoint = (a: TPoint | undefined, b: TPoint) =>
  a?.x === b.x && a.y === b.y;

/** The change from one board to the next. */
export const diffBoards = (before: TBoard, after: TBoard): TBoardChange => ({
  arrived: Object.keys(after.cards).filter(
    (id) => !Object.hasOwn(before.cards, id),
  ),
  left: Object.keys(before.cards).filter(
    (id) => !Object.hasOwn(after.cards, id),
  ),
  revised: Object.keys(after.cards).filter(
    (id) => versionsOf(after, id) > versionsOf(before, id),
  ),
  moved: Object.entries(after.positions)
    .filter(([id, at]) => !samePoint(before.positions[id], at))
    .map(([id]) => id),
  lost: Object.entries(before.arrows)
    .filter(([id]) => !Object.hasOwn(after.arrows, id))
    .map(([id, arrow]) => ({ id, arrow })),
});

/** The order with the ids last, in their order. */
export const raise = (order: string[], ids: string[]) =>
  ids.length === 0
    ? order
    : [...order.filter((id) => !ids.includes(id)), ...ids];

const without = <T>(
  record: Record<string, T>,
  drop: (id: string, value: T) => boolean,
) =>
  Object.fromEntries(
    Object.entries(record).filter(([id, value]) => !drop(id, value)),
  );

/** The markdown of the card's version before its last, or null when it has none or the same text. */
const previousOf = (after: TBoard, id: string): string | null => {
  const previous = after.history[id]?.at(-1)?.card.md;
  const card = after.cards[id];
  return previous === undefined || card === undefined || previous === card.md
    ? null
    : previous;
};

/**
 * The page's state after the board changed: an arrival is fresh, and an arrival, a new version or a move puts the card
 * on top, as a touch by the user does. A card that left loses its place and its freshness; a drop the server confirmed
 * and a place the server has are done. A new version that the user did not put from this page shows its changes
 * against the version the user last saw, and a user's arrow that went without the user's unlink from this page is lost; the expected ones are consumed.
 */
export const afterChange = (
  local: TLocal,
  change: TBoardChange,
  after: TBoard,
): TLocal => {
  const left = (id: string) => change.left.includes(id);
  const news = change.revised.filter((id) => !local.expected.includes(id));
  const lost = change.lost.filter(
    ({ id, arrow }) =>
      arrow.author === Author.enum.user && !local.expected.includes(id),
  );
  const consumed = [...change.revised, ...change.lost.map(({ id }) => id)];
  return {
    ...local,
    changed: {
      ...without(
        local.changed,
        (id) =>
          left(id) ||
          (change.revised.includes(id) && !news.includes(id)) ||
          after.cards[id]?.md === local.changed[id],
      ),
      ...Object.fromEntries(
        news.flatMap((id) => {
          const before = local.changed[id] ?? previousOf(after, id);
          return before === null || before === after.cards[id]?.md
            ? []
            : [[id, before]];
        }),
      ),
    },
    lostArrows: [...local.lostArrows, ...lost],
    expected: local.expected.filter((id) => !consumed.includes(id)),
    touched: [change.arrived, change.revised, change.moved].reduce(
      raise,
      local.touched.filter((id) => !left(id)),
    ),
    fresh: [
      ...local.fresh.filter((id) => !left(id)),
      ...change.arrived.filter((id) => !local.fresh.includes(id)),
    ],
    dropped: without(local.dropped, (id, at) =>
      samePoint(after.positions[id], at),
    ),
    placed: without(
      local.placed,
      (id) => left(id) || Object.hasOwn(after.positions, id),
    ),
  };
};

/** The model of the snapshot with the page's own state. */
export const modelOf = (snapshot: TSnapshot, local: TLocal): TBoardModel => {
  const { board } = snapshot;
  const ids = Object.keys(board.cards);
  const order = [
    ...ids.filter((id) => !local.touched.includes(id)),
    ...local.touched.filter((id) => Object.hasOwn(board.cards, id)),
  ];
  return {
    board,
    agent: snapshot.agent,
    pending: snapshot.pending,
    unsent: unsentOf(snapshot.pending),
    waiting: snapshot.waiting,
    fresh: local.fresh,
    changed: local.changed,
    lostArrows: local.lostArrows,
    cards: Object.entries(board.cards).map(([id, card]) => ({
      id,
      card,
      at:
        local.dragging?.id === id
          ? local.dragging.at
          : (local.dropped[id] ??
            board.positions[id] ??
            local.placed[id] ??
            null),
      width: board.sizes[id]?.width ?? null,
      height: board.sizes[id]?.height ?? null,
      versions: versionsOf(board, id),
      layer: order.indexOf(id) + 1,
    })),
  };
};

/** The view of a card that is on the board. */
export const cardIn = (model: TBoardModel, id: string): TCardView => {
  const card = model.cards.find((view) => view.id === id);
  invariant(card !== undefined, `card ${id} is on the board`);
  return card;
};
