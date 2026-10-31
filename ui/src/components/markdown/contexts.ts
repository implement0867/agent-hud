import { createContext, useContext } from "react";

import type { TCardFolds } from "~/lib/folds";
import { invariant } from "~/lib/invariant";

/** Flips the box whose markdown runs from start to end. */
export type TToggleBox = (start: number, end: number) => void;

export const BoxToggleContext = createContext<TToggleBox | null>(null);

/** The open card's flip of its boxes. */
export const useBoxToggle = (): TToggleBox => {
  const toggle = useContext(BoxToggleContext);
  invariant(toggle !== null, "an open card's boxes render inside CardBody");
  return toggle;
};

export const FoldContext = createContext<TCardFolds | null>(null);

/** The open card's folds, for its headings and sections. */
export const useCardFolds = (): TCardFolds => {
  const folds = useContext(FoldContext);
  invariant(folds !== null, "an open card's sections render inside CardBody");
  return folds;
};
