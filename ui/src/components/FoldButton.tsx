type TFoldButtonProps = {
  folded: boolean;
  /** What the button folds, for its label: the card, or a section by its heading. */
  label: string;
  toggle: () => void;
  className?: string;
};

/**
 * The triangle that folds a card or a section, down while it is open and right while it is folded. A press neither
 * selects nor drags the card, and a double click does not open the editor. It shows no words of the card.
 */
export const FoldButton = ({
  folded,
  label,
  toggle,
  className = "",
}: TFoldButtonProps) => (
  <button
    type="button"
    data-chrome=""
    aria-expanded={!folded}
    aria-label={`${folded ? "Open" : "Fold"} ${label}`}
    className={`grid cursor-pointer place-items-center rounded-sm text-ink-faint select-none hover:text-ink-soft ${className}`}
    onPointerDown={(event) => {
      event.stopPropagation();
    }}
    onDoubleClick={(event) => {
      event.stopPropagation();
    }}
    onClick={(event) => {
      event.stopPropagation();
      toggle();
    }}
  >
    <svg
      viewBox="0 0 10 10"
      aria-hidden
      className="block size-2.5 fill-current"
    >
      <path d={folded ? "M3 1.5 8 5 3 8.5Z" : "M1.5 3 8.5 3 5 8Z"} />
    </svg>
  </button>
);
