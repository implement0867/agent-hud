import { useEffect, useState } from "react";
import { z } from "zod";

import { openBoardSocket } from "~/api/boardSocket";
import type { TBoardSocket } from "~/api/boardSocket";
import type { TSnapshot } from "~/schemas/events";

export const ConnectionStatus = z.enum(["connecting", "live", "offline"]);

export type TConnection =
  | { status: typeof ConnectionStatus.enum.connecting }
  | {
      status: typeof ConnectionStatus.enum.live;
      snapshot: TSnapshot;
      act: TBoardSocket["act"];
    }
  /** The server went away: the last snapshot, while the page opens the socket again. */
  | { status: typeof ConnectionStatus.enum.offline; snapshot: TSnapshot };

/**
 * The last snapshot from the server: the board, the agent's state and the user's unsent actions. `act` exists only
 * while live. When the socket closes, the page opens it again after a delay that grows to ten seconds.
 */
export const useBoard = (): TConnection => {
  const [connection, setConnection] = useState<TConnection>({
    status: ConnectionStatus.enum.connecting,
  });

  useEffect(() => {
    let stopped = false;
    let delay = 1000;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let socket: TBoardSocket | undefined;
    const open = () => {
      const opened = openBoardSocket(
        (snapshot) => {
          delay = 1000;
          setConnection({
            status: ConnectionStatus.enum.live,
            snapshot,
            act: opened.act,
          });
        },
        () => {
          setConnection((current) =>
            current.status === ConnectionStatus.enum.connecting
              ? current
              : {
                  status: ConnectionStatus.enum.offline,
                  snapshot: current.snapshot,
                },
          );
          if (stopped) return;
          timer = setTimeout(open, delay);
          delay = Math.min(delay * 2, 10000);
        },
      );
      socket = opened;
    };
    open();
    return () => {
      stopped = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return connection;
};
