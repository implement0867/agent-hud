import type { ReactNode } from "react";

type TDirection = "row" | "column";

type TGap = 0.5 | 1 | 2;

type TAlign = "center";

type TJustify = "end";

type TFlexElement = "div" | "span" | "ul";

const directions: Record<TDirection, string> = {
  row: "flex",
  column: "flex flex-col",
};

const gaps: Record<TGap, string> = {
  0.5: "gap-0.5",
  1: "gap-1",
  2: "gap-2",
};

const aligns: Record<TAlign, string> = {
  center: "items-center",
};

const justifies: Record<TJustify, string> = {
  end: "justify-end",
};

type TFlexProps = {
  as?: TFlexElement;
  gap?: TGap;
  align?: TAlign;
  justify?: TJustify;
  wrap?: boolean;
  children: ReactNode;
};

const composeFlexClasses = (
  direction: TDirection,
  { gap, align, justify, wrap = false }: TFlexProps,
) =>
  [
    directions[direction],
    gap === undefined ? "" : gaps[gap],
    align === undefined ? "" : aligns[align],
    justify === undefined ? "" : justifies[justify],
    wrap ? "flex-wrap" : "",
  ]
    .filter((name) => name !== "")
    .join(" ");

export const Row = (props: TFlexProps) => {
  const { as: Element = "div", children } = props;
  return (
    <Element className={composeFlexClasses("row", props)}>{children}</Element>
  );
};

export const Column = (props: TFlexProps) => {
  const { as: Element = "div", children } = props;
  return (
    <Element className={composeFlexClasses("column", props)}>
      {children}
    </Element>
  );
};
