import { useCallback, useState } from "react";
import type { RefObject } from "react";

import { useBoard, useStore } from "~/data/context";
import { versionsOf } from "~/domain/board";
import type { TBoard } from "~/domain/board";
import { cardOf, isCardRef } from "~/domain/ref";
import { SelectionKind } from "~/hooks/useWhiteboard";
import type { TSelection } from "~/hooks/useWhiteboard";
import { anchorOf } from "~/lib/dom";
import type { TAnchor } from "~/lib/dom";
import { assertNever } from "~/lib/assertNever";
import { invariant } from "~/lib/invariant";

/** A selection with what select measured and counted: the anchor of a card or part, and its card's number of earlier versions. */
type TChosen = {
  selection: TSelection;
  anchor: TAnchor | null;
  versions: number;
};

/**
 * Whether the selection holds on the board. A card or arrow holds while it is on the board, and a part while its card
 * has the version it had when the user selected the part: a new version moves the part's feedback to the history.
 */
const holds = ({ selection, versions }: TChosen, board: TBoard) => {
  if (selection === null) return false;
  switch (selection.kind) {
    case SelectionKind.enum.ref: {
      const card = cardOf(selection.ref);
      return (
        Object.hasOwn(board.cards, card) &&
        (isCardRef(selection.ref) || versionsOf(board, card) === versions)
      );
    }
    case SelectionKind.enum.arrow:
      return Object.hasOwn(board.arrows, selection.id);
    default:
      return assertNever(selection);
  }
};

/**
 * The user's selection, the anchor of its panel, and whether the panel is open: a click on a card's header selects
 * without it, and Esc closes it before it ends the selection.
 */
export const useSelection = (world: RefObject<HTMLElement | null>) => {
  const { model } = useBoard();
  const store = useStore();
  const [chosen, setChosen] = useState<TChosen>({
    selection: null,
    anchor: null,
    versions: 0,
  });
  const [feedbackOpen, setFeedbackOpen] = useState(true);

  const select = useCallback(
    (selection: TSelection, feedback = true) => {
      setFeedbackOpen(feedback);
      if (selection?.kind !== SelectionKind.enum.ref) {
        setChosen({ selection, anchor: null, versions: 0 });
        return;
      }
      const root = world.current;
      invariant(root !== null, "parts render in the world");
      setChosen({
        selection,
        anchor: anchorOf(root, selection.ref),
        versions: versionsOf(store.read().board, cardOf(selection.ref)),
      });
    },
    [world, store],
  );

  /** Ends the selection of the arrow, if the user has not selected something else since, as when the arrow is removed. */
  const deselectArrow = useCallback((id: string) => {
    setChosen((current) =>
      current.selection?.kind === SelectionKind.enum.arrow &&
      current.selection.id === id
        ? { selection: null, anchor: null, versions: 0 }
        : current,
    );
  }, []);

  const holding = holds(chosen, model.board);
  return {
    selection: holding ? chosen.selection : null,
    anchor: holding ? chosen.anchor : null,
    feedbackOpen,
    setFeedbackOpen,
    select,
    deselectArrow,
  };
};
