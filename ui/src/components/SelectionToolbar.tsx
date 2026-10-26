import type { MouseEvent } from "react";

import type { TPoint } from "~/domain/board";

type TSelectionToolbarProps = {
  /** The top right of the selection, in the viewport. */
  at: TPoint;
  /** Whether an arrow from the selection is being drawn. */
  drawing: boolean;
  comment: () => void;
  arrow: (event: MouseEvent) => void;
};

const toolTone =
  "grid size-7 place-items-center rounded-code text-ink-soft hover:bg-surface-sunken hover:text-ink aria-pressed:bg-accent-soft aria-pressed:text-accent-strong";

/** The two actions on a selection of a card's words, above its end: comment, key C, and draw an arrow from it. */
export const SelectionToolbar = ({
  at,
  drawing,
  comment,
  arrow,
}: TSelectionToolbarProps) => (
  <span
    role="toolbar"
    aria-label="On the selection"
    className="pointer-events-auto absolute flex -translate-x-full -translate-y-[calc(100%+8px)] animate-pop items-center gap-0.5 rounded-bar bg-surface p-0.5 shadow-[var(--shadow-pop),0_0_0_1px_var(--edge)]"
    style={{ left: at.x, top: at.y }}
    onPointerDown={(event) => {
      // A press on the toolbar keeps the selection that it acts on.
      event.preventDefault();
      event.stopPropagation();
    }}
  >
    <button
      type="button"
      aria-label="Comment"
      title="Comment · C"
      className={toolTone}
      onClick={comment}
    >
      <svg
        viewBox="0 0 24 24"
        aria-hidden
        className="size-4 fill-none stroke-current stroke-2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    </button>
    <span aria-hidden className="mx-0.5 h-4 w-px bg-outline" />
    <button
      type="button"
      aria-label="Draw an arrow from here"
      aria-pressed={drawing}
      title="Arrow: then click a card"
      className={toolTone}
      onClick={arrow}
    >
      <svg
        viewBox="0 0 24 24"
        aria-hidden
        className="size-4 fill-none stroke-current stroke-2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="5" cy="19" r="2" />
        <path d="M7 17 18 6" />
        <path d="M11 6h7v7" />
      </svg>
    </button>
  </span>
);
