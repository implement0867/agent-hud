import { z } from "zod";

export const Author = z.enum(["agent", "user"]);
export const Reaction = z.enum(["approve", "reject", "question"]);
export const ActionKind = z.enum([
  "put",
  "remove",
  "react",
  "unreact",
  "comment",
  "say",
  "fill",
]);

export const valueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.null(),
]);

export const messageSchema = z.string().regex(/\S/);

export const bodySchema = z.discriminatedUnion("kind", [
  z.strictObject({
    kind: z.literal(ActionKind.enum.put),
    id: z.string(),
    md: z.string().min(1),
  }),
  z.strictObject({ kind: z.literal(ActionKind.enum.remove), id: z.string() }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.react),
    ref: z.string(),
    reaction: Reaction,
  }),
  z.strictObject({ kind: z.literal(ActionKind.enum.unreact), ref: z.string() }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.comment),
    ref: z.string(),
    text: messageSchema,
  }),
  z.strictObject({ kind: z.literal(ActionKind.enum.say), text: messageSchema }),
  z.strictObject({
    kind: z.literal(ActionKind.enum.fill),
    ref: z.string(),
    value: valueSchema,
  }),
]);

export const requestSchema = z.strictObject({
  id: z.string(),
  body: bodySchema,
});

export type TReaction = z.infer<typeof Reaction>;
export type TBody = z.infer<typeof bodySchema>;
export type TValue = z.infer<typeof valueSchema>;
