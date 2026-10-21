import { useEffect, useState } from "react";
import { z } from "zod";

import { openBoardSocket } from "~/api/boardSocket";
import type { TBoardSocket } from "~/api/boardSocket";
import type { TBoard } from "~/schemas/board";

export const ConnectionStatus = z.enum(["connecting", "live", "closed"]);

export type TConnection =
  | { status: typeof ConnectionStatus.enum.connecting }
  | {
      status: typeof ConnectionStatus.enum.live;
      board: TBoard;
      act: TBoardSocket["act"];
    }
  | { status: typeof ConnectionStatus.enum.closed };

/** The board from the server, replaced each time the agent changes it. `act` exists only while live. */
export const useBoard = (): TConnection => {
  const [connection, setConnection] = useState<TConnection>({
    status: ConnectionStatus.enum.connecting,
  });

  useEffect(() => {
    const socket = openBoardSocket(
      (board) => {
        setConnection({
          status: ConnectionStatus.enum.live,
          board,
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
