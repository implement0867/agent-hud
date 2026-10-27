import { z } from "zod";

import { Author, bodySchema } from "~/domain/actions";
import { boardSchema } from "~/domain/board";

export const EventKind = z
  .enum(["snapshot", "accepted", "rejected"])
  .describe("What the server tells the page");

export const AgentState = z
  .enum(["away", "working", "waiting"])
  .describe(
    "Away: no agent's monitor is open. Working: the agent has the user's last turn. Waiting: the agent waits for the user's next turn",
  );

export const editSchema = z
  .strictObject({
    kind: z.literal("edit"),
    id: z.string().describe("Card id"),
    diff: z
      .string()
      .describe(
        "A unified diff of the card's markdown, without the file header",
      ),
  })
  .describe(
    "The user's put on a card that was on the board, as the change to its markdown",
  );

export const heardSchema = z
  .strictObject({
    id: z.string().describe("The action's id"),
    author: Author,
    body: z.discriminatedUnion("kind", [...bodySchema.options, editSchema]),
  })
  .describe("A user's action as the agent's monitor gets it");

export const snapshotSchema = z.strictObject({
  kind: z.literal(EventKind.enum.snapshot),
  board: boardSchema,
  agent: AgentState,
  pending: z
    .array(heardSchema)
    .describe("The user's turn so far, as the agent will hear it on the send"),
  unsent: z
    .number()
    .int()
    .nonnegative()
    .describe("The number of pending actions"),
  waiting: z
    .number()
    .int()
    .nonnegative()
    .describe("The user's turns that were sent and that no agent has taken"),
});

export const serverEventSchema = z.discriminatedUnion("kind", [
  snapshotSchema,
  z.strictObject({
    kind: z.literal(EventKind.enum.accepted),
    id: z.string().describe("The id of the request the board took"),
  }),
  z.strictObject({
    kind: z.literal(EventKind.enum.rejected),
    id: z.string().describe("The id of the request the board refused"),
    reason: z.string().describe("Why the board refused it"),
  }),
]);

export const boardListSchema = z
  .array(
    z.strictObject({
      name: z.string().describe("The board's name"),
      cards: z
        .number()
        .int()
        .nonnegative()
        .describe("The number of cards on it"),
      agent: AgentState,
    }),
  )
  .describe("Every board on the server, as /boards lists them");

export type TAgentState = z.infer<typeof AgentState>;
export type THeard = z.infer<typeof heardSchema>;
export type TSnapshot = z.infer<typeof snapshotSchema>;
export type TBoardList = z.infer<typeof boardListSchema>;
