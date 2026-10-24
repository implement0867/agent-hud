import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { AgentState } from "~/schemas/events";

const boardsSchema = z.array(
  z.strictObject({
    id: z.string(),
    cards: z.number().int().nonnegative(),
    agent: AgentState,
  }),
);

type TBoards = z.infer<typeof boardsSchema>;

/** The id of the board that the page shows, from its URL; the shared board without one. */
const currentBoard = () =>
  new URLSearchParams(window.location.search).get("board") ?? "shared";

/** The page's URL for another board, with the token kept. */
const linkTo = (id: string) => {
  const url = new URL(window.location.href);
  url.searchParams.set("board", id);
  return url.toString();
};

const dots = {
  away: "bg-stone-300",
  working: "bg-amber-500",
  waiting: "bg-emerald-500",
};

/**
 * The board that the page shows, and a menu of every board on the server, one for each project that an agent works
 * in and the shared one, each with its cards and whether an agent follows it; a click opens that board's page.
 */
export const BoardMenu = () => {
  const [boards, setBoards] = useState<TBoards | "failed" | null>(null);
  const current = currentBoard();
  const open = async () => {
    try {
      const url = new URL(
        `/boards${window.location.search}`,
        window.location.href,
      );
      const response = await fetch(url);
      setBoards(boardsSchema.parse(await response.json()));
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
        className="flex items-center gap-0.5 rounded-full px-1.5 font-mono text-xs text-stone-600 hover:bg-stone-100"
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
          className="absolute top-full left-0 mt-2 flex w-64 flex-col gap-0.5 rounded-xl bg-white p-1 shadow-xl ring-1 ring-stone-900/10"
        >
          {boards === "failed" ? (
            <li className="px-2 py-1 text-xs text-stone-500">
              The boards could not be listed.
            </li>
          ) : (
            boards.map((board) => (
              <li key={board.id} role="none">
                <a
                  role="menuitem"
                  href={linkTo(board.id)}
                  aria-current={board.id === current ? "page" : undefined}
                  className={`flex items-center gap-2 rounded-lg px-2 py-1 text-xs hover:bg-stone-100 ${board.id === current ? "bg-sky-50 text-sky-800" : "text-stone-700"}`}
                >
                  <span
                    className={`size-2 rounded-full ${dots[board.agent]}`}
                  />
                  <span className="truncate font-mono">{board.id}</span>
                  <span className="ml-auto text-stone-400">
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
