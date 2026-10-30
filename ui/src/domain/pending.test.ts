import { describe, expect, it } from "vitest";

import { groupPending, unsentOf } from "~/domain/pending";
import { ActionKind, Author } from "~/domain/actions";
import type { TBoard } from "~/domain/board";
import type { THeard } from "~/domain/events";

const board: TBoard = {
  cards: {
    checklist: {
      md: "| | Task |\n|---|---|\n| [ ] | Build the UI |",
      author: Author.enum.agent,
      edited: false,
    },
    plan: {
      md: "# The plan\n\n1. parse\n2. render",
      author: "agent",
      edited: false,
    },
  },
  threads: {
    t1: {
      card: "plan",
      quote: "parse",
      occurrence: 0,
      comments: [
        {
          id: "a3",
          author: "user",
          text: "which parser?",
          thread: "t1",
          at: null,
        },
      ],
    },
  },
  arrows: {},
  messages: [
    { id: "a3", author: "user", text: "which parser?", thread: "t1", at: null },
  ],
  positions: {},
  sizes: {},
  history: {},
};

let count = 0;
const heard = (body: THeard["body"], id?: string): THeard => ({
  id: id ?? `a${String((count += 10))}`,
  author: Author.enum.user,
  body,
});

describe("groupPending", () => {
  it("reads a comment as its text under its words, and opens its thread", () => {
    const [group] = groupPending(
      [
        heard(
          {
            kind: ActionKind.enum.comment,
            card: "plan",
            quote: "parse",
            text: "which parser?",
          },
          "a3",
        ),
      ],
      board,
    );
    expect(group?.title).toBe("The plan");
    expect(group?.lines[0]).toMatchObject({
      what: "“which parser?”",
      where: "parse",
      card: "plan",
      thread: "t1",
    });
  });

  it("groups the actions by card in the order of the first on each, and puts messages under Chat", () => {
    const groups = groupPending(
      [
        heard({
          kind: ActionKind.enum.comment,
          card: "plan",
          quote: "",
          text: "fine",
        }),
        heard({ kind: ActionKind.enum.post, text: "go ahead" }),
        heard({ kind: "edit", id: "checklist", diff: "-| [ ] |\n+| [x] |" }),
        heard({
          kind: ActionKind.enum.link,
          id: "why",
          card: "plan",
          quote: "render",
          dst: "checklist",
          text: "",
        }),
      ],
      board,
    );
    expect(groups.map(({ title, lines }) => [title, lines.length])).toEqual([
      ["The plan", 2],
      ["Chat", 1],
      ["Task", 1],
    ]);
    expect(groups[0]?.lines.map(({ what, where }) => [what, where])).toEqual([
      ["“fine”", "the card"],
      ["arrow to Task", "render"],
    ]);
    expect(groups[1]?.lines[0]).toMatchObject({
      what: "go ahead",
      where: "",
      card: null,
    });
  });

  it("titles a new note by its first line and keeps one line per action, so the count and the list agree", () => {
    const pending = [
      heard({
        kind: ActionKind.enum.put,
        id: "note-1",
        md: "check the docs\n\nand the tests",
      }),
      heard({ kind: ActionKind.enum.remove, id: "plan" }),
    ];
    const groups = groupPending(pending, board);
    expect(groups.flatMap(({ lines }) => lines)).toHaveLength(pending.length);
    expect(groups[0]).toMatchObject({
      title: "note-1",
      lines: [{ what: "new note", where: "check the docs" }],
    });
    expect(groups[1]).toMatchObject({
      title: "The plan",
      lines: [{ what: "removed" }],
    });
  });
});

describe("unsentOf", () => {
  it("has the cards with an unsent put or edit, and every action's id", () => {
    const pending = [
      heard({
        kind: ActionKind.enum.comment,
        card: "plan",
        quote: "",
        text: "hi",
      }),
      heard({ kind: ActionKind.enum.put, id: "note-1", md: "hi" }),
      heard({ kind: "edit", id: "checklist", diff: "" }),
      heard({ kind: ActionKind.enum.post, text: "go" }),
    ];
    const { cards, ids } = unsentOf(pending);
    expect([...cards]).toEqual(["note-1", "checklist"]);
    expect(ids).toEqual(new Set(pending.map(({ id }) => id)));
  });
});
