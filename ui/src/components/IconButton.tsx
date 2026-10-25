import type { ReactNode } from "react";

export type TIconButtonVariant = "ghost" | "close" | "tool";

const variants: Record<TIconButtonVariant, string> = {
  ghost:
    "grid size-6 place-items-center rounded-md text-ink-faint hover:bg-edge-faint hover:text-ink-soft",
  close:
    "rounded p-1 text-ink-faint hover:bg-surface-sunken hover:text-ink-soft",
  tool: "flex h-9 min-w-9 items-center justify-center gap-1.5 rounded-xl px-2 text-sm text-ink-soft transition-colors hover:bg-surface-sunken hover:text-ink aria-pressed:bg-accent-soft aria-pressed:text-accent-strong",
};

type TIconButtonProps = {
  variant: TIconButtonVariant;
  label: string;
  /** The tooltip, when it says more than the label. */
  title?: string;
  /** Whether the button's state is on, for a toggle. */
  pressed?: boolean;
  onClick: () => void;
  children: ReactNode;
};

/** A button with an icon and a label for assistive technology; its press and click stay on it, not on the card or board under it. */
export const IconButton = ({
  variant,
  label,
  title = label,
  pressed,
  onClick,
  children,
}: TIconButtonProps) => (
  <button
    type="button"
    aria-label={label}
    aria-pressed={pressed}
    title={title}
    className={variants[variant]}
    onPointerDown={(event) => {
      event.stopPropagation();
    }}
    onClick={(event) => {
      event.stopPropagation();
      onClick();
    }}
  >
    {children}
  </button>
);
