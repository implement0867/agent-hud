import { z } from "zod";

import { Author } from "~/domain/actions";

const cardSchema = z.strictObject({
  md: z.string().min(1).describe("Markdown shown on the card"),
  author: Author.describe("Who put the card first"),
  edited: z
    .boolean()
    .describe(
      "Whether the latest version is by the other author: the user edited the agent's card, or the agent the user's card",
    ),
});

const saidSchema = z
  .strictObject({
    id: z.string().describe("The id of the action that said it"),
    author: Author,
    text: z.string().describe("What was said"),
    thread: z
      .string()
      .nullable()
      .describe("The thread of a comment; null for a chat message"),
    at: z.string().nullable().describe("When it was said, as an ISO time"),
  })
  .describe("A chat message, or a comment in the thread that thread names");

const anchorFields = {
  card: z.string().describe("The card the words are in"),
  quote: z
    .string()
    .describe(
      "The words, as the card shows them; empty for the card as a whole",
    ),
  occurrence: z
    .number()
    .int()
    .nonnegative()
    .describe("Which place of the quote in the card's text, from 0"),
};

const threadSchema = z
  .strictObject({
    ...anchorFields,
    comments: z.array(saidSchema).describe("The comments, oldest first"),
  })
  .describe("The comments on one place of a card");

const arrowSchema = z.strictObject({
  ...anchorFields,
  dst: z.string().describe("The card the arrow points to"),
  text: z.string().describe("Text on the arrow"),
  author: Author,
});

const pointSchema = z.strictObject({
  x: z.number().describe("Left edge on the board, in pixels"),
  y: z.number().describe("Top edge on the board, in pixels"),
});

const sizeSchema = z.strictObject({
  width: z
    .number()
    .nullable()
    .describe("Width in pixels; null fits the content"),
  height: z
    .number()
    .nullable()
    .describe("Height in pixels; null fits the content"),
});

const versionSchema = z
  .strictObject({
    card: cardSchema,
    threads: z
      .record(z.string(), threadSchema)
      .describe("The threads it had, by id"),
  })
  .describe(
    "A card as it was before a put replaced it or a remove took it away, with its threads",
  );

export const boardSchema = z.strictObject({
  cards: z.record(z.string(), cardSchema).describe("Cards by id"),
  threads: z
    .record(z.string(), threadSchema)
    .describe("Threads by the id of the comment that started each"),
  arrows: z.record(z.string(), arrowSchema).describe("Arrows by id"),
  messages: z
    .array(saidSchema)
    .describe("The chat, and each comment, in order"),
  positions: z
    .record(z.string(), pointSchema)
    .describe("The place of each card that has one"),
  sizes: z
    .record(z.string(), sizeSchema)
    .describe("The size of each card that the user or the agent resized"),
  history: z
    .record(z.string(), z.array(versionSchema))
    .describe("The earlier versions of each card, oldest first"),
});

export type TCard = z.infer<typeof cardSchema>;
export type TArrow = z.infer<typeof arrowSchema>;
export type TPoint = z.infer<typeof pointSchema>;
export type TSize = z.infer<typeof sizeSchema>;
export type TSaid = z.infer<typeof saidSchema>;
export type TThread = z.infer<typeof threadSchema>;
export type TVersion = z.infer<typeof versionSchema>;
export type TBoard = z.infer<typeof boardSchema>;

/** A place in a card: words at one of the places they occur, or the card as a whole when the quote is empty. */
export type TAnchor = { card: string; quote: string; occurrence: number };

/** An id for a card, an arrow or a draft that the user makes. */
export const newId = (prefix: string) =>
  `${prefix}-${crypto.randomUUID().replaceAll("-", "").slice(0, 8)}`;

/** The number of earlier versions of the card. */
export const versionsOf = (board: TBoard, card: string) =>
  board.history[card]?.length ?? 0;

/** The threads of the card, by id, in the board's order. */
export const threadsOn = (
  threads: Record<string, TThread>,
  card: string,
): [string, TThread][] =>
  Object.entries(threads).filter(([, thread]) => thread.card === card);

/** The anchors on the card with feedback: its threads and the arrows that start at it, which a change of their words moves to the history. */
export const anchorsOn = (board: TBoard, card: string): TAnchor[] => [
  ...threadsOn(board.threads, card).map(([, thread]) => thread),
  ...Object.values(board.arrows).filter((arrow) => arrow.card === card),
];

/** Whether an earlier version of the card holds threads, which the board does not show. */
export const historyHasFeedback = (board: TBoard, card: string) =>
  (board.history[card] ?? []).some(
    (version) => Object.keys(version.threads).length > 0,
  );

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
