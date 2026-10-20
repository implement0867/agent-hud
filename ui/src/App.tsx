import type { ReactNode } from "react";
import Markdown from "react-markdown";

import { ConnectionStatus, useBoard } from "~/hooks/useBoard";
import { assertNever } from "~/lib/assertNever";
import type { TBoard, TCard } from "~/schemas/board";

const Notice = ({ children }: { children: ReactNode }) => (
  <p className="text-stone-500">{children}</p>
);

const CardView = ({ id, card }: { id: string; card: TCard }) => (
  <article className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
    <header className="mb-2 font-mono text-xs text-stone-400">{id}</header>
    <div className="prose prose-sm prose-stone max-w-none">
      <Markdown>{card.md}</Markdown>
    </div>
  </article>
);

const Cards = ({ board }: { board: TBoard }) => {
  const cards = Object.entries(board.cards);
  if (cards.length === 0) return <Notice>No cards yet.</Notice>;
  return cards.map(([id, card]) => <CardView key={id} id={id} card={card} />);
};

const BoardView = () => {
  const connection = useBoard();
  switch (connection.status) {
    case ConnectionStatus.enum.connecting:
      return <Notice>Connecting to the agent…</Notice>;
    case ConnectionStatus.enum.live:
      return <Cards board={connection.board} />;
    case ConnectionStatus.enum.closed:
      return (
        <Notice>
          The agent closed the board. Reload the page after it starts again.
        </Notice>
      );
    default:
      return assertNever(connection);
  }
};

export const App = () => (
  <main className="mx-auto flex max-w-3xl flex-col gap-4 p-8">
    <BoardView />
  </main>
);
