import { z } from "zod";

import { boardSchema } from "~/schemas/board";

export const EventKind = z.enum(["snapshot", "accepted", "rejected"]);

export const serverEventSchema = z.discriminatedUnion("kind", [
  z.strictObject({
    kind: z.literal(EventKind.enum.snapshot),
    board: boardSchema,
  }),
  z.strictObject({ kind: z.literal(EventKind.enum.accepted), id: z.string() }),
  z.strictObject({
    kind: z.literal(EventKind.enum.rejected),
    id: z.string(),
    reason: z.string(),
  }),
]);
