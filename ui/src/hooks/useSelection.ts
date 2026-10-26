import { useCallback, useState } from "react";

import { useBoard, useStore } from "~/data/context";
import { versionsOf } from "~/domain/board";
import type { TBoard } from "~/domain/board";
import { SelectionKind } from "~/hooks/useWhiteboard";
import type { TSelection } from "~/hooks/useWhiteboard";
import { assertNever } from "~/lib/assertNever";

/** A selection with its card's number of earlier versions when it was made, and the thread a comment just started. */
type TChosen = {
  selection: TSelection;
  versions: number;
  awaiting: string | null;
};

/**
 * Whether the selection holds on the board. A card, a thread or an arrow holds while it is on the board, and a thread
 * that a comment of this page just started holds until the board has it. The words of a new thread hold while their
 * card has the version it had: a new version may not have them.
 */
const holds = ({ selection, versions, awaiting }: TChosen, board: TBoard) => {
  if (selection === null) return false;
  switch (selection.kind) {
    case SelectionKind.enum.card:
      return Object.hasOwn(board.cards, selection.id);
    case SelectionKind.enum.thread:
      return (
        Object.hasOwn(board.threads, selection.id) || awaiting === selection.id
      );
    case SelectionKind.enum.draft:
      return (
        Object.hasOwn(board.cards, selection.anchor.card) &&
        versionsOf(board, selection.anchor.card) === versions
      );
    case SelectionKind.enum.arrow:
      return Object.hasOwn(board.arrows, selection.id);
    default:
      return assertNever(selection);
  }
};

/** The user's selection on the board, which ends when what it names leaves the board. */
export const useSelection = () => {
  const { model } = useBoard();
  const store = useStore();
  const [chosen, setChosen] = useState<TChosen>({
    selection: null,
    versions: 0,
    awaiting: null,
  });

  const select = useCallback(
    (selection: TSelection) => {
      const card =
        selection?.kind === SelectionKind.enum.draft
          ? selection.anchor.card
          : null;
      setChosen({
        selection,
        versions: card === null ? 0 : versionsOf(store.read().board, card),
        awaiting: null,
      });
    },
    [store],
  );

  /** Opens the thread that the comment with the id started, which the board may not have yet. */
  const started = useCallback((id: string) => {
    setChosen({
      selection: { kind: SelectionKind.enum.thread, id },
      versions: 0,
      awaiting: id,
    });
  }, []);

  /** Ends the selection of the arrow, if the user has not selected something else since, as when the arrow is removed. */
  const deselectArrow = useCallback((id: string) => {
    setChosen((current) =>
      current.selection?.kind === SelectionKind.enum.arrow &&
      current.selection.id === id
        ? { selection: null, versions: 0, awaiting: null }
        : current,
    );
  }, []);

  return {
    selection: holds(chosen, model.board) ? chosen.selection : null,
    select,
    started,
    deselectArrow,
  };
};
