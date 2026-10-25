import {
  Eraser,
  History,
  Keyboard,
  Maximize2,
  Minus,
  Plus,
  StickyNote,
} from "lucide-react";

import { IconButton } from "~/components/IconButton";
import { useBoard, useStore } from "~/data/context";
import { ActionKind } from "~/domain/actions";

const Divider = () => <span className="mx-1 h-5 w-px bg-outline" />;

type TToolbarProps = {
  scale: number;
  /** Zooms in by the steps, or out by negative steps. */
  zoom: (steps: number) => void;
  reset: () => void;
  fit: () => void;
  note: () => void;
  history: boolean;
  toggleHistory: () => void;
  shortcuts: boolean;
  toggleShortcuts: () => void;
  /** Takes the toolbar's element, so that the chat sits above it on a narrow screen; returns what to do when it goes. */
  measure: (element: HTMLElement) => () => void;
};

/**
 * The board's tools at the bottom: notes, history, shortcuts, clear and the view. Its controls are the same whatever
 * the board holds, so that none of them moves; Send and what it carries are in the chat, beside the message box.
 */
export const Toolbar = ({
  scale,
  zoom,
  reset,
  fit,
  note,
  history,
  toggleHistory,
  shortcuts,
  toggleShortcuts,
  measure,
}: TToolbarProps) => {
  const { model } = useBoard();
  const store = useStore();
  return (
    <nav
      ref={measure}
      aria-label="Tools"
      className="panel pointer-events-auto absolute bottom-4 left-1/2 flex max-w-[calc(100%-2rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-0.5 p-1"
    >
      <IconButton
        variant="tool"
        label="New note"
        title="New note (N)"
        onClick={note}
      >
        <StickyNote className="size-4" />
        Note
      </IconButton>
      <IconButton
        variant="tool"
        label="History"
        title="History (H)"
        pressed={history}
        onClick={toggleHistory}
      >
        <History className="size-4" />
      </IconButton>
      <IconButton
        variant="tool"
        label="Shortcuts"
        title="Shortcuts (?)"
        pressed={shortcuts}
        onClick={toggleShortcuts}
      >
        <Keyboard className="size-4" />
      </IconButton>
      <IconButton
        variant="danger"
        label="Clear the board"
        title="Clear the board: the cards go to the history"
        disabled={model.cards.length === 0}
        onClick={() => {
          if (window.confirm("Clear the board? The cards go to the history."))
            void store.act({ kind: ActionKind.enum.clear });
        }}
      >
        <Eraser className="size-4" />
      </IconButton>
      <Divider />
      <IconButton
        variant="tool"
        label="Zoom out"
        title="Zoom out (-)"
        onClick={() => {
          zoom(-1);
        }}
      >
        <Minus className="size-4" />
      </IconButton>
      <IconButton
        variant="tool"
        label="Reset zoom"
        title="Reset zoom (0)"
        onClick={reset}
      >
        <span className="w-10 text-xs tabular-nums">
          {Math.round(scale * 100)}%
        </span>
      </IconButton>
      <IconButton
        variant="tool"
        label="Zoom in"
        title="Zoom in (+)"
        onClick={() => {
          zoom(1);
        }}
      >
        <Plus className="size-4" />
      </IconButton>
      <IconButton
        variant="tool"
        label="Fit all cards"
        title="Fit all cards (1)"
        onClick={fit}
      >
        <Maximize2 className="size-4" />
      </IconButton>
    </nav>
  );
};
