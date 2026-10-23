import { Check, CircleHelp, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Author } from "~/schemas/actions";
import type { TAuthor, TReaction } from "~/schemas/actions";
import type { TThread } from "~/schemas/board";

export const reactionIcons: Record<TReaction, LucideIcon> = {
  approve: Check,
  reject: X,
  question: CircleHelp,
};

export const reactionKeys: Record<TReaction, string> = {
  approve: "a",
  reject: "r",
  question: "q",
};

export const reactionTones: Record<TReaction, string> = {
  approve: "bg-emerald-100 text-emerald-700",
  reject: "bg-rose-100 text-rose-700",
  question: "bg-amber-100 text-amber-700",
};

/** The reaction of each author on the thread. */
export const reactionsOf = (
  thread: TThread | undefined,
): [TAuthor, TReaction][] =>
  Author.options.flatMap((author) => {
    const reaction = thread?.reactions[author];
    return reaction === undefined ? [] : [[author, reaction]];
  });

/** The user's reaction on the thread, which the page's buttons set and clear. */
export const userReaction = (thread: TThread | undefined): TReaction | null =>
  thread?.reactions.user ?? null;
