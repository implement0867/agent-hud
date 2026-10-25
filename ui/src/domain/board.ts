import { z } from "zod";

import { Author, Reaction, valueSchema } from "~/domain/actions";
import { cardOf, rowOf } from "~/domain/ref";

const cardSchema = z.strictObject({
  md: z.string().min(1).describe("Markdown shown on the card"),
  author: Author.describe("Who put the card first"),
  edited: z
    .boolean()
    .describe(
      "Whether the latest version is by the other author: the user edited the agent's card, or the agent the user's note",
    ),
});

const saidSchema = z
  .strictObject({
    id: z.string().describe("The id of the action that said it"),
    author: Author,
    text: z.string().describe("What was said"),
    ref: z
      .string()
      .nullable()
      .describe("The card or part a comment is on; null for a chat message"),
    at: z.string().nullable().describe("When it was said, as an ISO time"),
  })
  .describe("A chat message, or a comment on the part that ref names");

const threadSchema = z
  .strictObject({
    reactions: z
      .partialRecord(Author, Reaction)
      .describe("The reaction of each author"),
    comments: z.array(saidSchema).describe("The comments, oldest first"),
  })
  .describe("The reaction of each author and the comments on one ref");

const arrowSchema = z.strictObject({
  src: z.string().describe("The card or part the arrow starts at"),
  dst: z.string().describe("The card or part the arrow points to"),
  text: z.string().describe("Text on the arrow"),
  author: Author,
});

const pointSchema = z.strictObject({
  x: z.number().describe("Left edge on the board, in pixels"),
  y: z.number().describe("Top edge on the board, in pixels"),
});

const versionSchema = z
  .strictObject({
    card: cardSchema,
    threads: z.record(z.string(), threadSchema).describe("Threads by ref"),
    values: z
      .record(z.string(), valueSchema)
      .describe("Values of input cells by cell ref"),
  })
  .describe(
    "A card as it was before a put replaced it or a remove took it away, with its feedback",
  );

export const boardSchema = z.strictObject({
  cards: z.record(z.string(), cardSchema).describe("Cards by id"),
  threads: z.record(z.string(), threadSchema).describe("Threads by ref"),
  values: z
    .record(z.string(), valueSchema)
    .describe("Values of input cells by cell ref"),
  arrows: z.record(z.string(), arrowSchema).describe("Arrows by id"),
  messages: z
    .array(saidSchema)
    .describe("The chat, and each comment on a part, in order"),
  positions: z
    .record(z.string(), pointSchema)
    .describe("The place of each card that has one"),
  widths: z
    .record(z.string(), z.number())
    .describe(
      "The width of each card that the user or the agent resized, in pixels",
    ),
  history: z
    .record(z.string(), z.array(versionSchema))
    .describe("The earlier versions of each card, oldest first"),
});

export type TCard = z.infer<typeof cardSchema>;
export type TArrow = z.infer<typeof arrowSchema>;
export type TPoint = z.infer<typeof pointSchema>;
export type TSaid = z.infer<typeof saidSchema>;
export type TThread = z.infer<typeof threadSchema>;
export type TVersion = z.infer<typeof versionSchema>;
export type TBoard = z.infer<typeof boardSchema>;

/** The threads and values that the parts of a card show: the board's, or an earlier version's. */
export type TFeedback = Pick<TBoard, "threads" | "values">;

const emptyThread: TThread = { reactions: {}, comments: [] };

/** The thread on the ref; a ref without reactions or comments has an empty one. */
export const threadOf = (feedback: TFeedback, ref: string): TThread =>
  feedback.threads[ref] ?? emptyThread;

/** An id for a card, an arrow or a draft that the user makes. */
export const newId = (prefix: string) =>
  `${prefix}-${crypto.randomUUID().replaceAll("-", "").slice(0, 8)}`;

/** The number of earlier versions of the card. */
export const versionsOf = (board: TBoard, card: string) =>
  board.history[card]?.length ?? 0;

/**
 * The refs on the card that have reactions, comments, values or arrow ends: the feedback that a change of their text
 * moves to the history.
 */
export const refsWithFeedback = (board: TBoard, card: string): string[] => {
  const refs = new Set([
    ...Object.entries(board.threads)
      .filter(
        ([, thread]) =>
          thread.comments.length > 0 ||
          Object.keys(thread.reactions).length > 0,
      )
      .map(([ref]) => ref),
    ...Object.keys(board.values).map(rowOf),
    ...Object.values(board.arrows).flatMap((arrow) => [arrow.src, arrow.dst]),
  ]);
  return [...refs].filter((ref) => cardOf(ref) === card);
};

/** An earlier version of a card, numbered from 1; the last version of a card that is not on the board is removed. */
export type TEarlierVersion = {
  card: string;
  number: number;
  version: TVersion;
  removed: boolean;
};

/** The earlier versions of the card, or of every card when card is null, newest first for each card. */
export const earlierVersions = (
  board: TBoard,
  card: string | null,
): TEarlierVersion[] =>
  (card === null ? Object.keys(board.history) : [card]).flatMap((id) => {
    const versions = board.history[id] ?? [];
    return versions
      .map((version, index) => ({
        card: id,
        number: index + 1,
        version,
        removed:
          !Object.hasOwn(board.cards, id) && index === versions.length - 1,
      }))
      .toReversed();
  });
