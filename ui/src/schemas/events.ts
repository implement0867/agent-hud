import { z } from "zod";

import { boardSchema } from "~/schemas/board";

export const EventKind = z.enum(["snapshot", "accepted", "rejected"]);

/** Away: no agent's monitor is open. Working: the agent has the user's last turn. Waiting: the agent waits for the user's next turn. */
export const AgentState = z.enum(["away", "working", "waiting"]);

export const snapshotSchema = z.strictObject({
  kind: z.literal(EventKind.enum.snapshot),
  board: boardSchema,
  agent: AgentState,
  unsent: z.number().int().nonnegative(),
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
export type TSnapshot = z.infer<typeof snapshotSchema>;
