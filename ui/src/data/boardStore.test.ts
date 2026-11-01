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
    const shown = board({
      cards: { a: card },
      positions: { a: { x: far.x + edge, y: far.y + edge } },
    });
    server.send(snapshot(shown));
    server.send(snapshot({ ...shown, cards: { a: card, b: card } }));
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

describe("createBoardStore under attack", () => {
  it("keeps the card where the page put it through a snapshot that comes before the server has the place, and tells the server once", () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    const unplaced = board({
      cards: { a: card, b: card },
      positions: { a: { x: edge, y: edge } },
    });
    server.send(snapshot(unplaced));
    const first = cardsOf(store)[1];
    server.send(
      snapshot({ ...unplaced, cards: { ...unplaced.cards, c: card } }),
    );
    expect(cardsOf(store)[1]).toEqual(first);
    expect(cardsOf(store)[2]).toEqual([
      "c",
      { x: edge + 2 * (short.width + gap), y: edge },
    ]);
    expect(server.bodies().filter(({ kind }) => kind === "place")).toHaveLength(
      2,
    );
  });

  it("shows the card where the agent moved it when the move comes before the page's place is confirmed", () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(snapshot(board({ cards: { b: card } })));
    expect(cardsOf(store)).toEqual([["b", { x: edge, y: edge }]]);
    server.send(
      snapshot(
        board({ cards: { b: card }, positions: { b: { x: 900, y: 900 } } }),
      ),
    );
    server.sent[0]?.answer(false);
    expect(cardsOf(store)).toEqual([["b", { x: 900, y: 900 }]]);
  });

  it("packs a card that arrives during a drag around the dragged card where it is, and the drop then moves the dragged card", () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(
      snapshot(
        board({ cards: { a: card }, positions: { a: { x: 2000, y: 2000 } } }),
      ),
    );
    store.drag("a", { x: edge, y: edge });
    server.send(
      snapshot(
        board({
          cards: { a: card, b: card },
          positions: { a: { x: 2000, y: 2000 } },
        }),
      ),
    );
    expect(cardsOf(store)).toEqual([
      ["a", { x: edge, y: edge }],
      ["b", { x: edge + short.width + gap, y: edge }],
    ]);
    store.drop("a", { x: edge, y: edge });
    expect(server.bodies()).toEqual([
      { kind: "place", id: "b", x: edge + short.width + gap, y: edge },
      { kind: "move", id: "a", x: edge, y: edge },
    ]);
  });

  it("keeps a placed card where the user dropped it when the server confirms the page's place after the drop", () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(snapshot(board({ cards: { b: card } })));
    const dropAt = { x: 500, y: 600 };
    store.drop("b", dropAt);
    server.send(
      snapshot(
        board({ cards: { b: card }, positions: { b: { x: edge, y: edge } } }),
      ),
    );
    expect(cardsOf(store)).toEqual([["b", dropAt]]);
    server.send(
      snapshot(board({ cards: { b: card }, positions: { b: dropAt } })),
    );
    expect(cardsOf(store)).toEqual([["b", dropAt]]);
    expect(server.bodies().map(({ kind }) => kind)).toEqual(["place", "move"]);
  });

  it("packs a card the agent restores without a place into the view and tells the server", () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(
      snapshot(
        board({
          cards: { a: card },
          positions: { a: { x: edge, y: edge } },
          history: { b: [{ card, threads: {} }] },
        }),
      ),
    );
    server.send(
      snapshot(
        board({
          cards: { a: card, b: card },
          positions: { a: { x: edge, y: edge } },
          history: { b: [{ card, threads: {} }] },
        }),
      ),
    );
    const beside = { x: edge + short.width + gap, y: edge };
    expect(cardsOf(store)[1]).toEqual(["b", beside]);
    expect(server.bodies()).toEqual([{ kind: "place", id: "b", ...beside }]);
  });

  it("packs the user's new card like any arrival once the server refuses the move that was to put it where the user wanted", async () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(snapshot(board({})));
    const at = { x: 300, y: 400 };
    const creating = store.create("a", "1. parse", at);
    server.sent[0]?.answer(true);
    await expect(creating).resolves.toBe(true);
    server.sent[1]?.answer(false);
    await new Promise((settled) => setTimeout(settled));
    server.send(snapshot(board({ cards: { a: card } })));
    expect(cardsOf(store)).toEqual([["a", { x: edge, y: edge }]]);
    expect(server.bodies()[2]).toEqual({
      kind: "place",
      id: "a",
      x: edge,
      y: edge,
    });
  });

  it("gives every tab the server's place once one tab's place wins, dropping its own", () => {
    const server = serve();
    const store = createBoardStore(measureShort, pageSurface, server.open);
    store.open();
    server.send(snapshot(board({ cards: { b: card } })));
    expect(cardsOf(store)).toEqual([["b", { x: edge, y: edge }]]);
    const theirs = { x: 700, y: 64 };
    server.send(
      snapshot(board({ cards: { b: card }, positions: { b: theirs } })),
    );
    expect(cardsOf(store)).toEqual([["b", theirs]]);
    server.send(
      snapshot(
        board({ cards: { b: card, c: card }, positions: { b: theirs } }),
      ),
    );
    expect(cardsOf(store)[1]).toEqual(["c", { x: edge, y: edge }]);
  });
});
