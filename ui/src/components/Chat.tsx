import { MessagesSquare, PanelRightClose } from "lucide-react";
import { useState } from "react";
import type { CSSProperties, PointerEvent } from "react";

import { Bubble, Composer } from "~/components/FeedbackPanel";
import { useTools } from "~/lib/whiteboard";
import { ActionKind, Author } from "~/schemas/actions";

const widthKey = "agent-hud:chat-width";
const narrowest = 280;
const widest = 640;

const clampWidth = (width: number) =>
  Math.min(widest, Math.max(narrowest, Math.round(width)));

/** The width the user last dragged the chat to, in this browser, or the default. */
const storedWidth = () => {
  try {
    const stored = Number(localStorage.getItem(widthKey));
    return stored > 0 ? clampWidth(stored) : 320;
  } catch {
    return 320;
  }
};

const storeWidth = (width: number) => {
  try {
    localStorage.setItem(widthKey, String(width));
  } catch {
    // The chat keeps the width for this page alone.
  }
};

/**
 * The messages between the user and the agent, and the comments on parts, newest at the bottom.
 * A closed chat counts the agent's new messages and comments. A message also sends the user's unsent actions.
 * A drag on the chat's left edge sets its width, which the browser keeps.
 */
export const Chat = ({
  unsent,
  above,
  measure,
}: {
  unsent: number;
  /** The height of the toolbar, which the chat sits above on a screen narrower than 1280 px. */
  above: number;
  /** Gets the open chat's element, and null when it closes, for the board to keep clear of it. */
  measure: (element: HTMLElement | null) => void;
}) => {
  const { board, act } = useTools();
  const [width, setWidth] = useState(storedWidth);
  const lift = {
    "--toolbar": `${String(above)}px`,
    width,
  } as CSSProperties;
  const [open, setOpen] = useState(true);
  const fromAgent = board.messages.filter(
    (said) => said.author === Author.enum.agent,
  ).length;
  const [seen, setSeen] = useState(fromAgent);
  const unread = open ? 0 : fromAgent - seen;
  const resize = (event: PointerEvent<HTMLElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    const from = { x: event.clientX, width };
    const controller = new AbortController();
    window.addEventListener(
      "pointermove",
      (move) => {
        setWidth(clampWidth(from.width + from.x - move.clientX));
      },
      { signal: controller.signal },
    );
    window.addEventListener(
      "pointerup",
      (up) => {
        controller.abort();
        const settled = clampWidth(from.width + from.x - up.clientX);
        setWidth(settled);
        storeWidth(settled);
      },
      { signal: controller.signal },
    );
  };
  if (!open)
    return (
      <button
        type="button"
        aria-label="Open the chat"
        style={lift}
        className="pointer-events-auto absolute right-4 bottom-[calc(var(--toolbar)+2rem)] grid size-11 place-items-center rounded-full bg-white text-stone-600 shadow-lg ring-1 ring-stone-900/10 hover:text-stone-900 xl:bottom-4"
        onClick={() => {
          setOpen(true);
        }}
      >
        <MessagesSquare className="size-5" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 grid size-5 place-items-center rounded-full bg-sky-600 text-[11px] font-semibold text-white">
            {unread}
          </span>
        )}
      </button>
    );
  return (
    <aside
      ref={measure}
      aria-label="Chat with the agent"
      style={lift}
      className="pointer-events-auto absolute right-4 bottom-[calc(var(--toolbar)+2rem)] flex max-h-[70%] max-w-[calc(100%-2rem)] animate-pop flex-col rounded-2xl bg-white shadow-xl ring-1 ring-stone-900/10 select-text xl:bottom-4"
    >
      <div
        role="separator"
        aria-label="Resize the chat"
        aria-orientation="vertical"
        aria-valuenow={width}
        aria-valuemin={narrowest}
        aria-valuemax={widest}
        className="absolute inset-y-3 -left-1.5 w-3 cursor-col-resize rounded-full hover:bg-sky-200/60"
        onPointerDown={resize}
      />
      <header className="flex items-center justify-between border-b border-stone-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-stone-800">Chat</h2>
        <button
          type="button"
          aria-label="Close the chat"
          className="rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
          onClick={() => {
            setSeen(fromAgent);
            setOpen(false);
          }}
        >
          <PanelRightClose className="size-4" />
        </button>
      </header>
      <ul className="flex min-h-24 flex-col-reverse gap-2 overflow-y-auto px-3 py-3">
        {board.messages.toReversed().map((said) => (
          <Bubble key={said.id} said={said} withRef />
        ))}
      </ul>
      <div className="p-3 pt-0">
        <Composer
          label="Message the agent"
          id="message-box"
          send={(text) => act({ kind: ActionKind.enum.say, text })}
        />
        {unsent > 0 && (
          <p className="mt-1.5 px-2 text-[11px] text-stone-400">
            Your message also sends {unsent}{" "}
            {unsent === 1 ? "change" : "changes"}.
          </p>
        )}
      </div>
    </aside>
  );
};
