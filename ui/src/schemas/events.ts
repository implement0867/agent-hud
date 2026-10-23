import { z } from "zod";

import { Author, bodySchema } from "~/schemas/actions";
import { boardSchema } from "~/schemas/board";

export const EventKind = z.enum(["snapshot", "accepted", "rejected"]);

/** Away: no agent's monitor is open. Working: the agent has the user's last turn. Waiting: the agent waits for the user's next turn. */
export const AgentState = z.enum(["away", "working", "waiting"]);

/** The user's put on a card that was on the board, as the agent hears it: a diff of the markdown. */
export const editSchema = z.strictObject({
  kind: z.literal("edit"),
  id: z.string(),
  diff: z.string(),
});

/** A user's action as the agent's monitor gets it, with the text of each part it names. */
export const heardSchema = z.strictObject({
  id: z.string(),
  author: Author,
  body: z.discriminatedUnion("kind", [...bodySchema.options, editSchema]),
  parts: z.record(z.string(), z.string()),
});

export const snapshotSchema = z.strictObject({
  kind: z.literal(EventKind.enum.snapshot),
  board: boardSchema,
  agent: AgentState,
  pending: z.array(heardSchema),
  unsent: z.number().int().nonnegative(),
  waiting: z.number().int().nonnegative(),
});

export const serverEventSchema = z.discriminatedUnion("kind", [
  snapshotSchema,
  z.strictObject({ kind: z.literal(EventKind.enum.accepted), id: z.string() }),
  z.strictObject({
    kind: z.literal(EventKind.enum.rejected),
    id: z.string(),
    reason: z.string(),
  }),
]);

export type TAgentState = z.infer<typeof AgentState>;
export type THeard = z.infer<typeof heardSchema>;
export type TSnapshot = z.infer<typeof snapshotSchema>;
