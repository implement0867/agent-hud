import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { stop } from "~/lib/dom";

type EditableProps = {
  value: string;
  onCommit: (value: string) => void;
  children: ReactNode;
  /** Edit on a single click instead of a double click. */
  eager?: boolean;
  placeholder?: string;
  className?: string;
};

/** Enter commits, Shift+Enter adds a line, Escape cancels. */
export const Editable = ({
  value,
  onCommit,
  children,
  eager = false,
  placeholder,
  className,
}: EditableProps) => {
  const [draft, setDraft] = useState<string | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const area = ref.current;
    if (draft === null || area === null) return;
    area.style.height = "0px";
    area.style.height = `${String(area.scrollHeight)}px`;
  }, [draft]);

  const finish = (commit: boolean) => {
    if (commit && draft !== null && draft !== value) onCommit(draft);
    setDraft(null);
  };
  const start = () => {
    setDraft(value);
  };

  if (draft === null) {
    return (
      <div
        className={`editable ${className ?? ""}`}
        onDoubleClick={eager ? undefined : start}
        onClick={eager ? start : undefined}
        title={eager ? "Click to edit" : "Double-click to edit"}
      >
        {value === "" && placeholder !== undefined ? (
          <span className="placeholder">{placeholder}</span>
        ) : (
          children
        )}
      </div>
    );
  }
  return (
    <textarea
      ref={ref}
      className={`editor ${className ?? ""}`}
      value={draft}
      onChange={(e) => {
        setDraft(e.target.value);
      }}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Escape") finish(false);
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          finish(true);
        }
      }}
      onBlur={() => {
        finish(true);
      }}
      onPointerDown={stop}
      autoFocus
      rows={1}
    />
  );
};
