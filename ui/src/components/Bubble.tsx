import { Bot, User } from "lucide-react";

import { useBoard } from "~/data/context";
import { Author } from "~/domain/actions";
import type { TSaid } from "~/domain/board";
import { short } from "~/domain/text";
import { useWhiteboard } from "~/hooks/useWhiteboard";

type TBubbleProps = { said: TSaid };

/** The look of a bubble by who said it and whether the agent has it: the user's unsent words are outlined, not filled, until Send. */
const bubbleTone = (mine: boolean, unsent: boolean) => {
  if (!mine) return "rounded-bl-sm bg-surface-sunken text-ink";
  return unsent
    ? "rounded-br-sm bg-surface text-accent-strong outline-1 outline-accent outline-dashed -outline-offset-1"
    : "rounded-br-sm bg-accent text-on-accent";
};

/**
 * A message or comment, with the time it was said on hover; a comment starts with the words of its thread, which open
 * the thread. The user's words that the agent does not have yet are outlined and say so.
 */
export const Bubble = ({ said }: TBubbleProps) => {
  const { model } = useBoard();
  const { show } = useWhiteboard();
  const thread =
    said.thread === null ? undefined : model.board.threads[said.thread];
  const mine = said.author === Author.enum.user;
  const unsent = mine && model.unsent.ids.has(said.id);
  const Icon = mine ? User : Bot;
  return (
    <li
      className={`flex items-end gap-1.5 ${mine ? "flex-row-reverse" : ""}`}
      title={
        unsent
          ? "Not sent yet"
          : said.at === null
            ? undefined
            : new Date(said.at).toLocaleString()
      }
      data-unsent={unsent ? "" : undefined}
    >
      <span
        className={`grid size-5 shrink-0 place-items-center rounded-full ${mine ? "bg-accent-soft text-accent-strong" : "bg-outline text-ink-soft"}`}
      >
        <Icon className="size-3" />
      </span>
      <span
        className={`max-w-[85%] rounded-2xl px-3 py-1.5 text-lg whitespace-pre-wrap ${bubbleTone(mine, unsent)}`}
      >
        {thread !== undefined && said.thread !== null && (
          <button
            type="button"
            aria-label={`Show the thread on ${thread.quote === "" ? thread.card : `“${short(thread.quote)}”`}`}
            title={thread.quote === "" ? thread.card : thread.quote}
            className="mr-1.5 inline-block max-w-48 truncate rounded-sm bg-ink/10 px-1 align-bottom text-sm"
            onClick={() => {
              show(thread.card, said.thread);
            }}
          >
            “{thread.quote === "" ? thread.card : short(thread.quote)}”
          </button>
        )}
        {said.text}
        {unsent ? (
          <span className="ml-1.5 text-xs text-accent-strong/70">unsent</span>
        ) : null}
      </span>
    </li>
  );
};
