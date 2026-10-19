import { memo, useCallback, useState } from "react";
import type { ChangeEvent, KeyboardEvent, MouseEvent } from "react";

import { Icon } from "~/chrome/icons";
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
    const remove = useCallback(
      (e: MouseEvent<HTMLButtonElement>) => {
        const cid = e.currentTarget.dataset["cid"];
        if (cid !== undefined) send({ t: "uncomment", id, anchor, cid });
      },
      [send, id, anchor],
    );
    if (comments.length === 0 && !composing) return null;
    return (
      <div className="thread">
        {comments.map((c) => (
          <div
            key={c.id}
            className={
              c.author === "user"
                ? "comment comment-user"
                : "comment comment-agent"
            }
          >
            <span className="comment-author">
              {c.author === "user" ? "You" : "Agent"}
            </span>
            <span className="comment-text">{c.text}</span>
            {c.author === "user" ? (
              <button
                type="button"
                className="comment-remove"
                data-cid={c.id}
                onClick={remove}
                title="Delete comment"
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
  const onChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
  }, []);
  const submit = useCallback(() => {
    const trimmed = text.trim();
    if (trimmed !== "") send({ t: "comment", id, anchor, text: trimmed });
    setText("");
    onDone();
  }, [send, id, anchor, text, onDone]);
  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      e.stopPropagation();
      if (e.key === "Escape") onDone();
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submit();
      }
    },
    [submit, onDone],
  );
  return (
    <textarea
      className="composer"
      placeholder="Comment… Enter to add, Esc to cancel"
      value={text}
      onChange={onChange}
      onKeyDown={onKeyDown}
      onBlur={submit}
      autoFocus
      rows={2}
    />
  );
};
