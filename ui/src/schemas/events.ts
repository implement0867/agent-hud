import { z } from "zod";

import { boardSchema } from "~/schemas/board";

export const EventKind = z.enum(["board", "send"]);

export const boardEventSchema = z.strictObject({
  kind: z.literal(EventKind.enum.board),
  board: boardSchema,
});

export const sendEventSchema = z.strictObject({
  kind: z.literal(EventKind.enum.send),
  message: z.string(),
});

export type TSendEvent = z.infer<typeof sendEventSchema>;
