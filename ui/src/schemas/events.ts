import { z } from "zod";

import { Reaction, boardSchema } from "~/schemas/board";

export const EventKind = z.enum([
  "board_changed",
  "message_sent",
  "message_received",
  "reaction_set",
  "comment_added",
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

export const reactionSetSchema = z.strictObject({
  kind: z.literal(EventKind.enum.reaction_set),
  id: z.string(),
  reaction: Reaction.nullable(),
});

export const commentAddedSchema = z.strictObject({
  kind: z.literal(EventKind.enum.comment_added),
  id: z.string(),
  text: messageSchema,
});
