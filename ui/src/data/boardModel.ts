import { Author } from "~/domain/actions";
import type { TArrow, TBoard, TCard, TPoint } from "~/domain/board";
import { versionsOf } from "~/domain/board";
import type { TAgentState, THeard, TSnapshot } from "~/domain/events";
import { changesBetween } from "~/domain/parts";
import type { TChanges } from "~/domain/parts";
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
  /** What the agent's last version of each card changed, until the user looks at the card. */
  changed: Record<string, TChanges>;
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
  changed: Record<string, TChanges>;
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

/** What the card's new version changed against the version before it, or null when it has none or changed no part. */
const changesOf = (after: TBoard, id: string): TChanges | null => {
  const previous = after.history[id]?.at(-1);
  const card = after.cards[id];
  if (previous === undefined || card === undefined) return null;
  const changes = changesBetween(previous.card.md, card.md);
  return changes.parts.length === 0 && changes.removed.length === 0
    ? null
    : changes;
};

/**
 * The page's state after the board changed: an arrival is fresh, and an arrival, a new version or a move puts the card
 * on top, as a touch by the user does. A card that left loses its place and its freshness; a drop the server confirmed
 * and a place the server has are done. A new version that the user did not put from this page marks what it changed,
 * and a user's arrow that went without the user's unlink from this page is lost; the expected ones are consumed.
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
      ...without(local.changed, (id) => left(id) || news.includes(id)),
      ...Object.fromEntries(
        news.flatMap((id) => {
          const changes = changesOf(after, id);
          return changes === null ? [] : [[id, changes]];
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
      width: board.widths[id] ?? null,
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
