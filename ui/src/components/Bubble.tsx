import { Bot, User } from "lucide-react";

import { useBoard } from "~/data/context";
import { Author } from "~/domain/actions";
import type { TSaid } from "~/domain/board";
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

/** A message or comment, with the time it was said on hover; with its ref, a comment starts with a link to the part it is on. */
export const Bubble = ({ said, withRef = false }: TBubbleProps) => {
  const { show } = useWhiteboard();
  const mine = said.author === Author.enum.user;
  const Icon = mine ? User : Bot;
  const ref = withRef ? said.ref : null;
  return (
    <li
      className={`flex items-end gap-1.5 ${mine ? "flex-row-reverse" : ""}`}
      title={said.at === null ? undefined : new Date(said.at).toLocaleString()}
    >
      <span
        className={`grid size-5 shrink-0 place-items-center rounded-full ${mine ? "bg-accent-soft text-accent-strong" : "bg-outline text-ink-soft"}`}
      >
        <Icon className="size-3" />
      </span>
      <span
        className={`max-w-[85%] rounded-2xl px-3 py-1.5 text-sm whitespace-pre-wrap ${mine ? "rounded-br-sm bg-accent text-white" : "rounded-bl-sm bg-surface-sunken text-ink"}`}
      >
        {ref !== null && (
          <button
            type="button"
            aria-label={`Show ${ref}`}
            className="mr-1.5 rounded bg-black/10 px-1 font-mono text-[11px]"
            onClick={() => {
              show(ref);
            }}
          >
            {ref}
          </button>
        )}
        <RefText text={said.text} />
      </span>
    </li>
  );
};
