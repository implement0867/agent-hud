import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type { ReactNode } from "react";

import { ConnectionStatus, createBoardStore } from "~/data/boardStore";
import { BoardContext, FeedbackContext, StoreContext } from "~/data/context";

type TBoardProviderProps = { children: ReactNode };

/** Holds the connection to the board; the children render once the first snapshot is in, and see the board live or offline. */
export const BoardProvider = ({ children }: TBoardProviderProps) => {
  const [store] = useState(createBoardStore);
  useEffect(() => store.open(), [store]);
  const connection = useSyncExternalStore(store.subscribe, store.getConnection);
  const live = useMemo(
    () =>
      connection.status === ConnectionStatus.enum.connecting
        ? null
        : {
            model: connection.model,
            offline: connection.status === ConnectionStatus.enum.offline,
          },
    [connection],
  );
  if (live === null)
    return <p className="m-auto text-ink-muted">Connecting to the board…</p>;
  return (
    <StoreContext value={store}>
      <BoardContext value={live}>
        <FeedbackContext value={live.model.board}>{children}</FeedbackContext>
      </BoardContext>
    </StoreContext>
  );
};
