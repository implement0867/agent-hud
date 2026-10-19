import { ClientMsg, ServerMsg } from "~/protocol/schema";
import { boardStore, reduceBoard } from "~/store/board";
import type { Connection } from "~/store/board";

export type Socket = {
  send: (msg: ClientMsg) => void;
  close: () => void;
};

const setConnection = (connection: Connection) => {
  boardStore.set((s) =>
    s.connection === connection ? s : { ...s, connection },
  );
};

const reportError = (message: string) => {
  boardStore.set((s) => ({ ...s, error: { message, at: Date.now() } }));
};

/** Keep one websocket open to the server, reconnecting with backoff. */
export const connect = (url: string): Socket => {
  let ws: WebSocket | null = null;
  let retry = 0;
  let closed = false;
  let timer: number | undefined;

  const open = () => {
    setConnection("connecting");
    const socket = new WebSocket(url);
    ws = socket;
    socket.addEventListener("open", () => {
      retry = 0;
      setConnection("open");
    });
    socket.addEventListener("message", (event: MessageEvent<unknown>) => {
      if (typeof event.data !== "string") return;
      const parsed = ServerMsg.safeParse(JSON.parse(event.data));
      if (!parsed.success) {
        reportError(`Unexpected message from server: ${parsed.error.message}`);
        return;
      }
      boardStore.set((s) => reduceBoard(s, parsed.data));
    });
    socket.addEventListener("close", () => {
      ws = null;
      setConnection("closed");
      if (closed) return;
      retry += 1;
      timer = window.setTimeout(open, Math.min(500 * 2 ** retry, 8000));
    });
  };

  open();
  return {
    send: (msg) => {
      const checked = ClientMsg.parse(msg);
      if (ws?.readyState !== WebSocket.OPEN) {
        reportError("Not connected; the change was not sent");
        return;
      }
      ws.send(JSON.stringify(checked));
    },
    close: () => {
      closed = true;
      window.clearTimeout(timer);
      ws?.close();
    },
  };
};

export const socketUrl = (): string => {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}/ws`;
};
