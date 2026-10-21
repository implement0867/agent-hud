import { createContext, useContext, useMemo, useState } from "react";
import type { ComponentProps } from "react";
import Markdown from "react-markdown";
import type { ExtraProps } from "react-markdown";

import { Notice } from "~/components/Notice";
import type { TBoardSocket } from "~/api/boardSocket";
import { Reaction } from "~/schemas/board";
import type { TBoard, TCard, TReaction } from "~/schemas/board";
import { invariant } from "~/lib/invariant";
import { numberListItems } from "~/lib/numberListItems";
import { messageSchema } from "~/schemas/events";

type TReact = TBoardSocket["react"];
type TReactToItem = TBoardSocket["reactToItem"];
type TComment = TBoardSocket["comment"];

const CardContext = createContext<{
  id: string;
  card: TCard;
  reactToItem: TReactToItem;
} | null>(null);

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

const ListItem = ({ node, children }: ComponentProps<"li"> & ExtraProps) => {
  const context = useContext(CardContext);
  const number = node?.properties["dataItem"];
  invariant(context !== null, "list items render inside a card");
  invariant(typeof number === "number", "numberListItems numbers each li");
  const { id, card, reactToItem } = context;
  return (
    <li>
      {children}
      <ReactionButtons
        label={`Reactions on ${id} item ${String(number)}`}
        current={card.items[number]?.reaction ?? null}
        react={(reaction) => {
          reactToItem(id, number, reaction);
        }}
      />
    </li>
  );
};

const CardView = ({
  id,
  card,
  react,
  reactToItem,
  comment,
}: {
  id: string;
  card: TCard;
  react: TReact;
  reactToItem: TReactToItem;
  comment: TComment;
}) => {
  const context = useMemo(
    () => ({ id, card, reactToItem }),
    [id, card, reactToItem],
  );
  return (
    <article className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
      <header className="mb-2 font-mono text-xs text-stone-400">{id}</header>
      <div className="prose prose-sm prose-stone max-w-none">
        <CardContext value={context}>
          <Markdown
            rehypePlugins={[numberListItems]}
            components={{ li: ListItem }}
          >
            {card.md}
          </Markdown>
        </CardContext>
      </div>
      <ReactionButtons
        label={`Reactions on ${id}`}
        current={card.reaction}
        react={(reaction) => {
          react(id, reaction);
        }}
      />
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
};

export const Cards = ({
  board,
  react,
  reactToItem,
  comment,
}: {
  board: TBoard;
  react: TReact;
  reactToItem: TReactToItem;
  comment: TComment;
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
    />
  ));
};
