import { createContext, useContext } from "react";

import type { TBoardModel } from "~/data/boardModel";
import type { TBoardStore } from "~/data/boardStore";
import { threadOf } from "~/domain/board";
import type { TFeedback, TThread } from "~/domain/board";
import type { TValue } from "~/domain/actions";
import { invariant } from "~/lib/invariant";

/** The store of the board, which does not change while the page is open, for the components that act on the board. */
export const StoreContext = createContext<TBoardStore | null>(null);

export const useStore = (): TBoardStore => {
  const store = useContext(StoreContext);
  invariant(store !== null, "the board renders inside BoardProvider");
  return store;
};

/** The board below the provider's gate: the model of the last snapshot, and whether the server is away. */
export type TLiveBoard = { model: TBoardModel; offline: boolean };

export const BoardContext = createContext<TLiveBoard | null>(null);

/** The live board, for the components that render it; they render again on each change of the model. */
export const useBoard = (): TLiveBoard => {
  const board = useContext(BoardContext);
  invariant(board !== null, "the board renders inside BoardProvider");
  return board;
};

/** The feedback that the parts show: the board's, or an earlier version's in the history. */
export const FeedbackContext = createContext<TFeedback | null>(null);

const useFeedback = () => {
  const feedback = useContext(FeedbackContext);
  invariant(feedback !== null, "parts render inside BoardProvider");
  return feedback;
};

/** The thread on the ref. */
export const useThread = (ref: string): TThread => threadOf(useFeedback(), ref);

/** The value of the input cell; null when it is empty. */
export const useCellValue = (ref: string): TValue =>
  useFeedback().values[ref] ?? null;

/** Whether the parts are of an earlier version, which shows its feedback and takes no actions. */
export const ReadOnlyContext = createContext(false);

export const useReadOnly = () => useContext(ReadOnlyContext);

/** The id of the card that the parts render in. */
export const CardContext = createContext<string | null>(null);

export const useCardId = () => {
  const id = useContext(CardContext);
  invariant(id !== null, "parts render inside a card");
  return id;
};
