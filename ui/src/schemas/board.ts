import { z } from "zod";

export const Reaction = z.enum(["approve", "reject", "question"]);

export const cardSchema = z.strictObject({
  md: z.string().min(1),
  reaction: Reaction.nullable(),
  comments: z.array(z.string()),
});

export const boardSchema = z.strictObject({
  cards: z.record(z.string(), cardSchema),
});

export type TReaction = z.infer<typeof Reaction>;
export type TCard = z.infer<typeof cardSchema>;
export type TBoard = z.infer<typeof boardSchema>;
