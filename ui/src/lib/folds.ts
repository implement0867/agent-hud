import { Author } from "~/domain/actions";
import { findVersionWriter } from "~/domain/board";
import type { TBoard } from "~/domain/board";

/**
 * What the user folded on a card, which the page holds until it reloads and the server never sees: the card as a
 * whole, which then shows its first line, and its sections by key. The folds hold until the agent writes a version of
 * the card.
 */
export type TFolds = {
  /** The card's number of earlier versions when the user last folded or opened a part of it. */
  versions: number;
  /** Whether the card shows its first line alone. */
  card: boolean;
  /** The keys of the sections that show their heading alone. */
  sections: string[];
};

/** The folds that still hold on the card: the user's last ones, unless the agent wrote a version since; else all open. */
export const findHeldFolds = (
  last: TFolds | null,
  board: TBoard,
  id: string,
): TFolds => {
  const earlier = board.history[id] ?? [];
  const open = { versions: earlier.length, card: false, sections: [] };
  const card = board.cards[id];
  if (last === null || card === undefined || last.versions > earlier.length)
    return open;
  const since = [...earlier.map((version) => version.card), card].slice(
    last.versions + 1,
  );
  return since.some(
    (version) => findVersionWriter(version) === Author.enum.agent,
  )
    ? open
    : last;
};

/** The folds without the sections the card no longer has, whose headings the user or the agent changed. */
export const pruneSectionFolds = (
  folds: TFolds,
  keys: readonly string[],
): TFolds => ({
  ...folds,
  sections: folds.sections.filter((key) => keys.includes(key)),
});

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
