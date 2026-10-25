import { MessagesSquare, PanelRightClose } from "lucide-react";
import { useState } from "react";
import type { PointerEvent } from "react";

import { Bubble, Composer } from "~/components/FeedbackPanel";
import { IconButton } from "~/components/IconButton";
import { useBoard } from "~/data/useBoard";
import { ActionKind, Author } from "~/domain/actions";

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

/** Keeps the width in this browser; where storage is blocked, the chat keeps it for this page alone. */
const storeWidth = (width: number) => {
  try {
    localStorage.setItem(widthKey, String(width));
  } catch {
    return;
  }
};

/** The chat's place: above the toolbar on a screen narrower than 1280 px, at the bottom right on a wider one. */
const place =
  "pointer-events-auto absolute right-4 bottom-[calc(var(--toolbar)+2rem)] xl:bottom-4";

type TChatProps = {
  /** The height of the toolbar, which the chat sits above on a narrow screen. */
  above: number;
  /** Takes the open chat's element, for the board to keep clear of it; returns what to do when it goes. */
  measure: (element: HTMLElement) => () => void;
};

/**
 * The messages between the user and the agent, and the comments on parts, newest at the bottom.
 * A closed chat counts the agent's new messages and comments. A message also sends the user's unsent actions.
 * A drag on the chat's left edge sets its width, which the browser keeps.
 */
export const Chat = ({ above, measure }: TChatProps) => {
  const { model, store } = useBoard();
  const [width, setWidth] = useState(storedWidth);
  const [message, setMessage] = useState("");
  const [open, setOpen] = useState(true);
  const fromAgent = model.board.messages.filter(
    (said) => said.author === Author.enum.agent,
  ).length;
  const [seen, setSeen] = useState(fromAgent);
  const unread = open ? 0 : fromAgent - seen;
  const unsent = model.pending.length;
  const style = { "--toolbar": `${String(above)}px`, width };
  const resize = (event: PointerEvent<HTMLElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    const from = { x: event.clientX, width };
    const listening = new AbortController();
    const { signal } = listening;
    window.addEventListener(
      "pointermove",
      (move) => {
        setWidth(clampWidth(from.width + from.x - move.clientX));
      },
      { signal },
    );
    window.addEventListener(
      "pointerup",
      (up) => {
        listening.abort();
        const settled = clampWidth(from.width + from.x - up.clientX);
        setWidth(settled);
        storeWidth(settled);
      },
      { signal },
    );
  };
  if (!open)
    return (
      <button
        type="button"
        aria-label="Open the chat"
        style={style}
        className={`${place} grid size-11 place-items-center rounded-full bg-surface text-ink-soft shadow-lg ring-1 ring-edge hover:text-ink`}
        onClick={() => {
          setOpen(true);
        }}
      >
        <MessagesSquare className="size-5" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 grid size-5 place-items-center rounded-full bg-accent text-[11px] font-semibold text-white">
            {unread}
          </span>
        )}
      </button>
    );
  return (
    <aside
      ref={measure}
      aria-label="Chat with the agent"
      style={style}
      className={`${place} panel flex max-h-[70%] max-w-[calc(100%-2rem)] animate-pop flex-col select-text`}
    >
      <div
        role="separator"
        aria-label="Resize the chat"
        aria-orientation="vertical"
        aria-valuenow={width}
        aria-valuemin={narrowest}
        aria-valuemax={widest}
        className="absolute inset-y-3 -left-1.5 w-3 cursor-col-resize rounded-full hover:bg-accent-muted/60"
        onPointerDown={resize}
      />
      <header className="flex items-center justify-between border-b border-divider px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">Chat</h2>
        <IconButton
          variant="close"
          label="Close the chat"
          onClick={() => {
            setSeen(fromAgent);
            setOpen(false);
          }}
        >
          <PanelRightClose className="size-4" />
        </IconButton>
      </header>
      <ul className="flex min-h-24 flex-col-reverse gap-2 overflow-y-auto px-3 py-3">
        {model.board.messages.toReversed().map((said) => (
          <Bubble key={said.id} said={said} withRef />
        ))}
      </ul>
      <div className="p-3 pt-0">
        <Composer
          label="Message the agent"
          id="message-box"
          send={(text) => store.act({ kind: ActionKind.enum.say, text })}
          draft={{ text: message, set: setMessage }}
        />
        {unsent > 0 && (
          <p className="mt-1.5 px-2 text-[11px] text-ink-faint">
            Your message also sends {unsent}{" "}
            {unsent === 1 ? "change" : "changes"}.
          </p>
        )}
      </div>
    </aside>
  );
};
