import { z } from "zod";

import {
  afterChange,
  diffBoards,
  emptyLocal,
  modelOf,
  placeArrivals,
  raise,
} from "~/data/boardModel";
import type {
  TBoardModel,
  TLocal,
  TMeasure,
  TSurface,
} from "~/data/boardModel";
import { openBoardSocket } from "~/data/boardSocket";
import type { TBoardSocket } from "~/data/boardSocket";
import { ActionKind } from "~/domain/actions";
import type { TBody } from "~/domain/actions";
import type { TPoint } from "~/domain/board";
import type { TSnapshot } from "~/domain/events";
import { invariant } from "~/lib/invariant";

export const ConnectionStatus = z
  .enum(["connecting", "live", "offline"])
  .describe(
    "Connecting: no snapshot yet. Live: the socket is open. Offline: the server went away and the page opens the socket again",
  );

export type TConnection =
  | { status: typeof ConnectionStatus.enum.connecting }
  | {
      status:
        | typeof ConnectionStatus.enum.live
        | typeof ConnectionStatus.enum.offline;
      model: TBoardModel;
    };

/** Resolves true when the server takes the action, and false when it refuses it or the server is away. */
export type TAct = (body: TBody, id?: string) => Promise<boolean>;

export type TBoardStore = {
  subscribe: (listener: () => void) => () => void;
  getConnection: () => TConnection;
  /** The model now, for a handler that acts on the latest board; there is one once the first snapshot is in. */
  read: () => TBoardModel;
  /** Opens the socket, and opens it again after a delay that grows to ten seconds each time it closes; returns the close. */
  open: () => () => void;
  act: TAct;
  /** Puts the card on top of the cards it crosses. */
  touch: (id: string) => void;
  /** Shows the card where the user drags it. */
  drag: (id: string, at: TPoint) => void;
  /** Moves the card where the user dropped it, and back when the server refuses. */
  drop: (id: string, at: TPoint) => void;
  /** Puts the user's new card on the board at the point: it shows there from the start, and moves there once it is on. Resolves true when the server takes the put. */
  create: (id: string, md: string, at: TPoint) => Promise<boolean>;
  /** Brings a removed card back at the point, where it was: it shows there from the start, and moves there once it is on. */
  restoreCard: (id: string, at: TPoint) => Promise<boolean>;
  /**
   * The whiteboard shows the board: its view and the sizes of the cards as it lays them out stand for the page's, for
   * the places the store gives cards, until the whiteboard goes. Returns the leave.
   */
  attach: (surface: TSurface) => () => void;
  /** The view showed the cards: they are not fresh any more. */
  saw: (ids: string[]) => void;
  /** The user hides the changes the card shows, or edited it. */
  sawChanges: (id: string) => void;
  /** The user asks to see what the card's last version changed against the version before it. */
  showChanges: (id: string) => void;
  /** The user dismissed the loss of the arrow, or put it back. */
  forgetLostArrow: (id: string) => void;
};

/**
 * The board as the server last sent it, with the page's own state of its cards, for useSyncExternalStore. Every card
 * it publishes has a place: a card that arrives without one is packed into the view, measured on the stage when the
 * page has not laid it out, and the server is told, so that every tab and reload shows the card there; the first tab
 * to place a card wins. The surface is the page's before the whiteboard shows: the window at the home view.
 */
export const createBoardStore = (
  measure: TMeasure,
  surface: TSurface,
  openSocket: typeof openBoardSocket = openBoardSocket,
): TBoardStore => {
  const listeners = new Set<() => void>();
  let snapshot: TSnapshot | null = null;
  let local = emptyLocal;
  let live = false;
  let socket: TBoardSocket | null = null;
  let shown = surface;
  let connection: TConnection = { status: ConnectionStatus.enum.connecting };

  const publish = () => {
    connection =
      snapshot === null
        ? { status: ConnectionStatus.enum.connecting }
        : {
            status: live
              ? ConnectionStatus.enum.live
              : ConnectionStatus.enum.offline,
            model: modelOf(snapshot, local),
          };
    for (const listener of listeners) listener();
  };

  const update = (next: (current: TLocal) => TLocal) => {
    local = next(local);
    publish();
  };

  const receive = (next: TSnapshot) => {
    if (snapshot !== null)
      local = afterChange(
        local,
        diffBoards(snapshot.board, next.board),
        next.board,
      );
    const arrivals = placeArrivals(next.board, local, measure, shown);
    local = { ...local, placed: { ...local.placed, ...arrivals } };
    snapshot = next;
    live = true;
    publish();
    for (const [id, at] of Object.entries(arrivals))
      void act({ kind: ActionKind.enum.place, id, ...at });
  };

  /** Acts on the board; a put or an unlink by the user is expected, so that the change it brings is no news. */
  const act: TAct = async (body, id) => {
    if (!live || socket === null) return false;
    const expected =
      body.kind === ActionKind.enum.put || body.kind === ActionKind.enum.unlink
        ? body.id
        : null;
    if (expected !== null)
      update((current) => ({
        ...current,
        expected: [...current.expected, expected],
      }));
    const taken = await socket.act(body, id);
    if (!taken && expected !== null)
      update((current) => ({
        ...current,
        expected: current.expected.filter((id) => id !== expected),
      }));
    return taken;
  };

  /** Brings the card onto the board with the body, showing it at the point meanwhile, then moves it there. */
  const bring = async (id: string, at: TPoint, body: TBody) => {
    update((current) => ({
      ...current,
      dropped: { ...current.dropped, [id]: at },
    }));
    const taken = await act(body);
    if (taken) void act({ kind: ActionKind.enum.move, id, ...at });
    else
      update(({ dropped: { [id]: _refused, ...rest }, ...current }) => ({
        ...current,
        dropped: rest,
      }));
    return taken;
  };

  return {
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    getConnection: () => connection,
    read: () => {
      invariant(
        connection.status !== ConnectionStatus.enum.connecting,
        "the board renders once the first snapshot is in",
      );
      return connection.model;
    },
    open: () => {
      let delay = 1000;
      let timer: ReturnType<typeof setTimeout> | undefined;
      const connect = () => {
        socket = openSocket(
          (next) => {
            delay = 1000;
            receive(next);
          },
          () => {
            socket = null;
            live = false;
            publish();
            timer = setTimeout(connect, delay);
            delay = Math.min(delay * 2, 10000);
          },
        );
      };
      connect();
      return () => {
        clearTimeout(timer);
        socket?.close();
        socket = null;
        live = false;
      };
    },
    act,
    touch: (id) => {
      update((current) => ({
        ...current,
        touched: raise(current.touched, [id]),
      }));
    },
    drag: (id, at) => {
      update((current) => ({ ...current, dragging: { id, at } }));
    },
    drop: (id, at) => {
      update((current) => ({
        ...current,
        dragging: null,
        dropped: { ...current.dropped, [id]: at },
      }));
      void act({ kind: ActionKind.enum.move, id, ...at }).then((taken) => {
        if (taken) return;
        update(({ dropped: { [id]: _refused, ...rest }, ...current }) => ({
          ...current,
          dropped: rest,
        }));
      });
    },
    create: (id, md, at) =>
      bring(id, at, { kind: ActionKind.enum.put, id, md }),
    restoreCard: (id, at) =>
      bring(id, at, { kind: ActionKind.enum.restore, id }),
    attach: (next) => {
      shown = next;
      return () => {
        shown = surface;
      };
    },
    saw: (ids) => {
      update((current) => ({
        ...current,
        fresh: current.fresh.filter((id) => !ids.includes(id)),
      }));
    },
    sawChanges: (id) => {
      if (!Object.hasOwn(local.changed, id)) return;
      update(({ changed: { [id]: _seen, ...rest }, ...current }) => ({
        ...current,
        changed: rest,
      }));
    },
    showChanges: (id) => {
      if (snapshot === null) return;
      const before = snapshot.board.history[id]?.at(-1)?.card.md;
      if (before === undefined) return;
      update((current) => ({
        ...current,
        changed: { ...current.changed, [id]: before },
      }));
    },
    forgetLostArrow: (id) => {
      update((current) => ({
        ...current,
        lostArrows: current.lostArrows.filter((lost) => lost.id !== id),
      }));
    },
  };
};
