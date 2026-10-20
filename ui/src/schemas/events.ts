import { z } from "zod";

import { boardSchema } from "~/schemas/board";

export const EventKind = z.enum([
  "board_changed",
  "message_sent",
  "message_received",
]);

export const messageSchema = z.string().regex(/\S/);

const boardChangedSchema = z.strictObject({
  kind: z.literal(EventKind.enum.board_changed),
  board: boardSchema,
});

const messageReceivedSchema = z.strictObject({
  kind: z.literal(EventKind.enum.message_received),
});

export const serverEventSchema = z.discriminatedUnion("kind", [
  boardChangedSchema,
  messageReceivedSchema,
]);

export const messageSentSchema = z.strictObject({
  kind: z.literal(EventKind.enum.message_sent),
  message: messageSchema,
});
