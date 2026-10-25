import { z } from "zod";

export const Author = z
  .enum(["agent", "user"])
  .describe("Who made a card, a reaction, a comment, an arrow or a message");

export const Reaction = z
  .enum(["approve", "reject", "question"])
  .describe("An author's reaction to a card or a part");

export const ActionKind = z
  .enum([
    "put",
    "remove",
    "restore",
    "react",
    "unreact",
    "comment",
    "say",
    "fill",
    "link",
    "unlink",
    "move",
    "resize",
    "place",
    "clear",
    "send",
  ])
  .describe("What an action does to the board");

export const valueSchema = z
  .union([z.string(), z.number(), z.boolean(), z.null()])
  .describe(
    "The value of an input cell: text, a number, true or false, or one of the options; null when the cell is empty",
  );

export const messageSchema = z
  .string()
  .regex(/\S/)
  .describe("A chat message or a comment, with text that is not all space");

export const bodySchema = z.discriminatedUnion("kind", [
  z.strictObject({
    kind: z.literal(ActionKind.enum.put),
    id: z.string().describe("Card id, such as plan"),
    md: z.string().min(1).describe("Markdown shown on the card"),
    version: z
      .number()
      .int()
      .nonnegative()
      .nullish()
      .describe(
        "The number of earlier versions the card has; the put is refused when the card has another number. Null or missing replaces whatever is there, as for a new note",
      ),
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.remove),
    id: z.string().describe("Card id"),
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.restore),
    id: z.string().describe("Id of a removed card"),
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.react),
    ref: z.string().describe("The card or part reacted to, such as plan/2"),
    reaction: Reaction,
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.unreact),
    ref: z.string().describe("The card or part whose reaction goes"),
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.comment),
    ref: z.string().describe("The card or part commented on"),
    text: messageSchema,
  }),
  z.strictObject({ kind: z.literal(ActionKind.enum.say), text: messageSchema }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.fill),
    ref: z.string().describe("A cell of an input column, such as plan/3/2"),
    value: valueSchema,
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.link),
    id: z.string().describe("Arrow id"),
    src: z.string().describe("The card or part the arrow starts at"),
    dst: z.string().describe("The card or part the arrow points to"),
    text: z.string().describe("Text on the arrow"),
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.unlink),
    id: z.string().describe("Arrow id"),
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.move),
    id: z.string().describe("Card id"),
    x: z.number().describe("Left edge of the card on the board, in pixels"),
    y: z.number().describe("Top edge of the card on the board, in pixels"),
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.resize),
    id: z.string().describe("Card id"),
    width: z
      .number()
      .positive()
      .describe("Width of the card on the board, in pixels"),
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.place),
    id: z.string().describe("Id of a card that has no place yet"),
    x: z.number().describe("Left edge of the card on the board, in pixels"),
    y: z.number().describe("Top edge of the card on the board, in pixels"),
  }),
  z.strictObject({ kind: z.literal(ActionKind.enum.clear) }),
  z.strictObject({ kind: z.literal(ActionKind.enum.send) }),
]);

export const requestSchema = z.strictObject({
  id: z.string().describe("The request's id, which the server's answer names"),
  body: bodySchema,
});

export type TAuthor = z.infer<typeof Author>;
export type TReaction = z.infer<typeof Reaction>;
export type TBody = z.infer<typeof bodySchema>;
export type TValue = z.infer<typeof valueSchema>;
