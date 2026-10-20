import { z } from "zod";

import { boardSchema } from "~/schemas/board";

export const EventKind = z.enum(["board_changed", "message_sent"]);

export const boardChangedSchema = z.strictObject({
  kind: z.literal(EventKind.enum.board_changed),
  board: boardSchema,
});

export const messageSentSchema = z.strictObject({
  kind: z.literal(EventKind.enum.message_sent),
  message: z.string(),
});

export type TMessageSent = z.infer<typeof messageSentSchema>;
