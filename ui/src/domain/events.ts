import { z } from "zod";

import { ActionKind, Author, bodySchema } from "~/domain/actions";
import { boardSchema } from "~/domain/board";
import { assertNever } from "~/lib/assertNever";

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
    parts: z
      .record(z.string(), z.string())
      .describe(
        "The text of each part that the action names, as it was when the user acted",
      ),
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
      id: z.string().describe("Board id: a project's, or shared"),
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

/** One line for a pending action, as the agent will hear it. */
export const describeHeard = ({ body, parts }: THeard): string => {
  const text = (ref: string) => {
    const part = parts[ref];
    return part === undefined ? ref : `${ref} "${part}"`;
  };
  switch (body.kind) {
    case ActionKind.enum.put:
      return `new note ${body.id}`;
    case "edit":
      return `edit ${body.id}`;
    case ActionKind.enum.remove:
      return `remove ${body.id}`;
    case ActionKind.enum.restore:
      return `restore ${body.id}`;
    case ActionKind.enum.react:
      return `${body.reaction} ${text(body.ref)}`;
    case ActionKind.enum.unreact:
      return `no reaction on ${text(body.ref)}`;
    case ActionKind.enum.comment:
      return `comment on ${text(body.ref)}: ${body.text}`;
    case ActionKind.enum.say:
      return body.text;
    case ActionKind.enum.fill:
      return `${body.ref} = ${JSON.stringify(body.value)}`;
    case ActionKind.enum.link:
      return `arrow ${body.src} → ${body.dst}${body.text === "" ? "" : ` "${body.text}"`}`;
    case ActionKind.enum.unlink:
      return `remove arrow ${body.id}`;
    case ActionKind.enum.move:
      return `move ${body.id}`;
    case ActionKind.enum.resize:
      return `resize ${body.id}`;
    case ActionKind.enum.place:
      return `place ${body.id}`;
    case ActionKind.enum.clear:
      return "clear the board";
    case ActionKind.enum.send:
      return "send";
    default:
      return assertNever(body);
  }
};
