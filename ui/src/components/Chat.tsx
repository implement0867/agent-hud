import { MessagesSquare, PanelRightClose } from "lucide-react";
import { useState } from "react";
import type { CSSProperties } from "react";

import { Bubble, Composer } from "~/components/FeedbackPanel";
import { useTools } from "~/lib/whiteboard";
import { ActionKind, Author } from "~/schemas/actions";

/**
 * The messages between the user and the agent, and the comments on parts, newest at the bottom.
 * A closed chat counts the agent's new messages and comments. A message also sends the user's unsent actions.
 */
export const Chat = ({
  unsent,
  above,
}: {
  unsent: number;
  /** The height of the toolbar, which the chat sits above on a screen narrower than 1280 px. */
  above: number;
}) => {
  const { board, act } = useTools();
  const lift = { "--toolbar": `${String(above)}px` } as CSSProperties;
  const [open, setOpen] = useState(true);
  const fromAgent = board.messages.filter(
    (said) => said.author === Author.enum.agent,
  ).length;
  const [seen, setSeen] = useState(fromAgent);
  const unread = open ? 0 : fromAgent - seen;
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
      aria-label="Chat with the agent"
      style={lift}
      className="pointer-events-auto absolute right-4 bottom-[calc(var(--toolbar)+2rem)] flex max-h-[70%] w-80 max-w-[calc(100%-2rem)] animate-pop flex-col rounded-2xl bg-white shadow-xl ring-1 ring-stone-900/10 select-text xl:bottom-4"
    >
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
