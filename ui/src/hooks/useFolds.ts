import { useCallback, useEffect, useMemo, useState } from "react";

import { boardInUrl } from "~/data/boards";
import { versionsOf } from "~/domain/board";
import type { TBoard } from "~/domain/board";
import {
  findHeldFolds,
  foldsSchema,
  isAllOpen,
  pruneSectionFolds,
  toggleCardFold,
  toggleSectionFold,
} from "~/lib/folds";
import type { TFolds } from "~/lib/folds";
import { readKept, writeKept } from "~/lib/kept";
import { listSectionKeys } from "~/lib/sections";

/**
 * The folds of the card on this board, which the browser keeps, with toggles of the card and of a section; the agent's
 * next version of the card opens it. A toggle forgets the folds of sections the card no longer has.
 */
export const useFolds = (id: string, md: string, board: TBoard) => {
  const key = `agent-hud:folds:${boardInUrl() ?? ""}:${id}`;
  const [kept, setKept] = useState(() => readKept(key, foldsSchema));
  const folds = useMemo(
    () => findHeldFolds(kept, board, id),
    [kept, board, id],
  );
  useEffect(() => {
    writeKept(key, kept === null || isAllOpen(kept) ? null : kept);
  }, [key, kept]);
  /** The held folds of the card now, without those of sections it no longer has. */
  const findPrunedFolds = useCallback(
    (current: TFolds | null) =>
      pruneSectionFolds(findHeldFolds(current, board, id), listSectionKeys(md)),
    [board, id, md],
  );
  const toggleCard = useCallback(() => {
    setKept((current) =>
      toggleCardFold(findPrunedFolds(current), versionsOf(board, id)),
    );
  }, [findPrunedFolds, board, id]);
  const toggleSection = useCallback(
    (section: string) => {
      setKept((current) =>
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
