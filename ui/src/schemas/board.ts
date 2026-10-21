import { z } from "zod";

import { Author, Reaction } from "~/schemas/actions";

const cardSchema = z.strictObject({ md: z.string().min(1), author: Author });

const saidSchema = z.strictObject({
  id: z.string(),
  author: Author,
  text: z.string(),
});

const threadSchema = z.strictObject({
  reaction: Reaction.nullable(),
  comments: z.array(saidSchema),
});

export const boardSchema = z.strictObject({
  cards: z.record(z.string(), cardSchema),
  threads: z.record(z.string(), threadSchema),
});

export type TCard = z.infer<typeof cardSchema>;
export type TSaid = z.infer<typeof saidSchema>;
export type TThread = z.infer<typeof threadSchema>;
export type TBoard = z.infer<typeof boardSchema>;
