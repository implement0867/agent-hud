import { Bot, User } from "lucide-react";

import { useBoard } from "~/data/context";
import { Author } from "~/domain/actions";
import type { TSaid } from "~/domain/board";
import { nameOf } from "~/domain/parts";
import { splitRefs } from "~/domain/ref";
import { useWhiteboard } from "~/hooks/useWhiteboard";

type TRefTextProps = { text: string };

/** The text, with each ref to a part on the board, such as plan/2, as a link that shows the part. */
const RefText = ({ text }: TRefTextProps) => {
  const { model } = useBoard();
  const { show } = useWhiteboard();
  return splitRefs(text, (card) => Object.hasOwn(model.board.cards, card)).map(
    ({ text: piece, ref, at }) =>
      ref === null ? (
        <span key={at}>{piece}</span>
      ) : (
        <button
          key={at}
          type="button"
          title={nameOf(model.board, ref)}
          className="font-mono underline decoration-dotted underline-offset-2"
          onClick={() => {
            show(ref);
          }}
        >
          {piece}
        </button>
      ),
  );
};

type TBubbleProps = { said: TSaid; withRef?: boolean };

/** The look of a bubble by who said it and whether the agent has it: the user's unsent words are outlined, not filled, until Send. */
const bubbleTone = (mine: boolean, unsent: boolean) => {
  if (!mine) return "rounded-bl-sm bg-surface-sunken text-ink";
  return unsent
    ? "rounded-br-sm bg-surface text-accent-strong outline-1 outline-accent outline-dashed -outline-offset-1"
    : "rounded-br-sm bg-accent text-white";
};

/**
 * A message or comment, with the time it was said on hover; with its ref, a comment starts with a link to the part it
 * is on. The user's words that the agent does not have yet are outlined and say so.
 */
export const Bubble = ({ said, withRef = false }: TBubbleProps) => {
  const { model } = useBoard();
  const { show } = useWhiteboard();
  const name = said.ref === null ? "" : nameOf(model.board, said.ref);
  const mine = said.author === Author.enum.user;
  const unsent = mine && model.unsent.ids.has(said.id);
  const Icon = mine ? User : Bot;
  const ref = withRef ? said.ref : null;
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
        className={`max-w-[85%] rounded-2xl px-3 py-1.5 text-sm whitespace-pre-wrap ${bubbleTone(mine, unsent)}`}
      >
        {ref !== null && (
          <button
            type="button"
            aria-label={`Show ${ref}`}
            title={ref}
            className="mr-1.5 inline-block max-w-48 truncate rounded bg-black/10 px-1 align-bottom text-[11px]"
            onClick={() => {
              show(ref);
            }}
          >
            “{name}”
          </button>
        )}
        <RefText text={said.text} />
        {unsent ? (
          <span className="ml-1.5 text-[10px] text-accent-strong/70">
            unsent
          </span>
        ) : null}
      </span>
    </li>
  );
};
