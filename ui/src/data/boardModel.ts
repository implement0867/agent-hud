import type { TBoard, TCard, TPoint } from "~/domain/board";
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
};

export const emptyLocal: TLocal = {
  touched: [],
  fresh: [],
  dragging: null,
  dropped: {},
  placed: {},
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
};

/** The cards that joined, left, got a new version or changed place from one board to the next. */
export type TBoardChange = {
  arrived: string[];
  left: string[];
  revised: string[];
  moved: string[];
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

/**
 * The page's state after the board changed: an arrival is fresh, and an arrival, a new version or a move puts the card
 * on top, as a touch by the user does. A card that left loses its place and its freshness; a drop the server confirmed
 * and a place the server has are done.
 */
export const afterChange = (
  local: TLocal,
  change: TBoardChange,
  after: TBoard,
): TLocal => {
  const left = (id: string) => change.left.includes(id);
  return {
    ...local,
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
