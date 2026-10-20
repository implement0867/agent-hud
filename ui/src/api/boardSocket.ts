import { assertNever } from "~/lib/assertNever";
import { invariant } from "~/lib/invariant";
import {
  EventKind,
  messageSentSchema,
  serverEventSchema,
} from "~/schemas/events";
import type { TBoard } from "~/schemas/board";

export type TBoardSocket = {
  /** Resolves true when the server confirms the message, or false when the connection closes first. */
  send: (message: string) => Promise<boolean>;
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
  // The server confirms messages in the order sent.
  const unconfirmed: ((received: boolean) => void)[] = [];
  socket.addEventListener(
    "message",
    (message: MessageEvent<unknown>) => {
      invariant(typeof message.data === "string", "the server sends text");
      const event = serverEventSchema.parse(JSON.parse(message.data));
      switch (event.kind) {
        case EventKind.enum.board_changed:
          onBoard(event.board);
          return;
        case EventKind.enum.message_received: {
          const confirm = unconfirmed.shift();
          invariant(
            confirm !== undefined,
            "the server confirms only sent messages",
          );
          confirm(true);
          return;
        }
        default:
          return assertNever(event);
      }
    },
    { signal },
  );
  socket.addEventListener(
    "close",
    () => {
      for (const confirm of unconfirmed.splice(0)) confirm(false);
      onClose();
    },
    { signal },
  );
  return {
    send: (message) => {
      const event = messageSentSchema.parse({
        kind: EventKind.enum.message_sent,
        message,
      });
      socket.send(JSON.stringify(event));
      return new Promise((resolve) => {
        unconfirmed.push(resolve);
      });
    },
    close: () => {
      listening.abort();
      socket.close();
    },
  };
};
