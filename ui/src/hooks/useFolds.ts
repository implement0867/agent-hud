import { useCallback, useEffect, useMemo, useState } from "react";

import { boardInUrl } from "~/data/boards";
import { versionsOf } from "~/domain/board";
import type { TBoard } from "~/domain/board";
import {
  findHeldFolds,
  foldsSchema,
  isAllOpen,
  toggleCardFold,
  toggleSectionFold,
} from "~/lib/folds";
import { readKept, writeKept } from "~/lib/kept";

/**
 * The folds of the card on this board, which the browser keeps, with toggles of the card and of a section; the agent's
 * next version of the card opens it.
 */
export const useFolds = (id: string, board: TBoard) => {
  const key = `agent-hud:folds:${boardInUrl() ?? ""}:${id}`;
  const [kept, setKept] = useState(() => readKept(key, foldsSchema));
  const folds = useMemo(
    () => findHeldFolds(kept, board, id),
    [kept, board, id],
  );
  useEffect(() => {
    writeKept(key, kept === null || isAllOpen(kept) ? null : kept);
  }, [key, kept]);
  const toggleCard = useCallback(() => {
    setKept((current) =>
      toggleCardFold(findHeldFolds(current, board, id), versionsOf(board, id)),
    );
  }, [board, id]);
  const toggleSection = useCallback(
    (section: string) => {
      setKept((current) =>
        toggleSectionFold(
          findHeldFolds(current, board, id),
          versionsOf(board, id),
          section,
        ),
      );
    },
    [board, id],
  );
  return { folds, toggleCard, toggleSection };
};
