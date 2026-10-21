import { useState } from "react";
import Markdown from "react-markdown";

import { Notice } from "~/components/Notice";
import type { TBoardSocket } from "~/api/boardSocket";
import { Reaction } from "~/schemas/board";
import type { TBoard, TCard } from "~/schemas/board";
import { messageSchema } from "~/schemas/events";

type TReact = TBoardSocket["react"];
type TComment = TBoardSocket["comment"];

/** The page clears the box when it sends the comment. */
const CommentForm = ({ id, comment }: { id: string; comment: TComment }) => {
  const [text, setText] = useState("");
  return (
    <div className="mt-2 flex gap-1">
      <input
        className="flex-1 rounded border border-stone-300 px-2 text-sm"
        placeholder="Comment"
        aria-label={`Comment on ${id}`}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
        }}
      />
      <button
        type="button"
        className="rounded border border-stone-300 px-2 text-xs text-stone-600 hover:bg-stone-100 disabled:text-stone-300"
        disabled={!messageSchema.safeParse(text).success}
        onClick={() => {
          comment(id, text);
          setText("");
        }}
      >
        Comment
      </button>
    </div>
  );
};

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
  comment,
}: {
  id: string;
  card: TCard;
  react: TReact;
  comment: TComment;
}) => (
  <article className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
    <header className="mb-2 font-mono text-xs text-stone-400">{id}</header>
    <div className="prose prose-sm prose-stone max-w-none">
      <Markdown>{card.md}</Markdown>
    </div>
    <ReactionButtons id={id} card={card} react={react} />
    <ul className="mt-2 space-y-1 text-sm text-stone-700">
      {card.comments.map(({ id, text }) => (
        <li key={id} className="rounded bg-stone-100 px-2 py-1">
          {text}
        </li>
      ))}
    </ul>
    <CommentForm id={id} comment={comment} />
  </article>
);

export const Cards = ({
  board,
  react,
  comment,
}: {
  board: TBoard;
  react: TReact;
  comment: TComment;
}) => {
  const cards = Object.entries(board.cards);
  if (cards.length === 0) return <Notice>No cards yet.</Notice>;
  return cards.map(([id, card]) => (
    <CardView key={id} id={id} card={card} react={react} comment={comment} />
  ));
};
