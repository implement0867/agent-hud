import { memo, useState } from "react";

import { Icon } from "~/chrome/icons";
import { Author } from "~/protocol/schema";
import type { Comment } from "~/protocol/schema";
import { useSend } from "~/store/socket";

type ThreadProps = {
  id: string;
  anchor: string;
  comments: readonly Comment[];
  composing: boolean;
  onDone: () => void;
};

export const Thread = memo(
  ({ id, anchor, comments, composing, onDone }: ThreadProps) => {
    const send = useSend();
    if (comments.length === 0 && !composing) return null;
    return (
      <div className="thread">
        {comments.map((c) => (
          <div key={c.id} className={`comment comment-${c.author}`}>
            <span className="comment-author">
              {c.author === Author.enum.user ? "You" : "Agent"}
            </span>
            <span className="comment-text">{c.text}</span>
            {c.author === Author.enum.user ? (
              <button
                type="button"
                className="comment-remove"
                title="Delete comment"
                onClick={() => {
                  send({ t: "uncomment", id, anchor, cid: c.id });
                }}
              >
                <Icon name="x" size={12} />
              </button>
            ) : null}
          </div>
        ))}
        {composing ? (
          <Composer id={id} anchor={anchor} onDone={onDone} />
        ) : null}
      </div>
    );
  },
);
Thread.displayName = "Thread";

type ComposerProps = { id: string; anchor: string; onDone: () => void };

const Composer = ({ id, anchor, onDone }: ComposerProps) => {
  const send = useSend();
  const [text, setText] = useState("");
  const submit = () => {
    if (text.trim() !== "")
      send({ t: "comment", id, anchor, text: text.trim() });
    setText("");
    onDone();
  };
  return (
    <textarea
      className="composer"
      placeholder="Comment… Enter to add, Esc to cancel"
      value={text}
      onChange={(e) => {
        setText(e.target.value);
      }}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Escape") onDone();
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          submit();
        }
      }}
      onBlur={submit}
      autoFocus
      rows={2}
    />
  );
};
