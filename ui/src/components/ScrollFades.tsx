type TScrollFadesProps = { top: boolean; bottom: boolean };

/** The fades at the ends of a card that scrolls, at each end that has more text past it. */
export const ScrollFades = ({ top, bottom }: TScrollFadesProps) => (
  <>
    {top ? (
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-7 rounded-t-card bg-linear-to-b from-surface to-transparent"
      />
    ) : null}
    {bottom ? (
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-7 rounded-b-card bg-linear-to-t from-surface to-transparent"
      />
    ) : null}
  </>
);
