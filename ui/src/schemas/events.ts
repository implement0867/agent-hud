import { z } from "zod";

import { boardSchema } from "~/schemas/board";

export const EventKind = z.enum(["board"]);

export const boardEventSchema = z.strictObject({
  kind: z.literal(EventKind.enum.board),
  board: boardSchema,
});
