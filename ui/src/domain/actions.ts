import { z } from "zod";

export const Author = z
  .enum(["agent", "user"])
  .describe("Who made a card, a comment, an arrow or a message");

export const ActionKind = z
  .enum([
    "put",
    "remove",
    "restore",
    "comment",
    "post",
    "link",
    "unlink",
    "move",
    "resize",
    "place",
    "clear",
    "send",
  ])
  .describe("What an action does to the board");

export const quoteSchema = z
  .string()
  .describe(
    "Words of a card as the card shows them, without markdown; empty for the card as a whole",
  );

export const occurrenceSchema = z
  .number()
  .int()
  .nonnegative()
  .nullish()
  .describe("Which place of the quote in the card's text, from 0");

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
    kind: z.literal(ActionKind.enum.comment),
    card: z.string().describe("The card commented on"),
    quote: quoteSchema,
    occurrence: occurrenceSchema,
    text: messageSchema,
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.post),
    text: messageSchema,
  }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.link),
    id: z.string().describe("Arrow id"),
    card: z.string().describe("The card the arrow starts at"),
    quote: quoteSchema,
    occurrence: occurrenceSchema,
    dst: z.string().describe("The card the arrow points to"),
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
      .optional()
      .describe("Width of the card on the board, in pixels"),
    height: z
      .number()
      .positive()
      .optional()
      .describe("Height of the card on the board, in pixels"),
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
export type TBody = z.infer<typeof bodySchema>;
