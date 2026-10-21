import { z } from "zod";

export const Reaction = z.enum(["approve", "reject", "question"]);

export const cardSchema = z.strictObject({
  md: z.string().min(1),
  items: z.array(
    z.strictObject({
      id: z.string(),
      md: z.string().min(1),
      reaction: Reaction.nullable(),
    }),
  ),
  reaction: Reaction.nullable(),
  comments: z.array(z.strictObject({ id: z.string(), text: z.string() })),
});

export const boardSchema = z.strictObject({
  cards: z.record(z.string(), cardSchema),
});

export type TReaction = z.infer<typeof Reaction>;
export type TCard = z.infer<typeof cardSchema>;
export type TBoard = z.infer<typeof boardSchema>;
