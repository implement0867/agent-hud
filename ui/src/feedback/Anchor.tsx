import { memo, useState } from "react";
import type { ReactNode } from "react";

import { Icon } from "~/chrome/icons";
import type { IconName } from "~/chrome/icons";
import { Thread } from "~/feedback/Thread";
import { cx } from "~/lib/cx";
import { useStore } from "~/lib/store";
import { Reaction } from "~/protocol/schema";
import type { Element, Feedback } from "~/protocol/schema";
import { useSend } from "~/store/socket";
import { anchorKey, pickAnchor, uiStore } from "~/store/ui";

const verdicts: Readonly<Record<Reaction, { icon: IconName; label: string }>> =
  {
    approve: { icon: "check", label: "Approve" },
    reject: { icon: "x", label: "Reject" },
    question: { icon: "question", label: "Question" },
  };

const noFeedback: Feedback = { reaction: null, revised: false, comments: [] };

type AnchorProps = {
  el: Element;
  /** Empty for the whole element. */
  anchor: string;
  children: ReactNode;
  /** `popover` keeps comments out of the layout, for table cells. */
  thread?: "inline" | "popover";
  onRemove?: () => void;
  className?: string;
};

/** A part the user can react to, comment on, or draw an arrow from. */
export const Anchor = memo(
  ({
    el,
    anchor,
    children,
    thread = "inline",
    onRemove,
    className,
  }: AnchorProps) => {
    const send = useSend();
    const linking = useStore(uiStore, (s) => s.tool === "link");
    const isSource = useStore(
      uiStore,
      (s) => s.linkFrom?.id === el.id && s.linkFrom.anchor === anchor,
    );
    const [composing, setComposing] = useState(false);
    const [open, setOpen] = useState(false);
    const { reaction, revised, comments } = el.feedback[anchor] ?? noFeedback;

    return (
      <div
        className={cx(
          "anchor",
          linking && "anchor-linkable",
          isSource && "anchor-source",
          className,
        )}
        data-anchor={anchorKey(el.id, anchor)}
        data-reaction={reaction ?? undefined}
        onClickCapture={(e) => {
          if (uiStore.get().tool !== "link") return;
          e.preventDefault();
          e.stopPropagation();
          pickAnchor({ id: el.id, anchor }, e.clientX, e.clientY);
        }}
      >
        <div className="anchor-content">{children}</div>
        <div className="anchor-marks">
          {reaction === null ? null : (
            <span className={`mark mark-${reaction}`} title={reaction}>
              <Icon name={verdicts[reaction].icon} size={12} />
            </span>
          )}
          {revised ? (
            <span
              className="mark-revised"
              title="The agent changed this after your feedback"
            >
              revised
            </span>
          ) : null}
          {thread === "popover" && comments.length > 0 ? (
            <button
              type="button"
              className="mark-count"
              title="Show comments"
              onClick={() => {
                setOpen((o) => !o);
              }}
            >
              <Icon name="message" size={11} />
              {comments.length}
            </button>
          ) : null}
        </div>
        {linking ? null : (
          <div className="anchor-actions">
            {Reaction.options.map((option) => (
              <button
                key={option}
                type="button"
                className={cx(
                  "act",
                  `act-${option}`,
                  reaction === option && "act-on",
                )}
                title={verdicts[option].label}
                onClick={() => {
                  send({
                    t: "react",
                    id: el.id,
                    anchor,
                    reaction: reaction === option ? null : option,
                  });
                }}
              >
                <Icon name={verdicts[option].icon} size={13} />
              </button>
            ))}
            <button
              type="button"
              className="act"
              title="Comment"
              onClick={() => {
                setComposing(true);
                setOpen(true);
              }}
            >
              <Icon name="message" size={13} />
            </button>
            {onRemove === undefined ? null : (
              <button
                type="button"
                className="act act-reject"
                onClick={onRemove}
                title="Remove"
              >
                <Icon name="trash" size={13} />
              </button>
            )}
          </div>
        )}
        {thread === "inline" || open ? (
          <div
            className={
              thread === "popover" ? "thread-popover" : "anchor-thread"
            }
          >
            <Thread
              id={el.id}
              anchor={anchor}
              comments={comments}
              composing={composing}
              onDone={() => {
                setComposing(false);
                if (thread === "popover") setOpen(false);
              }}
            />
          </div>
        ) : null}
      </div>
    );
  },
);
Anchor.displayName = "Anchor";
