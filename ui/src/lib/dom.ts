export const stop = (e: { stopPropagation: () => void }) => {
  e.stopPropagation();
};

/** The event target is a field the user types into, so key shortcuts must not fire. */
export const isTyping = (target: EventTarget | null): boolean =>
  target instanceof HTMLElement &&
  (target.isContentEditable ||
    target.closest("input, textarea, select") !== null);
