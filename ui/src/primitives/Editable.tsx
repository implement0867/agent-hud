import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, KeyboardEvent, ReactNode } from "react";

const stop = (e: { stopPropagation: () => void }) => {
  e.stopPropagation();
};

type EditableProps = {
  value: string;
  onCommit: (value: string) => void;
  /** Rendered while not editing. */
  children: ReactNode;
  /** Start editing on a single click instead of a double click. */
  eager?: boolean;
  placeholder?: string;
  className?: string;
};

/** Double-click to edit; Enter commits, Shift+Enter adds a line, Escape cancels. */
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

  const start = useCallback(() => {
    setDraft(value);
  }, [value]);

  const finish = useCallback(
    (commit: boolean) => {
      if (commit && draft !== null && draft !== value) onCommit(draft);
      setDraft(null);
    },
    [draft, value, onCommit],
  );

  const onChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    setDraft(e.target.value);
  }, []);

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Escape") finish(false);
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        finish(true);
      }
      e.stopPropagation();
    },
    [finish],
  );

  const onBlur = useCallback(() => {
    finish(true);
  }, [finish]);

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
      onChange={onChange}
      onKeyDown={onKeyDown}
      onBlur={onBlur}
      onPointerDown={stop}
      autoFocus
      rows={1}
    />
  );
};
