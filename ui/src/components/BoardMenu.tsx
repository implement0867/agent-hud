import { ChevronDown, Eraser } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { useBoard, useStore } from "~/data/context";
import { ActionKind } from "~/domain/actions";
import { boardInUrl, fetchBoards, linkTo } from "~/data/boards";
import type { TBoardList } from "~/domain/events";
import { agentDots } from "~/theme";

const count = (n: number, one: string) =>
  `${String(n)} ${n === 1 ? one : `${one}s`}`;

const rowTone = "flex items-center gap-2 rounded-lg px-2 py-1 text-xs";

type TClearDialogProps = { board: string; close: () => void };

/**
 * The confirm before the board is cleared, in the page: it names the board and what goes, the cards to the history
 * with their feedback, and the arrows and the chat for good. Esc or Keep closes it with the board as it is.
 */
const ClearDialog = ({ board, close }: TClearDialogProps) => {
  const { model } = useBoard();
  const store = useStore();
  const cards = model.cards.length;
  const arrows = Object.keys(model.board.arrows).length;
  const messages = model.board.messages.length;
  useEffect(() => {
    const listening = new AbortController();
    document.addEventListener(
      "keydown",
      (event) => {
        if (event.key !== "Escape") return;
        event.stopPropagation();
        close();
      },
      { capture: true, signal: listening.signal },
    );
    return () => {
      listening.abort();
    };
  }, [close]);
  return (
    <div
      role="dialog"
      aria-label="Clear this board?"
      className="panel absolute top-full left-0 mt-2 flex w-80 flex-col gap-3 p-4 text-sm text-ink-soft"
    >
      <p className="font-semibold text-ink">
        Clear <span className="font-mono">{board}</span>?
      </p>
      <p>
        {count(cards, "card")} {cards === 1 ? "goes" : "go"} to the history with{" "}
        {cards === 1 ? "its" : "their"} feedback. {count(arrows, "arrow")} and{" "}
        {count(messages, "message")} go for good.
      </p>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          className="rounded-xl px-3 py-1.5 font-medium hover:bg-surface-sunken"
          onClick={close}
        >
          Keep
        </button>
        <button
          type="button"
          className="rounded-xl bg-danger px-3 py-1.5 font-medium text-white hover:bg-danger-strong"
          onClick={() => {
            void store.act({ kind: ActionKind.enum.clear });
            close();
          }}
        >
          Clear the board
        </button>
      </div>
    </div>
  );
};

/**
 * The board that the page shows, and a menu of every board on the server, each with its cards and whether an agent
 * follows it; a click opens that board's page. The
 * menu ends with Clear this board, which asks first, in the page, and names what goes.
 */
export const BoardMenu = () => {
  const { model } = useBoard();
  const [boards, setBoards] = useState<TBoardList | "failed" | null>(null);
  const [clearing, setClearing] = useState(false);
  const menuId = useId();
  const menu = useRef<HTMLUListElement>(null);
  const current = boardInUrl() ?? "";
  const open = async () => {
    try {
      setBoards(await fetchBoards());
    } catch {
      setBoards("failed");
    }
  };
  return (
    <span className="relative flex items-center">
      <button
        type="button"
        aria-label="Boards"
        popoverTarget={menuId}
        title="The board this page shows; click for the other boards"
        className="flex items-center gap-0.5 rounded-full px-1.5 font-mono text-xs text-ink-soft [anchor-name:--board-menu] hover:bg-surface-sunken"
      >
        {current}
        <ChevronDown className="size-3" />
      </button>
      <ul
        id={menuId}
        ref={menu}
        popover="auto"
        role="menu"
        aria-label="Other boards"
        className={`panel inset-auto m-0 mt-2 border-0 [position-anchor:--board-menu] [top:anchor(bottom)] [left:anchor(left)] w-64 flex-col gap-0.5 p-1 open:flex`}
        onToggle={(event) => {
          if (event.newState === "open") void open();
        }}
      >
        {boards === "failed" ? (
          <li className="px-2 py-1 text-xs text-ink-muted">
            The boards could not be listed.
          </li>
        ) : (
          boards?.map((board) => {
            const row = (
              <>
                <span
                  className={`size-2 rounded-full ${agentDots[board.agent]}`}
                />
                <span className="truncate font-mono">{board.name}</span>
                <span className="ml-auto text-ink-faint">
                  {board.card_count} {board.card_count === 1 ? "card" : "cards"}
                </span>
              </>
            );
            return (
              <li key={board.name} role="none">
                {board.name === current ? (
                  <span
                    role="menuitem"
                    aria-current="page"
                    aria-disabled
                    className={`${rowTone} bg-accent-faint text-accent-strong`}
                  >
                    {row}
                  </span>
                ) : (
                  <a
                    role="menuitem"
                    href={linkTo(board.name)}
                    className={`${rowTone} text-ink-soft hover:bg-surface-sunken`}
                  >
                    {row}
                  </a>
                )}
              </li>
            );
          })
        )}
        <li role="none" className="mt-1 border-t border-divider pt-1">
          <button
            type="button"
            role="menuitem"
            disabled={model.cards.length === 0}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left text-xs text-ink-soft enabled:hover:bg-danger-faint enabled:hover:text-danger-strong disabled:text-ink-ghost"
            onClick={() => {
              menu.current?.hidePopover();
              setClearing(true);
            }}
          >
            <Eraser className="size-3.5" />
            Clear this board…
          </button>
        </li>
      </ul>
      {clearing ? (
        <ClearDialog
          board={current}
          close={() => {
            setClearing(false);
          }}
        />
      ) : null}
    </span>
  );
};
