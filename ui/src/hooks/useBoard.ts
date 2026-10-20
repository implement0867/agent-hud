import { useEffect, useState } from "react";
import { z } from "zod";

import { invariant } from "~/lib/invariant";
import type { TBoard } from "~/schemas/board";
import { EventKind, boardChangedSchema } from "~/schemas/events";
import type { TMessageSent } from "~/schemas/events";

export const ConnectionStatus = z.enum(["connecting", "live", "closed"]);

export type TConnection =
  | { status: typeof ConnectionStatus.enum.connecting }
  | {
      status: typeof ConnectionStatus.enum.live;
      board: TBoard;
      send: (message: string) => void;
    }
  | { status: typeof ConnectionStatus.enum.closed };

/** The board from the server, replaced each time the agent changes it. `send` exists only while live. */
export const useBoard = (): TConnection => {
  const [connection, setConnection] = useState<TConnection>({
    status: ConnectionStatus.enum.connecting,
  });

  useEffect(() => {
    const url = new URL("/ws", window.location.href);
    url.protocol = "ws:";
    const socket = new WebSocket(url);
    const listening = new AbortController();
    const { signal } = listening;
    const send = (message: string) => {
      const event: TMessageSent = {
        kind: EventKind.enum.message_sent,
        message,
      };
      socket.send(JSON.stringify(event));
    };
    socket.addEventListener(
      "message",
      (event: MessageEvent<unknown>) => {
        invariant(typeof event.data === "string", "the server sends text");
        const { board } = boardChangedSchema.parse(JSON.parse(event.data));
        setConnection({ status: ConnectionStatus.enum.live, board, send });
      },
      { signal },
    );
    socket.addEventListener(
      "close",
      () => {
        setConnection({ status: ConnectionStatus.enum.closed });
      },
      { signal },
    );
    return () => {
      listening.abort();
      socket.close();
    };
  }, []);

  return connection;
};
