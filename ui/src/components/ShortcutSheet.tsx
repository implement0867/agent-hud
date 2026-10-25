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
    title: "Selection",
    rows: [
      ["Click a part or a card header", "Select it and open its feedback"],
      ["A / R / Q", "Approve, reject, question"],
      ["C or Enter", "Comment"],
      ["E", "Edit the card"],
      [`${mod} + Enter, in an editor`, "Save"],
      ["Delete", "Remove the card or arrow, with undo"],
      ["Drag the dot on a part", "Draw an arrow"],
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
                <kbd className="rounded bg-surface-sunken px-1.5 py-px font-mono text-[11px] text-ink-soft">
                  {keys}
                </kbd>
              </dt>
              <dd className="text-ink-soft">{does}</dd>
            </div>
          ))}
        </dl>
      </section>
    ))}
  </section>
);
