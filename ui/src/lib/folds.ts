import { z } from "zod";

import { Author } from "~/domain/actions";
import type { TBoard, TCard } from "~/domain/board";
import { assertNever } from "~/lib/assertNever";

/**
 * What the user folded on a card, which the browser keeps and the server never sees: the card as a whole, which then
 * shows its first line, and its sections by key. The folds hold until the agent writes a version of the card.
 */
export const foldsSchema = z.object({
  versions: z
    .number()
    .int()
    .nonnegative()
    .describe(
      "The card's number of earlier versions when the user last folded or opened a part of it",
    ),
  card: z.boolean().describe("Whether the card shows its first line alone"),
  sections: z
    .array(z.string())
    .describe("The keys of the sections that show their heading alone"),
});

export type TFolds = z.infer<typeof foldsSchema>;

/** Who wrote the card's version: its first author, or the other author when the version is an edit by the other. */
const findWriter = (card: TCard) => {
  if (!card.edited) return card.author;
  switch (card.author) {
    case Author.enum.agent:
      return Author.enum.user;
    case Author.enum.user:
      return Author.enum.agent;
    default:
      return assertNever(card.author);
  }
};

/** The folds that still hold on the card: the kept ones, unless the agent wrote a version since; else all open. */
export const findHeldFolds = (
  kept: TFolds | null,
  board: TBoard,
  id: string,
): TFolds => {
  const earlier = board.history[id] ?? [];
  const open = { versions: earlier.length, card: false, sections: [] };
  const card = board.cards[id];
  if (kept === null || card === undefined || kept.versions > earlier.length)
    return open;
  const since = [...earlier.map((version) => version.card), card].slice(
    kept.versions + 1,
  );
  return since.some((version) => findWriter(version) === Author.enum.agent)
    ? open
    : kept;
};

/** Whether the folds fold nothing, which the browser need not keep. */
export const isAllOpen = (folds: TFolds) =>
  !folds.card && folds.sections.length === 0;

/** The folds with the card folded, or opened when it was folded, as of the card's versions now. */
export const toggleCardFold = (folds: TFolds, versions: number): TFolds => ({
  ...folds,
  versions,
  card: !folds.card,
});

/** The folds with the section folded, or opened when it was folded, as of the card's versions now. */
export const toggleSectionFold = (
  folds: TFolds,
  versions: number,
  section: string,
): TFolds => ({
  ...folds,
  versions,
  sections: folds.sections.includes(section)
    ? folds.sections.filter((key) => key !== section)
    : [...folds.sections, section],
});
