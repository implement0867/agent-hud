import { z } from "zod";

import { viewSchema } from "~/schemas/view";

export const EventKind = z.enum([
  "view_changed",
  "message_sent",
  "message_received",
]);

export const messageSchema = z.string().regex(/\S/);

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
