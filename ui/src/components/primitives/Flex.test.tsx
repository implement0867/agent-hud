import { __unstable__loadDesignSystem } from "@tailwindcss/node";
import type { ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Column, Row } from "~/components/primitives/Flex";

const designSystem = await __unstable__loadDesignSystem(
  '@import "./index.css";',
  {
    base: new URL("../../", import.meta.url).pathname,
  },
);

type TFlexProps = Omit<ComponentProps<typeof Row>, "children">;

const renderFlex = (Component: typeof Row, props: TFlexProps) =>
  renderToStaticMarkup(<Component {...props}>child</Component>);

const deliverCss = (markup: string) => {
  const match = /class="([^"]*)"/.exec(markup);
  if (match?.[1] === undefined) throw new Error(`No class in ${markup}`);
  const rules = designSystem.candidatesToCss(match[1].split(" "));
  expect(rules).not.toContain(null);
  return rules.join("");
};

describe("Row and Column", () => {
  it("renders Row as a div whose only class is flex", () => {
    expect(renderFlex(Row, {})).toBe('<div class="flex">child</div>');
  });

  it("renders Column as a div whose only classes are flex flex-col", () => {
    expect(renderFlex(Column, {})).toBe(
      '<div class="flex flex-col">child</div>',
    );
  });

  it("renders the element that as names", () => {
    expect(renderFlex(Row, { as: "ul" })).toBe('<ul class="flex">child</ul>');
    expect(renderFlex(Column, { as: "section" })).toBe(
      '<section class="flex flex-col">child</section>',
    );
  });

  it("reverses the direction of Row and Column", () => {
    expect(deliverCss(renderFlex(Row, { reverse: true }))).toContain(
      "flex-direction: row-reverse;",
    );
    expect(deliverCss(renderFlex(Column, { reverse: true }))).toContain(
      "flex-direction: column-reverse;",
    );
  });

  it.each([
    0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75,
    4, 4.25, 4.5, 4.75, 5, 5.25, 5.5, 5.75, 6, 6.25, 6.5, 6.75, 7, 7.25, 7.5,
    7.75, 8, 8.25, 8.5, 8.75, 9, 9.25, 9.5, 9.75, 10, 10.25, 10.5, 10.75, 11,
    11.25, 11.5, 11.75, 12,
  ] as const)("delivers a gap of %s spacing steps", (gap) => {
    expect(deliverCss(renderFlex(Row, { gap }))).toContain(
      gap === 1
        ? "gap: var(--spacing);"
        : `gap: calc(var(--spacing) * ${String(gap)});`,
    );
  });

  it.each([
    ["start", "flex-start"],
    ["end", "flex-end"],
    ["end-safe", "safe flex-end"],
    ["center", "center"],
    ["center-safe", "safe center"],
    ["baseline", "baseline"],
    ["baseline-last", "last baseline"],
    ["stretch", "stretch"],
  ] as const)("delivers align %s as align-items: %s", (align, value) => {
    expect(deliverCss(renderFlex(Row, { align }))).toContain(
      `align-items: ${value};`,
    );
  });

  it.each([
    ["start", "flex-start"],
    ["end", "flex-end"],
    ["end-safe", "safe flex-end"],
    ["center", "center"],
    ["center-safe", "safe center"],
    ["between", "space-between"],
    ["around", "space-around"],
    ["evenly", "space-evenly"],
    ["stretch", "stretch"],
    ["baseline", "baseline"],
    ["normal", "normal"],
  ] as const)(
    "delivers justify %s as justify-content: %s",
    (justify, value) => {
      expect(deliverCss(renderFlex(Row, { justify }))).toContain(
        `justify-content: ${value};`,
      );
    },
  );

  it.each(["wrap", "wrap-reverse", "nowrap"] as const)(
    "delivers wrap %s",
    (wrap) => {
      expect(deliverCss(renderFlex(Row, { wrap }))).toContain(
        `flex-wrap: ${wrap};`,
      );
    },
  );
});
