import { z } from "zod";

export const cardSchema = z.strictObject({ md: z.string().min(1) });

export const boardSchema = z.strictObject({
  cards: z.record(z.string(), cardSchema),
});

export type Card = z.infer<typeof cardSchema>;
export type Board = z.infer<typeof boardSchema>;
