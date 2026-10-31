import { createContext } from "react";

import type { TCardFolds } from "~/lib/folds";

/** Flips the box whose markdown runs from start to end. */
export type TToggleBox = (start: number, end: number) => void;

/** The open card's flip of its boxes; an earlier version's boxes have no range, so nothing flips them. */
export const BoxToggleContext = createContext<TToggleBox>(() => undefined);

/** The open card's folds; an earlier version has no sections, so no heading or section reads them. */
export const FoldContext = createContext<TCardFolds>({
  label: "",
  toggleCard: () => undefined,
  sections: [],
  toggleSection: () => undefined,
});
