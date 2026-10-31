import { useCallback, useMemo, useState } from "react";

import { versionsOf } from "~/domain/board";
import type { TBoard } from "~/domain/board";
import {
  findHeldFolds,
  pruneSectionFolds,
  toggleCardFold,
  toggleSectionFold,
} from "~/lib/folds";
import type { TFolds } from "~/lib/folds";
import { listSectionKeys } from "~/lib/sections";

/**
 * The folds of the card, with toggles of the card and of a section. The page holds them while it is open, as the card's
 * frame stays mounted over the board's snapshots, and forgets them on a reload; the server never sees them. The agent's
 * next version of the card opens it, and a toggle forgets the folds of sections the card no longer has.
 */
export const useFolds = (id: string, md: string, board: TBoard) => {
  const [last, setLast] = useState<TFolds | null>(null);
  const folds = useMemo(
    () => findHeldFolds(last, board, id),
    [last, board, id],
  );
  /** The held folds of the card now, without those of sections it no longer has. */
  const findPrunedFolds = useCallback(
    (current: TFolds | null) =>
      pruneSectionFolds(findHeldFolds(current, board, id), listSectionKeys(md)),
    [board, id, md],
  );
  const toggleCard = useCallback(() => {
    setLast((current) =>
      toggleCardFold(findPrunedFolds(current), versionsOf(board, id)),
    );
  }, [findPrunedFolds, board, id]);
  const toggleSection = useCallback(
    (section: string) => {
      setLast((current) =>
        toggleSectionFold(
          findPrunedFolds(current),
          versionsOf(board, id),
          section,
        ),
      );
    },
    [findPrunedFolds, board, id],
  );
  return { folds, toggleCard, toggleSection };
};
