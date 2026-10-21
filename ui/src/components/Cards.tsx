import Markdown from "react-markdown";

import { Notice } from "~/components/Notice";
import type { TBoardSocket } from "~/api/boardSocket";
import { Reaction } from "~/schemas/board";
import type { TBoard, TCard } from "~/schemas/board";

type TReact = TBoardSocket["react"];

/** Pressing the card's reaction again clears it. */
const ReactionButtons = ({
  id,
  card,
  react,
}: {
  id: string;
  card: TCard;
  react: TReact;
}) => (
  <div className="mt-2 flex gap-1">
    {Reaction.options.map((reaction) => (
      <button
        key={reaction}
        type="button"
        className="rounded border border-stone-300 px-2 text-xs text-stone-600 hover:bg-stone-100 aria-pressed:bg-stone-800 aria-pressed:text-white"
        aria-pressed={card.reaction === reaction}
        onClick={() => {
          react(id, card.reaction === reaction ? null : reaction);
        }}
      >
        {reaction}
      </button>
    ))}
  </div>
);

const CardView = ({
  id,
  card,
  react,
}: {
  id: string;
  card: TCard;
  react: TReact;
}) => (
  <article className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
    <header className="mb-2 font-mono text-xs text-stone-400">{id}</header>
    <div className="prose prose-sm prose-stone max-w-none">
      <Markdown>{card.md}</Markdown>
    </div>
    <ReactionButtons id={id} card={card} react={react} />
  </article>
);

export const Cards = ({ board, react }: { board: TBoard; react: TReact }) => {
  const cards = Object.entries(board.cards);
  if (cards.length === 0) return <Notice>No cards yet.</Notice>;
  return cards.map(([id, card]) => (
    <CardView key={id} id={id} card={card} react={react} />
  ));
};
