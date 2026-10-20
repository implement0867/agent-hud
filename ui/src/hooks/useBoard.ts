import { useEffect, useState } from "react";
import { z } from "zod";

import { invariant } from "~/lib/invariant";
import type { TBoard } from "~/schemas/board";
import { boardEventSchema } from "~/schemas/events";

export const ConnectionStatus = z.enum(["connecting", "live", "closed"]);

export type TConnecting = {
  status: typeof ConnectionStatus.enum.connecting;
};
export type TLive = {
  status: typeof ConnectionStatus.enum.live;
  board: TBoard;
};
export type TClosed = { status: typeof ConnectionStatus.enum.closed };
export type TConnection = TConnecting | TLive | TClosed;

/** The board from the server, replaced each time the agent changes it. */
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
    socket.addEventListener(
      "message",
      (event: MessageEvent<unknown>) => {
        invariant(typeof event.data === "string", "the server sends text");
        const { board } = boardEventSchema.parse(JSON.parse(event.data));
        setConnection({ status: ConnectionStatus.enum.live, board });
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
