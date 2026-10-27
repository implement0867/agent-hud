import { useEffect, useState } from "react";

import { fetchBoards, linkTo } from "~/data/boards";
import type { TBoardList } from "~/domain/events";
import { agentDots } from "~/theme";

/**
 * The page without a board in its URL: the list of every board on the server, each a link to its page, or how to
 * make one when there is none.
 */
export const BoardPicker = () => {
  const [boards, setBoards] = useState<TBoardList | "failed" | null>(null);
  useEffect(() => {
    fetchBoards().then(setBoards, () => {
      setBoards("failed");
    });
  }, []);
  return (
    <section
      aria-label="Boards"
      className="panel m-auto flex w-80 flex-col gap-1 p-3"
    >
      <h1 className="px-2 pb-1 text-sm font-semibold text-ink">Boards</h1>
      {boards === null ? null : boards === "failed" ? (
        <p className="px-2 text-xs text-ink-muted">
          The boards could not be listed.
        </p>
      ) : boards.length === 0 ? (
        <p className="px-2 text-xs text-ink-muted">
          No board yet. The agent makes one with its create_board tool.
        </p>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {boards.map((board) => (
            <li key={board.name}>
              <a
                href={linkTo(board.name)}
                className="flex items-center gap-2 rounded-lg px-2 py-1 text-xs text-ink-soft hover:bg-surface-sunken"
              >
                <span
                  className={`size-2 rounded-full ${agentDots[board.agent]}`}
                />
                <span className="truncate font-mono">{board.name}</span>
                <span className="ml-auto text-ink-faint">
                  {board.cards} {board.cards === 1 ? "card" : "cards"}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};
