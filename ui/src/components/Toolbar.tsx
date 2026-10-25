import {
  History,
  Keyboard,
  Maximize2,
  Minus,
  Plus,
  RotateCcw,
  StickyNote,
} from "lucide-react";

import { IconButton } from "~/components/IconButton";

const Divider = () => <span className="mx-1 h-5 w-px bg-outline" />;

type TToolbarProps = {
  scale: number;
  /** Whether the view is where it starts, at full size; a reset takes it back there. */
  atHome: boolean;
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
 * The board's tools at the bottom, each with a visible label: a note, the history, the shortcuts and the view, where
 * Fit shows every card and the zoom button, which reads the zoom, resets the view. Its controls are the same whatever
 * the board holds, so that none of them moves. Send is in the chat beside the message box, and Clear in the board menu.
 */
export const Toolbar = ({
  scale,
  atHome,
  zoom,
  reset,
  fit,
  note,
  history,
  toggleHistory,
  shortcuts,
  toggleShortcuts,
  measure,
}: TToolbarProps) => (
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
      History
    </IconButton>
    <IconButton
      variant="tool"
      label="Shortcuts"
      title="Shortcuts (?)"
      pressed={shortcuts}
      onClick={toggleShortcuts}
    >
      <Keyboard className="size-4" />
      Shortcuts
    </IconButton>
    <Divider />
    <IconButton
      variant="tool"
      label="Zoom out"
      title="Zoom out (−)"
      onClick={() => {
        zoom(-1);
      }}
    >
      <Minus className="size-4" />
    </IconButton>
    <IconButton
      variant="tool"
      label="Reset the view"
      title="Reset the view to full size at the start (0)"
      disabled={atHome}
      onClick={reset}
    >
      <RotateCcw className={`size-3.5 ${atHome ? "invisible" : ""}`} />
      <span className="text-xs tabular-nums">{Math.round(scale * 100)}%</span>
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
      title="Fit all cards in view, at the zoom that shows them all (1)"
      onClick={fit}
    >
      <Maximize2 className="size-4" />
      Fit
    </IconButton>
  </nav>
);
