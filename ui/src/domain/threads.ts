import { Author } from "~/domain/actions";
import type { TThread } from "~/domain/board";

/**
 * The comments of the thread the user has read: the number kept when the user last opened it, or, before that, the
 * comments up to the user's own last one.
 */
export const readOf = (thread: TThread, seen: number | undefined) =>
  seen ??
  thread.comments.findLastIndex((said) => said.author === Author.enum.user) + 1;

/** The agent's comments that came after the ones the user read. */
export const unreadOf = (thread: TThread, seen: number | undefined) =>
  thread.comments
    .slice(readOf(thread, seen))
    .filter((said) => said.author === Author.enum.agent).length;
