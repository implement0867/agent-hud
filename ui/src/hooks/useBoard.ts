import { useEffect, useState } from "react";
import { z } from "zod";

import { openBoardSocket } from "~/api/boardSocket";
import type { TBoardSocket } from "~/api/boardSocket";
import type { TView } from "~/schemas/events";

export const ConnectionStatus = z.enum(["connecting", "live", "closed"]);

export type TConnection =
  | { status: typeof ConnectionStatus.enum.connecting }
  | {
      status: typeof ConnectionStatus.enum.live;
      view: TView;
      send: TBoardSocket["send"];
    }
  | { status: typeof ConnectionStatus.enum.closed };

/** The view from the server, replaced on each change. `send` exists only while live. */
export const useBoard = (): TConnection => {
  const [connection, setConnection] = useState<TConnection>({
    status: ConnectionStatus.enum.connecting,
  });

  useEffect(() => {
    const socket = openBoardSocket(
      (view) => {
        setConnection({
          status: ConnectionStatus.enum.live,
          view,
          send: socket.send,
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
