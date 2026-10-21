import { useState } from "react";
import Markdown from "react-markdown";

import { Notice } from "~/components/Notice";
import type { TBoardSocket } from "~/api/boardSocket";
import { Reaction } from "~/schemas/board";
import type { TBoard, TCard, TComment, TReaction } from "~/schemas/board";
import { messageSchema } from "~/schemas/events";

type TReact = TBoardSocket["react"];
type TReactToItem = TBoardSocket["reactToItem"];
type TCommentOnCard = TBoardSocket["comment"];
type TCommentOnItem = TBoardSocket["commentOnItem"];

const CommentList = ({ comments }: { comments: TComment[] }) => (
  <ul className="mt-2 space-y-1 text-sm text-stone-700">
    {comments.map(({ id, text }) => (
      <li key={id} className="rounded bg-stone-100 px-2 py-1">
        {text}
      </li>
    ))}
  </ul>
);

/** The page clears the box when it sends the comment. */
const CommentForm = ({
  label,
  comment,
}: {
  label: string;
  comment: (text: string) => void;
}) => {
  const [text, setText] = useState("");
  return (
    <div className="mt-2 flex gap-1">
      <input
        className="flex-1 rounded border border-stone-300 px-2 text-sm"
        placeholder="Comment"
        aria-label={label}
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
          comment(text);
          setText("");
        }}
      >
        Comment
      </button>
    </div>
  );
};

/** Pressing the set reaction again clears it. */
const ReactionButtons = ({
  label,
  current,
  react,
}: {
  label: string;
  current: TReaction | null;
  react: (reaction: TReaction | null) => void;
}) => (
  <div role="group" aria-label={label} className="mt-2 flex gap-1">
    {Reaction.options.map((reaction) => (
      <button
        key={reaction}
        type="button"
        className="rounded border border-stone-300 px-2 text-xs text-stone-600 hover:bg-stone-100 aria-pressed:bg-stone-800 aria-pressed:text-white"
        aria-pressed={current === reaction}
        onClick={() => {
          react(current === reaction ? null : reaction);
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
  reactToItem,
  comment,
  commentOnItem,
}: {
  id: string;
  card: TCard;
  react: TReact;
  reactToItem: TReactToItem;
  comment: TCommentOnCard;
  commentOnItem: TCommentOnItem;
}) => (
  <article className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
    <header className="mb-2 font-mono text-xs text-stone-400">{id}</header>
    {card.items.length === 0 ? (
      <div className="prose prose-sm prose-stone max-w-none">
        <Markdown>{card.md}</Markdown>
      </div>
    ) : (
      <ol className="list-decimal space-y-2 pl-5">
        {card.items.map((item, index) => (
          <li key={item.id}>
            <div className="prose prose-sm prose-stone max-w-none">
              <Markdown>{item.md}</Markdown>
            </div>
            <ReactionButtons
              label={`Reactions on ${id} item ${String(index + 1)}`}
              current={item.reaction}
              react={(reaction) => {
                reactToItem(id, index + 1, reaction);
              }}
            />
            <CommentList comments={item.comments} />
            <CommentForm
              label={`Comment on ${id} item ${String(index + 1)}`}
              comment={(text) => {
                commentOnItem(id, index + 1, text);
              }}
            />
          </li>
        ))}
      </ol>
    )}
    <ReactionButtons
      label={`Reactions on ${id}`}
      current={card.reaction}
      react={(reaction) => {
        react(id, reaction);
      }}
    />
    <CommentList comments={card.comments} />
    <CommentForm
      label={`Comment on ${id}`}
      comment={(text) => {
        comment(id, text);
      }}
    />
  </article>
);

export const Cards = ({
  board,
  react,
  reactToItem,
  comment,
  commentOnItem,
}: {
  board: TBoard;
  react: TReact;
  reactToItem: TReactToItem;
  comment: TCommentOnCard;
  commentOnItem: TCommentOnItem;
}) => {
  const cards = Object.entries(board.cards);
  if (cards.length === 0) return <Notice>No cards yet.</Notice>;
  return cards.map(([id, card]) => (
    <CardView
      key={id}
      id={id}
      card={card}
      react={react}
      reactToItem={reactToItem}
      comment={comment}
      commentOnItem={commentOnItem}
    />
  ));
};
