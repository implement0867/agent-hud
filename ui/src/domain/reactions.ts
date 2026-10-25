import { z } from "zod";

import { ActionKind, Author, Reaction } from "~/domain/actions";
import type { TAuthor, TBody, TReaction } from "~/domain/actions";
import type { TThread } from "~/domain/board";

/** The key that sets each reaction on the selection. */
export const reactionKeys: Record<TReaction, string> = {
  approve: "a",
  reject: "r",
  question: "q",
};

/** The reactions with a button on each part; a question wants words, so it is set in the thread. */
export const quickReactions = Reaction.options.filter(
  (option) => option !== Reaction.enum.question,
);

/** The reaction of each author on the thread. */
export const reactionsOf = (thread: TThread): [TAuthor, TReaction][] =>
  Author.options.flatMap((author) => {
    const reaction = thread.reactions[author];
    return reaction === undefined ? [] : [[author, reaction]];
  });

/** The user's reaction on the thread, which the page's buttons set and clear. */
export const userReaction = (thread: TThread): TReaction | null =>
  thread.reactions.user ?? null;

/** The action that sets the user's reaction on the ref, or clears it when the user has that reaction there. */
export const toggleReaction = (
  thread: TThread,
  ref: string,
  reaction: TReaction,
): TBody =>
  userReaction(thread) === reaction
    ? { kind: ActionKind.enum.unreact, ref }
    : { kind: ActionKind.enum.react, ref, reaction };

export const TallyKind = z
  .enum([...Reaction.options, "comments"])
  .describe("A kind of feedback that the toolbar counts");

export type TTallyKind = z.infer<typeof TallyKind>;

/** The refs with each kind of feedback, by either author, in the board's order. */
export const tally = (
  threads: Record<string, TThread>,
): Record<TTallyKind, string[]> => {
  const entries = Object.entries(threads);
  const withReaction = (reaction: TReaction) =>
    entries
      .filter(([, thread]) =>
        reactionsOf(thread).some(([, reacted]) => reacted === reaction),
      )
      .map(([ref]) => ref);
  return {
    approve: withReaction(Reaction.enum.approve),
    reject: withReaction(Reaction.enum.reject),
    question: withReaction(Reaction.enum.question),
    comments: entries
      .filter(([, thread]) => thread.comments.length > 0)
      .map(([ref]) => ref),
  };
};
