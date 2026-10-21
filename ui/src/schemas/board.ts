import { z } from "zod";

export const Reaction = z.enum(["approve", "reject", "question"]);

const commentSchema = z.strictObject({ id: z.string(), text: z.string() });

const itemSchema = z.strictObject({
  reaction: Reaction.nullable(),
  comments: z.array(commentSchema),
});

export const cardSchema = z.strictObject({
  md: z.string().min(1),
  items: z.record(z.string(), itemSchema),
  reaction: Reaction.nullable(),
  comments: z.array(commentSchema),
});

export const boardSchema = z.strictObject({
  cards: z.record(z.string(), cardSchema),
});

export type TReaction = z.infer<typeof Reaction>;
export type TCard = z.infer<typeof cardSchema>;
export type TBoard = z.infer<typeof boardSchema>;
