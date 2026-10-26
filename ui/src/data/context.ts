import { createContext, useContext } from "react";

import type { TBoardModel } from "~/data/boardModel";
import type { TBoardStore } from "~/data/boardStore";
import type { TThread } from "~/domain/board";
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

/** The threads that a card shows: the board's, or an earlier version's in the history. */
export const ThreadsContext = createContext<Record<string, TThread> | null>(
  null,
);

export const useThreads = () => {
  const threads = useContext(ThreadsContext);
  invariant(threads !== null, "cards render inside BoardProvider");
  return threads;
};

/** Whether the card is an earlier version, which shows its threads and takes no actions. */
export const ReadOnlyContext = createContext(false);

export const useReadOnly = () => useContext(ReadOnlyContext);
