import { z } from "zod";

import { Author, Reaction, valueSchema } from "~/schemas/actions";

const cardSchema = z.strictObject({
  md: z.string().min(1),
  author: Author,
  edited: z.boolean(),
});

const saidSchema = z.strictObject({
  id: z.string(),
  author: Author,
  text: z.string(),
  ref: z.string().nullable(),
  at: z.string().nullable(),
});

const threadSchema = z.strictObject({
  reactions: z.partialRecord(Author, Reaction),
  comments: z.array(saidSchema),
});

const arrowSchema = z.strictObject({
  src: z.string(),
  dst: z.string(),
  text: z.string(),
  author: Author,
});

const pointSchema = z.strictObject({ x: z.number(), y: z.number() });

const versionSchema = z.strictObject({
  card: cardSchema,
  threads: z.record(z.string(), threadSchema),
  values: z.record(z.string(), valueSchema),
});

export const boardSchema = z.strictObject({
  cards: z.record(z.string(), cardSchema),
  threads: z.record(z.string(), threadSchema),
  values: z.record(z.string(), valueSchema),
  arrows: z.record(z.string(), arrowSchema),
  messages: z.array(saidSchema),
  positions: z.record(z.string(), pointSchema),
  history: z.record(z.string(), z.array(versionSchema)),
});

export type TCard = z.infer<typeof cardSchema>;
export type TArrow = z.infer<typeof arrowSchema>;
export type TPoint = z.infer<typeof pointSchema>;
export type TSaid = z.infer<typeof saidSchema>;
export type TThread = z.infer<typeof threadSchema>;
export type TVersion = z.infer<typeof versionSchema>;
export type TBoard = z.infer<typeof boardSchema>;
