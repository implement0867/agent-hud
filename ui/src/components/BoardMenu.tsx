import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { boardListSchema } from "~/domain/events";
import type { TBoardList } from "~/domain/events";
import { agentDots } from "~/theme";

/** The id of the board that the page shows, from its URL; the shared board without one. */
const currentBoard = () =>
  new URLSearchParams(window.location.search).get("board") ?? "shared";

/** The page's URL for another board, with the token kept. */
const linkTo = (id: string) => {
  const url = new URL(window.location.href);
  url.searchParams.set("board", id);
  return url.toString();
};

/**
 * The board that the page shows, and a menu of every board on the server, one for each project that an agent works
 * in and the shared one, each with its cards and whether an agent follows it; a click opens that board's page.
 */
export const BoardMenu = () => {
  const [boards, setBoards] = useState<TBoardList | "failed" | null>(null);
  const current = currentBoard();
  const open = async () => {
    try {
      const url = new URL(
        `/boards${window.location.search}`,
        window.location.href,
      );
      const response = await fetch(url);
      setBoards(boardListSchema.parse(await response.json()));
    } catch {
      setBoards("failed");
    }
  };
  return (
    <span className="relative flex items-center">
      <button
        type="button"
        aria-label="Boards"
        aria-expanded={boards !== null}
        title="The board this page shows; click for the other boards"
        className="flex items-center gap-0.5 rounded-full px-1.5 font-mono text-xs text-ink-soft hover:bg-surface-sunken"
        onClick={() => {
          if (boards === null) void open();
          else setBoards(null);
        }}
      >
        {current}
        <ChevronDown className="size-3" />
      </button>
      {boards !== null && (
        <ul
          role="menu"
          aria-label="Other boards"
          className="panel absolute top-full left-0 mt-2 flex w-64 flex-col gap-0.5 p-1"
        >
          {boards === "failed" ? (
            <li className="px-2 py-1 text-xs text-ink-muted">
              The boards could not be listed.
            </li>
          ) : (
            boards.map((board) => (
              <li key={board.id} role="none">
                <a
                  role="menuitem"
                  href={linkTo(board.id)}
                  aria-current={board.id === current ? "page" : undefined}
                  className={`flex items-center gap-2 rounded-lg px-2 py-1 text-xs hover:bg-surface-sunken ${board.id === current ? "bg-accent-faint text-accent-strong" : "text-ink-soft"}`}
                >
                  <span
                    className={`size-2 rounded-full ${agentDots[board.agent]}`}
                  />
                  <span className="truncate font-mono">{board.id}</span>
                  <span className="ml-auto text-ink-faint">
                    {board.cards} {board.cards === 1 ? "card" : "cards"}
                  </span>
                </a>
              </li>
            ))
          )}
        </ul>
      )}
    </span>
  );
};
