import type { ComponentProps } from "react";
import type { ExtraProps } from "react-markdown";

/** Links open in a new tab. */
export const Anchor = ({
  href,
  children,
}: ComponentProps<"a"> & ExtraProps) => (
  <a
    href={href}
    target="_blank"
    rel="noreferrer"
    onClick={(event) => {
      event.stopPropagation();
    }}
  >
    {children}
  </a>
);
