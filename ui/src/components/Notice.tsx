import type { ReactNode } from "react";

export const Notice = ({ children }: { children: ReactNode }) => (
  <p className="m-auto text-stone-500">{children}</p>
);
