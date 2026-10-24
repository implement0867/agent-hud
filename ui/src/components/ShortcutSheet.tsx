import { X } from "lucide-react";

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

/** The keys and gestures of the page, with the platform's modifier. */
export const ShortcutSheet = ({ close }: { close: () => void }) => (
  <section
    role="dialog"
    aria-label="Shortcuts"
    className="pointer-events-auto absolute top-16 left-1/2 max-h-[80%] w-[26rem] max-w-[calc(100%-2rem)] -translate-x-1/2 animate-pop overflow-y-auto rounded-2xl bg-white p-4 shadow-xl ring-1 ring-stone-900/10"
  >
    <header className="mb-3 flex items-center justify-between">
      <h2 className="text-sm font-semibold text-stone-800">Shortcuts</h2>
      <button
        type="button"
        aria-label="Close the shortcuts"
        className="rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
        onClick={close}
      >
        <X className="size-4" />
      </button>
    </header>
    {groups.map(({ title, rows }) => (
      <section key={title} className="mb-3">
        <h3 className="mb-1 text-[11px] font-semibold tracking-wide text-stone-400 uppercase">
          {title}
        </h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          {rows.map(([keys, does]) => (
            <div key={keys} className="contents">
              <dt>
                <kbd className="rounded bg-stone-100 px-1.5 py-px font-mono text-[11px] text-stone-700">
                  {keys}
                </kbd>
              </dt>
              <dd className="text-stone-600">{does}</dd>
            </div>
          ))}
        </dl>
      </section>
    ))}
  </section>
);
