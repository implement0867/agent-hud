import { useEffect, useState } from "react";

import { useStore } from "~/lib/store";
import { boardStore } from "~/store/board";
import { uiStore } from "~/store/ui";

/** Shows the last server error for a few seconds. */
export const Toast = () => {
  const error = useStore(boardStore, (s) => s.error);
  const [dismissed, setDismissed] = useState<number | null>(null);
  useEffect(() => {
    if (error === null) return;
    const timer = window.setTimeout(() => {
      setDismissed(error.at);
    }, 4000);
    return () => {
      window.clearTimeout(timer);
    };
  }, [error]);
  if (error === null || dismissed === error.at) return null;
  return (
    <div className="chrome toast" role="status">
      {error.message}
    </div>
  );
};

export const ToolHint = () => {
  const tool = useStore(uiStore, (s) => s.tool);
  const from = useStore(uiStore, (s) => s.linkFrom);
  const text =
    tool === "link"
      ? from === null
        ? "Click the part the arrow starts at"
        : "Click the part the arrow points to · Esc cancels"
      : tool === "note"
        ? "Click anywhere to place a note for the agent"
        : null;
  return text === null ? null : <div className="chrome tool-hint">{text}</div>;
};

export const EmptyState = () => {
  const empty = useStore(boardStore, (s) => s.order.length === 0);
  const open = useStore(boardStore, (s) => s.connection === "open");
  if (!empty) return null;
  return (
    <div className="empty">
      <h1>{open ? "Waiting for the agent" : "Connecting to the agent…"}</h1>
      <p>
        Plans, options and tables the agent shares appear here. Approve, reject
        or question each item, comment, draw arrows, then press <kbd>Send</kbd>.
      </p>
      <p className="empty-keys">
        <kbd>N</kbd> note · <kbd>L</kbd> arrow · <kbd>T</kbd> tidy ·{" "}
        <kbd>Space</kbd>+drag pan · <kbd>Ctrl</kbd>+scroll zoom
      </p>
    </div>
  );
};
