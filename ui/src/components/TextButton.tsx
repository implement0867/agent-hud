import type { ReactNode } from "react";

export type TTextButtonVariant = "link" | "onDark";

const variants: Record<TTextButtonVariant, string> = {
  link: "font-semibold text-accent-strong hover:underline",
  onDark:
    "font-semibold text-surface underline decoration-surface/40 underline-offset-2 hover:decoration-surface",
};

type TTextButtonProps = {
  variant: TTextButtonVariant;
  label?: string;
  onClick: () => void;
  children: ReactNode;
};

/** A button that reads as a link; a press keeps the focus where it is, so that a field's blur does not change what is under the click. */
export const TextButton = ({
  variant,
  label,
  onClick,
  children,
}: TTextButtonProps) => (
  <button
    type="button"
    aria-label={label}
    className={variants[variant]}
    onPointerDown={(event) => {
      event.preventDefault();
    }}
    onClick={onClick}
  >
    {children}
  </button>
);
