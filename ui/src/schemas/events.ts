import { z } from "zod";

import { boardSchema } from "~/schemas/board";

export const EventKind = z.enum([
  "view_changed",
  "message_sent",
  "message_received",
]);

export const messageSchema = z.string().regex(/\S/);

export const Turn = z.enum(["agent", "user"]);

export const viewSchema = z.strictObject({ board: boardSchema, turn: Turn });

export type TTurn = z.infer<typeof Turn>;
export type TView = z.infer<typeof viewSchema>;

const viewChangedSchema = z.strictObject({
  kind: z.literal(EventKind.enum.view_changed),
  view: viewSchema,
});

const messageReceivedSchema = z.strictObject({
  kind: z.literal(EventKind.enum.message_received),
});

export const serverEventSchema = z.discriminatedUnion("kind", [
  viewChangedSchema,
  messageReceivedSchema,
]);

export const messageSentSchema = z.strictObject({
  kind: z.literal(EventKind.enum.message_sent),
  message: messageSchema,
});
