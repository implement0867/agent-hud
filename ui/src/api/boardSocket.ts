import { assertNever } from "~/lib/assertNever";
import { invariant } from "~/lib/invariant";
import { requestSchema } from "~/schemas/actions";
import type { TBody } from "~/schemas/actions";
import type { TBoard } from "~/schemas/board";
import { EventKind, serverEventSchema } from "~/schemas/events";

export type TBoardSocket = {
  /** Resolves true when the server takes the action, or false when it rejects it or the connection closes first. */
  act: (body: TBody) => Promise<boolean>;
  close: () => void;
};

/** The page's websocket. The server sends the board on connect and after each change. */
export const openBoardSocket = (
  onBoard: (board: TBoard) => void,
  onClose: () => void,
): TBoardSocket => {
  const url = new URL("/ws", window.location.href);
  url.protocol = "ws:";
  const socket = new WebSocket(url);
  const listening = new AbortController();
  const { signal } = listening;
  const pending = new Map<string, (taken: boolean) => void>();
  const settle = (id: string, taken: boolean) => {
    const resolve = pending.get(id);
    invariant(resolve !== undefined, "the server answers only sent actions");
    pending.delete(id);
    resolve(taken);
  };
  socket.addEventListener(
    "message",
    (message: MessageEvent<unknown>) => {
      invariant(typeof message.data === "string", "the server sends text");
      const event = serverEventSchema.parse(JSON.parse(message.data));
      switch (event.kind) {
        case EventKind.enum.snapshot:
          onBoard(event.board);
          return;
        case EventKind.enum.accepted:
          settle(event.id, true);
          return;
        case EventKind.enum.rejected:
          settle(event.id, false);
          return;
        default:
          return assertNever(event);
      }
    },
    { signal },
  );
  socket.addEventListener(
    "close",
    () => {
      for (const resolve of pending.values()) resolve(false);
      pending.clear();
      onClose();
    },
    { signal },
  );
  return {
    act: (body) => {
      const request = requestSchema.parse({ id: crypto.randomUUID(), body });
      socket.send(JSON.stringify(request));
      return new Promise((resolve) => {
        pending.set(request.id, resolve);
      });
    },
    close: () => {
      listening.abort();
      socket.close();
    },
  };
};
