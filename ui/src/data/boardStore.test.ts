import { describe, expect, it } from "vitest";

import type { TCardBox, TSurface } from "~/data/boardModel";
import { ConnectionStatus, createBoardStore } from "~/data/boardStore";
import type { TBoardSocket } from "~/data/boardSocket";
import type { TBody } from "~/domain/actions";
import type { TBoard, TCard } from "~/domain/board";
import type { TSnapshot } from "~/domain/events";
import { viewMargin } from "~/lib/geometry";
import type { TSize } from "~/lib/geometry";
import { gap } from "~/lib/packing";

const card: TCard = { md: "1. parse", author: "agent", edited: false };
const edge = viewMargin;
const area = { x: 0, y: 0, width: 1440, height: 900 };
const short: TSize = { width: 256, height: 100 };

const board = (patch: Partial<TBoard>): TBoard => ({
  cards: {},
  threads: {},
  arrows: {},
  messages: [],
  positions: {},
  sizes: {},
  history: {},
  ...patch,
});

const snapshot = (of: TBoard): TSnapshot => ({
  kind: "snapshot",
  board: of,
  agent: "waiting",
  pending: [],
  waiting: 0,
});

const measureShort = (_box: TCardBox): TSize => short;

const pageSurface: TSurface = {
  viewport: () => area,
  sizes: () => new Map(),
};

/** A server at the other end of the socket: it records the actions and answers each when the test says. */
const serve = () => {
  const sent: { body: TBody; answer: (taken: boolean) => void }[] = [];
  let receive: ((next: TSnapshot) => void) | null = null;
  const open = (onSnapshot: (next: TSnapshot) => void): TBoardSocket => {
    receive = onSnapshot;
    return {
      act: (body) =>
        new Promise((answer) => {
          sent.push({ body, answer });
        }),
      close: () => undefined,
    };
  };
  return {
    open,
    sent,
    bodies: () => sent.map(({ body }) => body),
    send: (next: TSnapshot) => {
      if (receive === null) throw new Error("the store has not opened");
      receive(next);
    },
  };
};

const cardsOf = (store: ReturnType<typeof createBoardStore>) => {
  const connection = store.getConnection();
  if (connection.status === ConnectionStatus.enum.connecting)
    throw new Error("the store has not published a model");
  return connection.model.cards.map(({ id, at }) => [id, at]);
};

describe("createBoardStore", () => {
  it("places a card that arrives without a place before it publishes, and tells the server", () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(
      snapshot(
        board({
          cards: { a: card, b: card },
          positions: { a: { x: edge, y: edge } },
        }),
      ),
    );
    const beside = { x: edge + short.width + gap, y: edge };
    expect(cardsOf(store)).toEqual([
      ["a", { x: edge, y: edge }],
      ["b", beside],
    ]);
    expect(server.bodies()).toEqual([{ kind: "place", id: "b", ...beside }]);
  });

  it("places into the whiteboard's view at its sizes once it attaches, and into the page's again once it leaves", () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    const far = { x: 5000, y: 5000, width: 1440, height: 900 };
    const leave = store.attach({
      viewport: () => far,
      sizes: () => new Map([["a", { width: 600, height: 100 }]]),
    });
    server.send(
      snapshot(
        board({
          cards: { a: card, b: card },
          positions: { a: { x: far.x + edge, y: far.y + edge } },
        }),
      ),
    );
    expect(cardsOf(store)[1]).toEqual([
      "b",
      { x: far.x + edge + 600 + gap, y: far.y + edge },
    ]);
    leave();
    server.send(
      snapshot(
        board({
          cards: { a: card, b: card, c: card },
          positions: {
            a: { x: far.x + edge, y: far.y + edge },
            b: { x: far.x + edge + 600 + gap, y: far.y + edge },
          },
        }),
      ),
    );
    expect(cardsOf(store)[2]).toEqual(["c", { x: edge, y: edge }]);
  });

  it("shows the user's new card where the user put it, and moves it there once the server has it", async () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(snapshot(board({})));
    const at = { x: 300, y: 400 };
    const creating = store.create("a", "1. parse", at);
    server.send(snapshot(board({ cards: { a: card } })));
    expect(cardsOf(store)).toEqual([["a", at]]);
    expect(server.bodies()).toEqual([{ kind: "put", id: "a", md: "1. parse" }]);
    server.sent[0]?.answer(true);
    await expect(creating).resolves.toBe(true);
    expect(server.bodies()[1]).toEqual({ kind: "move", id: "a", ...at });
  });

  it("forgets where the user's new card was to go when the server refuses the put", async () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(snapshot(board({})));
    const creating = store.create("a", "1. parse", { x: 300, y: 400 });
    server.sent[0]?.answer(false);
    await expect(creating).resolves.toBe(false);
    server.send(snapshot(board({ cards: { a: card } })));
    expect(cardsOf(store)).toEqual([["a", { x: edge, y: edge }]]);
  });

  it("brings a removed card back where it was", async () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(snapshot(board({ history: { a: [{ card, threads: {} }] } })));
    const at = { x: 300, y: 400 };
    const restoring = store.restoreCard("a", at);
    server.send(
      snapshot(
        board({ cards: { a: card }, history: { a: [{ card, threads: {} }] } }),
      ),
    );
    expect(cardsOf(store)).toEqual([["a", at]]);
    server.sent[0]?.answer(true);
    await expect(restoring).resolves.toBe(true);
    expect(server.bodies()).toEqual([
      { kind: "restore", id: "a" },
      { kind: "move", id: "a", ...at },
    ]);
  });
});
