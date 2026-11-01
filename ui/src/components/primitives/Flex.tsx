import type { ReactNode } from "react";

type TDirection = "row" | "column";

type TGap =
  | 0.25
  | 0.5
  | 0.75
  | 1
  | 1.25
  | 1.5
  | 1.75
  | 2
  | 2.25
  | 2.5
  | 2.75
  | 3
  | 3.25
  | 3.5
  | 3.75
  | 4
  | 4.25
  | 4.5
  | 4.75
  | 5
  | 5.25
  | 5.5
  | 5.75
  | 6
  | 6.25
  | 6.5
  | 6.75
  | 7
  | 7.25
  | 7.5
  | 7.75
  | 8
  | 8.25
  | 8.5
  | 8.75
  | 9
  | 9.25
  | 9.5
  | 9.75
  | 10
  | 10.25
  | 10.5
  | 10.75
  | 11
  | 11.25
  | 11.5
  | 11.75
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
  0.25: "gap-0.25",
  0.5: "gap-0.5",
  0.75: "gap-0.75",
  1: "gap-1",
  1.25: "gap-1.25",
  1.5: "gap-1.5",
  1.75: "gap-1.75",
  2: "gap-2",
  2.25: "gap-2.25",
  2.5: "gap-2.5",
  2.75: "gap-2.75",
  3: "gap-3",
  3.25: "gap-3.25",
  3.5: "gap-3.5",
  3.75: "gap-3.75",
  4: "gap-4",
  4.25: "gap-4.25",
  4.5: "gap-4.5",
  4.75: "gap-4.75",
  5: "gap-5",
  5.25: "gap-5.25",
  5.5: "gap-5.5",
  5.75: "gap-5.75",
  6: "gap-6",
  6.25: "gap-6.25",
  6.5: "gap-6.5",
  6.75: "gap-6.75",
  7: "gap-7",
  7.25: "gap-7.25",
  7.5: "gap-7.5",
  7.75: "gap-7.75",
  8: "gap-8",
  8.25: "gap-8.25",
  8.5: "gap-8.5",
  8.75: "gap-8.75",
  9: "gap-9",
  9.25: "gap-9.25",
  9.5: "gap-9.5",
  9.75: "gap-9.75",
  10: "gap-10",
  10.25: "gap-10.25",
  10.5: "gap-10.5",
  10.75: "gap-10.75",
  11: "gap-11",
  11.25: "gap-11.25",
  11.5: "gap-11.5",
  11.75: "gap-11.75",
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
