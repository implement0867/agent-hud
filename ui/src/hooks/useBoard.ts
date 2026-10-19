import { useEffect, useState } from "react";

import { invariant } from "~/lib/invariant";
import { boardSchema } from "~/schemas/board";
import type { Board } from "~/schemas/board";

export type Connection =
  | { status: "connecting" }
  | { status: "live"; board: Board }
  | { status: "closed" };

/** The board from the server, replaced each time the agent changes it. */
export const useBoard = (): Connection => {
  const [connection, setConnection] = useState<Connection>({
    status: "connecting",
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
        const board = boardSchema.parse(JSON.parse(event.data));
        setConnection({ status: "live", board });
      },
      { signal },
    );
    socket.addEventListener(
      "close",
      () => {
        setConnection({ status: "closed" });
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
