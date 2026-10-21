import { assertNever } from "~/lib/assertNever";
import { invariant } from "~/lib/invariant";
import {
  EventKind,
  commentAddedSchema,
  itemReactionSetSchema,
  messageSentSchema,
  reactionSetSchema,
  serverEventSchema,
} from "~/schemas/events";
import type { TBoard, TReaction } from "~/schemas/board";

export type TBoardSocket = {
  /** Resolves true when the server confirms the message, or false when the connection closes first. */
  send: (message: string) => Promise<boolean>;
  /** The page gets the board with the reaction on the card. */
  react: (id: string, reaction: TReaction | null) => void;
  /** The page gets the board with the reaction on the card's item of that number, from 1. */
  reactToItem: (id: string, item: number, reaction: TReaction | null) => void;
  /** The page gets the board with the comment on the card. */
  comment: (id: string, text: string) => void;
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
    react: (id, reaction) => {
      const event = reactionSetSchema.parse({
        kind: EventKind.enum.reaction_set,
        id,
        reaction,
      });
      socket.send(JSON.stringify(event));
    },
    reactToItem: (id, item, reaction) => {
      const event = itemReactionSetSchema.parse({
        kind: EventKind.enum.item_reaction_set,
        id,
        item,
        reaction,
      });
      socket.send(JSON.stringify(event));
    },
    comment: (id, text) => {
      const event = commentAddedSchema.parse({
        kind: EventKind.enum.comment_added,
        id,
        text,
      });
      socket.send(JSON.stringify(event));
    },
    close: () => {
      listening.abort();
      socket.close();
    },
  };
};
