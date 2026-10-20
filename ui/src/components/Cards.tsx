import Markdown from "react-markdown";

import { Notice } from "~/components/Notice";
import type { TBoard, TCard } from "~/schemas/board";

const CardView = ({ id, card }: { id: string; card: TCard }) => (
  <article className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
    <header className="mb-2 font-mono text-xs text-stone-400">{id}</header>
    <div className="prose prose-sm prose-stone max-w-none">
      <Markdown>{card.md}</Markdown>
    </div>
  </article>
);

export const Cards = ({ board }: { board: TBoard }) => {
  const cards = Object.entries(board.cards);
  if (cards.length === 0) return <Notice>No cards yet.</Notice>;
  return cards.map(([id, card]) => <CardView key={id} id={id} card={card} />);
};
