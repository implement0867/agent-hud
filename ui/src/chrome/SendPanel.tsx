import { useEffect, useState } from "react";

import { Icon } from "~/chrome/icons";
import { cx } from "~/lib/cx";
import { useStore } from "~/lib/store";
import { boardStore } from "~/store/board";
import { useSend } from "~/store/socket";

/** Send returns the agent's blocking `read`. */
export const SendPanel = () => {
  const send = useSend();
  const waiting = useStore(boardStore, (s) => s.status.waiting);
  const pending = useStore(boardStore, (s) => s.status.pending);
  const open = useStore(boardStore, (s) => s.connection === "open");
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState(false);

  useEffect(() => {
    if (!sent) return;
    const timer = window.setTimeout(() => {
      setSent(false);
    }, 2500);
    return () => {
      window.clearTimeout(timer);
    };
  }, [sent]);

  const submit = () => {
    send({
      t: "submit",
      message: message.trim() === "" ? null : message.trim(),
    });
    setMessage("");
    setSent(true);
  };

  return (
    <section
      className={cx("chrome send-panel", waiting && "send-waiting")}
      aria-label="Send feedback"
    >
      <div className="send-status">
        {waiting ? (
          <span className="send-badge">Agent is waiting for your review</span>
        ) : (
          <span className="send-idle">
            {sent ? "Sent to the agent" : "Agent is working"}
          </span>
        )}
        <span className="send-count" title="Changes the agent has not read">
          {pending === 0
            ? "no unread changes"
            : `${String(pending)} unread change${pending === 1 ? "" : "s"}`}
        </span>
      </div>
      <div className="send-row">
        <textarea
          className="send-message"
          placeholder="Optional message… Enter sends"
          value={message}
          onChange={(e) => {
            setMessage(e.target.value);
          }}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !e.shiftKey)) {
              e.preventDefault();
              submit();
            }
          }}
          rows={1}
        />
        <button
          type="button"
          className="send-button"
          onClick={submit}
          disabled={!open}
          title="Send (Ctrl+Enter)"
        >
          <Icon name="send" size={16} />
          Send
        </button>
      </div>
    </section>
  );
};
