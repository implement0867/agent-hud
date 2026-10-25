import { describe, expect, it } from "vitest";

import { groupPending, unsentOf } from "~/domain/pending";
import { ActionKind, Author, Reaction } from "~/domain/actions";
import type { TValue } from "~/domain/actions";
import type { TBoard } from "~/domain/board";
import type { THeard } from "~/domain/events";

const board: TBoard = {
  cards: {
    checklist: {
      md: "| Task | Owner {text} | Hours {number} | Done {check} |\n|---|---|---|---|\n| Build the UI | | | |\n| Run make check | | | |",
      author: Author.enum.agent,
      edited: false,
    },
    plan: {
      md: "# The plan\n\n1. parse\n2. render",
      author: "agent",
      edited: false,
    },
  },
  threads: {},
  values: {},
  arrows: {},
  messages: [],
  positions: {},
  widths: {},
  history: {},
};

let count = 0;
const heard = (
  body: THeard["body"],
  parts: Record<string, string> = {},
): THeard => ({
  id: `a${String((count += 1))}`,
  author: Author.enum.user,
  body,
  parts,
});

const fill = (ref: string, value: TValue) =>
  heard(
    { kind: ActionKind.enum.fill, ref, value },
    { "checklist/2": "Run make check |  |  | " },
  );

describe("groupPending", () => {
  it("reads a fill as the row's name, the column's title and the value, under the card's title", () => {
    const [group] = groupPending(
      [fill("checklist/2/2", "agent"), fill("checklist/2/3", 1)],
      board,
    );
    expect(group?.title).toBe("Task");
    expect(group?.lines.map(({ what, where }) => [where, what])).toEqual([
      ["Run make check", "Owner: agent"],
      ["Run make check", "Hours: 1"],
    ]);
    expect(group?.lines[0]?.ref).toBe("checklist/2");
  });

  it("names yes, no and cleared for a check and an empty cell", () => {
    const [group] = groupPending(
      [
        fill("checklist/2/4", true),
        fill("checklist/2/4", false),
        fill("checklist/2/2", null),
      ],
      board,
    );
    expect(group?.lines.map(({ what }) => what)).toEqual([
      "Done: yes",
      "Done: no",
      "Owner: cleared",
    ]);
  });

  it("groups the actions by card in the order of the first on each, and puts messages under Chat", () => {
    const groups = groupPending(
      [
        heard(
          {
            kind: ActionKind.enum.react,
            ref: "plan/2",
            reaction: Reaction.enum.reject,
          },
          { "plan/2": "render" },
        ),
        heard({ kind: ActionKind.enum.say, text: "go ahead" }),
        fill("checklist/2/3", 1),
        heard(
          {
            kind: ActionKind.enum.comment,
            ref: "plan/1",
            text: "which parser?",
          },
          { "plan/1": "parse" },
        ),
      ],
      board,
    );
    expect(groups.map(({ title, lines }) => [title, lines.length])).toEqual([
      ["The plan", 2],
      ["Chat", 1],
      ["Task", 1],
    ]);
    expect(groups[0]?.lines.map(({ what, where }) => [what, where])).toEqual([
      ["reject", "render"],
      ["“which parser?”", "parse"],
    ]);
    expect(groups[1]?.lines[0]).toMatchObject({
      what: "go ahead",
      where: "",
      ref: null,
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
  it("has the refs of the parts, cells and cards with an unsent action, and every action's id", () => {
    const pending = [
      heard({
        kind: ActionKind.enum.react,
        ref: "plan/2",
        reaction: Reaction.enum.approve,
      }),
      fill("checklist/2/3", 1),
      heard({ kind: ActionKind.enum.put, id: "note-1", md: "hi" }),
      heard({ kind: ActionKind.enum.say, text: "go" }),
    ];
    const { refs, ids } = unsentOf(pending);
    expect([...refs]).toEqual(["plan/2", "checklist/2/3", "note-1"]);
    expect(ids).toEqual(new Set(pending.map(({ id }) => id)));
  });
});
