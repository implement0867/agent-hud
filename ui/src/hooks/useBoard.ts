import { useEffect, useState } from "react";
import { z } from "zod";

import { openBoardSocket } from "~/api/boardSocket";
import type { TBoardSocket } from "~/api/boardSocket";
import type { TSnapshot } from "~/schemas/events";

export const ConnectionStatus = z.enum(["connecting", "live", "closed"]);

export type TConnection =
  | { status: typeof ConnectionStatus.enum.connecting }
  | {
      status: typeof ConnectionStatus.enum.live;
      snapshot: TSnapshot;
      act: TBoardSocket["act"];
    }
  | { status: typeof ConnectionStatus.enum.closed };

/** The last snapshot from the server: the board, the agent's state and the user's unsent actions. `act` exists only while live. */
export const useBoard = (): TConnection => {
  const [connection, setConnection] = useState<TConnection>({
    status: ConnectionStatus.enum.connecting,
  });

  useEffect(() => {
    const socket = openBoardSocket(
      (snapshot) => {
        setConnection({
          status: ConnectionStatus.enum.live,
          snapshot,
          act: socket.act,
        });
      },
      () => {
        setConnection({ status: ConnectionStatus.enum.closed });
      },
    );
    return socket.close;
  }, []);

  return connection;
};
