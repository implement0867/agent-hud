import { X } from "lucide-react";

import { IconButton } from "~/components/IconButton";
import { mod } from "~/lib/keys";

const groups: { title: string; rows: [string, string][] }[] = [
  {
    title: "Board",
    rows: [
      ["N", "New note"],
      ["Double-click empty space", "New note there"],
      ["H", "History"],
      ["1", "Fit all cards"],
      ["0", "Reset the view"],
      ["+ / −", "Zoom"],
      [`${mod} + scroll`, "Zoom at the pointer"],
      ["Drag empty space, Space + drag, scroll", "Pan"],
      ["?", "This sheet"],
    ],
  },
  {
    title: "Cards",
    rows: [
      ["Click a card", "Select it"],
      ["Drag a card's padding", "Move it"],
      ["Arrow keys, Shift for more", "Move the selected card"],
      ["Drag an edge or a corner", "Resize the card"],
      ["Double-click, E or Enter", "Edit the card's markdown"],
      [`${mod} + Enter, in an editor`, "Save"],
      ["Delete", "Remove the card or arrow, with undo"],
      ["Click a box", "Check it, as an edit"],
    ],
  },
  {
    title: "Words",
    rows: [
      ["Select words in a card", "Show the comment and arrow buttons"],
      ["C", "Comment on the selected words"],
      ["Arrow button, then click a card", "Draw an arrow to that card"],
      ["Click a bubble", "Open its thread"],
      ["Esc", "Close"],
    ],
  },
  {
    title: "Agent",
    rows: [
      [`${mod} + Enter`, "Send your changes"],
      ["M", "Message the agent"],
    ],
  },
];

type TShortcutSheetProps = { close: () => void };

/** The keys and gestures of the page, with the platform's modifier. */
export const ShortcutSheet = ({ close }: TShortcutSheetProps) => (
  <section
    role="dialog"
    aria-label="Shortcuts"
    className="panel pointer-events-auto absolute top-16 left-1/2 max-h-[80%] w-[26rem] max-w-[calc(100%-2rem)] -translate-x-1/2 animate-pop overflow-y-auto p-4"
  >
    <header className="mb-3 flex items-center justify-between">
      <h2 className="text-sm font-semibold text-ink">Shortcuts</h2>
      <IconButton variant="close" label="Close the shortcuts" onClick={close}>
        <X className="size-4" />
      </IconButton>
    </header>
    {groups.map(({ title, rows }) => (
      <section key={title} className="mb-3">
        <h3 className="mb-1 text-[11px] font-semibold tracking-wide text-ink-faint uppercase">
          {title}
        </h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          {rows.map(([keys, does]) => (
            <div key={keys} className="contents">
              <dt>
                <kbd className="kbd">{keys}</kbd>
              </dt>
              <dd className="text-ink-soft">{does}</dd>
            </div>
          ))}
        </dl>
      </section>
    ))}
  </section>
);
