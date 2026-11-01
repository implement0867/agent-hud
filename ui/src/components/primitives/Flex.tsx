import type { ReactNode } from "react";

type TDirection = "row" | "column";

type TGap =
  | 0
  | "px"
  | 0.5
  | 1
  | 1.5
  | 2
  | 2.5
  | 3
  | 3.5
  | 4
  | 5
  | 6
  | 7
  | 8
  | 9
  | 10
  | 11
  | 12;

type TAlign =
  | "start"
  | "end"
  | "end-safe"
  | "center"
  | "center-safe"
  | "baseline"
  | "baseline-last"
  | "stretch";

type TJustify =
  | "start"
  | "end"
  | "end-safe"
  | "center"
  | "center-safe"
  | "between"
  | "around"
  | "evenly"
  | "stretch"
  | "baseline"
  | "normal";

type TWrap = "wrap" | "wrap-reverse" | "nowrap";

type TVoidElement =
  | "area"
  | "base"
  | "br"
  | "col"
  | "embed"
  | "hr"
  | "img"
  | "input"
  | "link"
  | "meta"
  | "source"
  | "track"
  | "wbr";

type TFlexElement = Exclude<keyof HTMLElementTagNameMap, TVoidElement>;

const forwards: Record<TDirection, string> = {
  row: "flex",
  column: "flex flex-col",
};

const reverses: Record<TDirection, string> = {
  row: "flex flex-row-reverse",
  column: "flex flex-col-reverse",
};

const gaps: Record<TGap, string> = {
  0: "gap-0",
  px: "gap-px",
  0.5: "gap-0.5",
  1: "gap-1",
  1.5: "gap-1.5",
  2: "gap-2",
  2.5: "gap-2.5",
  3: "gap-3",
  3.5: "gap-3.5",
  4: "gap-4",
  5: "gap-5",
  6: "gap-6",
  7: "gap-7",
  8: "gap-8",
  9: "gap-9",
  10: "gap-10",
  11: "gap-11",
  12: "gap-12",
};

const aligns: Record<TAlign, string> = {
  start: "items-start",
  end: "items-end",
  "end-safe": "items-end-safe",
  center: "items-center",
  "center-safe": "items-center-safe",
  baseline: "items-baseline",
  "baseline-last": "items-baseline-last",
  stretch: "items-stretch",
};

const justifies: Record<TJustify, string> = {
  start: "justify-start",
  end: "justify-end",
  "end-safe": "justify-end-safe",
  center: "justify-center",
  "center-safe": "justify-center-safe",
  between: "justify-between",
  around: "justify-around",
  evenly: "justify-evenly",
  stretch: "justify-stretch",
  baseline: "justify-baseline",
  normal: "justify-normal",
};

const wraps: Record<TWrap, string> = {
  wrap: "flex-wrap",
  "wrap-reverse": "flex-wrap-reverse",
  nowrap: "flex-nowrap",
};

type TFlexProps = {
  as?: TFlexElement;
  gap?: TGap;
  align?: TAlign;
  justify?: TJustify;
  wrap?: TWrap;
  reverse?: boolean;
  children: ReactNode;
};

const renderFlex = (
  direction: TDirection,
  {
    as: Element = "div",
    gap,
    align,
    justify,
    wrap,
    reverse = false,
    children,
  }: TFlexProps,
) => (
  <Element
    className={[
      (reverse ? reverses : forwards)[direction],
      gap === undefined ? "" : gaps[gap],
      align === undefined ? "" : aligns[align],
      justify === undefined ? "" : justifies[justify],
      wrap === undefined ? "" : wraps[wrap],
    ]
      .filter((name) => name !== "")
      .join(" ")}
  >
    {children}
  </Element>
);

export const Row = (props: TFlexProps) => renderFlex("row", props);

export const Column = (props: TFlexProps) => renderFlex("column", props);
