// Mirrors the server models; protocol/fixtures/*.json keeps both sides in step.
import { z } from "zod";

export const ElementId = z.string().regex(/^[A-Za-z][A-Za-z0-9_-]{0,31}$/);
export const Author = z.enum(["agent", "user"]);
export const Reaction = z.enum(["approve", "reject", "question"]);
export const CellValue = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.null(),
]);

export const Comment = z.strictObject({
  id: z.string(),
  author: Author,
  text: z.string().min(1),
  seq: z.number().int().nonnegative(),
});

export const Feedback = z.strictObject({
  reaction: Reaction.nullable(),
  revised: z.boolean(),
  comments: z.array(Comment),
});

const base = {
  id: ElementId,
  author: Author,
  /** Keyed by anchor; the empty key is the whole element. */
  feedback: z.record(z.string(), Feedback),
};

const box = {
  ...base,
  title: z.string(),
  x: z.number().nullable(),
  y: z.number().nullable(),
  w: z.number().positive().nullable(),
};

export const TextEl = z.strictObject({
  ...box,
  kind: z.literal("text"),
  body: z.string(),
});

export const ListItem = z.strictObject({
  id: z.string(),
  author: Author,
  text: z.string(),
});

export const ListEl = z.strictObject({
  ...box,
  kind: z.literal("list"),
  ordered: z.boolean(),
  items: z.array(ListItem),
});

export const ColumnType = z.enum([
  "static",
  "text",
  "check",
  "number",
  "select",
]);

export const Column = z.strictObject({
  key: z.string(),
  title: z.string(),
  type: ColumnType,
  options: z.array(z.string()),
});

export const Row = z.strictObject({
  id: z.string(),
  author: Author,
  cells: z.record(z.string(), CellValue),
});

/** Columns typed other than `static` take user input. */
export const TableEl = z.strictObject({
  ...box,
  kind: z.literal("table"),
  columns: z.array(Column),
  rows: z.array(Row),
});

export const AnchorRef = z.strictObject({
  id: ElementId,
  anchor: z.string(),
});

export const LinkEl = z.strictObject({
  ...base,
  kind: z.literal("link"),
  src: AnchorRef,
  dst: AnchorRef,
  text: z.string(),
});

export const Element = z.discriminatedUnion("kind", [
  TextEl,
  ListEl,
  TableEl,
  LinkEl,
]);

export const Status = z.strictObject({
  waiting: z.boolean(),
  pending: z.number().int().nonnegative(),
  viewers: z.number().int().nonnegative(),
});

export const ServerMsg = z.discriminatedUnion("t", [
  z.strictObject({
    t: z.literal("hello"),
    project: z.string(),
    elements: z.array(Element),
    status: Status,
  }),
  z.strictObject({ t: z.literal("upsert"), element: Element }),
  z.strictObject({ t: z.literal("gone"), id: ElementId }),
  z.strictObject({ t: z.literal("status"), status: Status }),
  z.strictObject({ t: z.literal("error"), message: z.string() }),
]);

const target = { id: ElementId, anchor: z.string() };

export const ClientMsg = z.discriminatedUnion("t", [
  z.strictObject({
    t: z.literal("move"),
    id: ElementId,
    x: z.number(),
    y: z.number(),
  }),
  z.strictObject({
    t: z.literal("place"),
    id: ElementId,
    x: z.number(),
    y: z.number(),
  }),
  z.strictObject({
    t: z.literal("resize"),
    id: ElementId,
    w: z.number().positive(),
  }),
  z.strictObject({
    t: z.literal("react"),
    ...target,
    reaction: Reaction.nullable(),
  }),
  z.strictObject({
    t: z.literal("comment"),
    ...target,
    text: z.string().min(1),
  }),
  z.strictObject({ t: z.literal("uncomment"), ...target, cid: z.string() }),
  z.strictObject({ t: z.literal("edit"), ...target, value: CellValue }),
  z.strictObject({ t: z.literal("add"), id: ElementId, value: z.string() }),
  z.strictObject({ t: z.literal("remove"), ...target }),
  z.strictObject({
    t: z.literal("note"),
    x: z.number(),
    y: z.number(),
    text: z.string().min(1),
  }),
  z.strictObject({
    t: z.literal("link"),
    src: AnchorRef,
    dst: AnchorRef,
    text: z.string(),
  }),
  z.strictObject({ t: z.literal("delete"), id: ElementId }),
  z.strictObject({ t: z.literal("submit"), message: z.string() }),
]);

export type Author = z.infer<typeof Author>;
export type Reaction = z.infer<typeof Reaction>;
export type CellValue = z.infer<typeof CellValue>;
export type Comment = z.infer<typeof Comment>;
export type Feedback = z.infer<typeof Feedback>;
export type TextEl = z.infer<typeof TextEl>;
export type ListEl = z.infer<typeof ListEl>;
export type ListItem = z.infer<typeof ListItem>;
export type Column = z.infer<typeof Column>;
export type TableEl = z.infer<typeof TableEl>;
export type ColumnType = z.infer<typeof ColumnType>;
export type Row = z.infer<typeof Row>;
export type AnchorRef = z.infer<typeof AnchorRef>;
export type LinkEl = z.infer<typeof LinkEl>;
export type Element = z.infer<typeof Element>;
export type ElementKind = Element["kind"];
export type BoxEl = Exclude<Element, LinkEl>;
export type Status = z.infer<typeof Status>;
export type ServerMsg = z.infer<typeof ServerMsg>;
export type ClientMsg = z.infer<typeof ClientMsg>;
