import { createContext, useContext } from "react";

import type { TBoardModel } from "~/data/boardModel";
import type { TBoardStore } from "~/data/boardStore";
import { threadOf } from "~/domain/board";
import type { TFeedback, TThread } from "~/domain/board";
import type { TValue } from "~/domain/actions";
import { invariant } from "~/lib/invariant";

/** The board below the provider's gate: the model of the last snapshot, whether the server is away, and the store. */
export type TLiveBoard = {
  model: TBoardModel;
  offline: boolean;
  store: TBoardStore;
};

export const BoardContext = createContext<TLiveBoard | null>(null);

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
