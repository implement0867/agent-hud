import { describe, expect, it } from "vitest";

import type { TBoard, TCard } from "~/domain/board";
import {
  findHeldFolds,
  pruneSectionFolds,
  toggleCardFold,
  toggleSectionFold,
} from "~/lib/folds";
import type { TFolds } from "~/lib/folds";

const agentCard: TCard = { md: "# Plan", author: "agent", edited: false };
const userEdit: TCard = {
  md: "# Plan\n\nMine.",
  author: "agent",
  edited: true,
};

/** A board with the one card plan, whose versions are the earlier ones and then the card. */
const makeBoard = (versions: TCard[]): TBoard => {
  const card = versions.at(-1);
  if (card === undefined) throw new Error("a card has a version");
  return {
    cards: { plan: card },
    threads: {},
    arrows: {},
    messages: [],
    positions: {},
    sizes: {},
    history: {
      plan: versions.slice(0, -1).map((version) => ({
        card: version,
        threads: {},
      })),
    },
  };
};

const folded: TFolds = { versions: 0, card: true, sections: ["0:Steps"] };

describe("findHeldFolds", () => {
  it("opens all of a card the user never folded", () => {
    expect(findHeldFolds(null, makeBoard([agentCard]), "plan")).toEqual({
      versions: 0,
      card: false,
      sections: [],
    });
  });

  it("holds the folds while the card has the version they were made on", () => {
    expect(findHeldFolds(folded, makeBoard([agentCard]), "plan")).toBe(folded);
  });

  it("holds the folds over the user's own edits", () => {
    expect(
      findHeldFolds(folded, makeBoard([agentCard, userEdit, userEdit]), "plan"),
    ).toBe(folded);
  });

  it("opens the card when the agent writes a version after the folds", () => {
    expect(
      findHeldFolds(
        folded,
        makeBoard([agentCard, userEdit, agentCard]),
        "plan",
      ),
    ).toEqual({ versions: 2, card: false, sections: [] });
  });

  it("opens the card when the agent's version came before the user's last edit", () => {
    expect(
      findHeldFolds(folded, makeBoard([agentCard, agentCard, userEdit]), "plan")
        .card,
    ).toBe(false);
  });

  it("opens a card that has fewer versions than the folds, as after a clear", () => {
    expect(
      findHeldFolds({ ...folded, versions: 3 }, makeBoard([agentCard]), "plan")
        .card,
    ).toBe(false);
  });
});

describe("toggleCardFold and toggleSectionFold", () => {
  const open: TFolds = { versions: 0, card: false, sections: [] };

  it("fold and open again, as of the versions now", () => {
    const once = toggleSectionFold(toggleCardFold(open, 2), 3, "0:Steps");
    expect(once).toEqual({ versions: 3, card: true, sections: ["0:Steps"] });
    const back = toggleSectionFold(toggleCardFold(once, 3), 3, "0:Steps");
    expect(back).toEqual({ versions: 3, card: false, sections: [] });
  });
});

describe("pruneSectionFolds", () => {
  it("forgets the folds of sections the card no longer has", () => {
    expect(
      pruneSectionFolds(
        { versions: 1, card: false, sections: ["0:Steps", "0:Gone"] },
        ["0:Plan", "0:Steps"],
      ).sections,
    ).toEqual(["0:Steps"]);
  });
});
