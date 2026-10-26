import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  cardTitle,
  keeps,
  placesIn,
  plainText,
  squeeze,
  toggledBox,
} from "~/domain/text";

describe("plainText", () => {
  it("has the words the page shows, as the server's text has them", () => {
    const md = [
      "# Plan",
      "",
      "Ship **the** board ~~x~~ &amp; more",
      "",
      "- [ ] task one",
      "- b",
      "",
      "| | Step |",
      "|---|---|",
      "| [x] | parse |",
      "",
      "```py file=a.py",
      "x = 1",
      "```",
    ].join("\n");
    // The server's text_of gives "Plan\nShip the board x & more\ntask one\nb\n\nStep\n\nparse\nx = 1".
    expect(squeeze(plainText(md))).toBe(
      "PlanShiptheboardx&moretaskonebStepparsex=1",
    );
  });
});

describe("placesIn", () => {
  it("finds each place of the quote, whatever its white space, and overlapping places", () => {
    expect(placesIn("a b a b a", "a  b")).toEqual([0, 2]);
    expect(placesIn("aaa", "aa")).toEqual([0, 1]);
    expect(placesIn("abc", "")).toEqual([0]);
    expect(placesIn("abc", "x")).toEqual([]);
  });

  it("finds a quote cut from the text where it was cut", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1 }),
        fc.nat(),
        fc.nat(),
        (text, a, b) => {
          const squeezed = squeeze(text);
          if (squeezed === "") return;
          const from = a % squeezed.length;
          const to = from + 1 + (b % (squeezed.length - from));
          expect(placesIn(text, squeezed.slice(from, to))).toContain(from);
        },
      ),
    );
  });
});

describe("keeps", () => {
  it("tells whether the markdown still shows the words", () => {
    expect(keeps("1. parse the input", "the input")).toBe(true);
    expect(keeps("1. parse", "the input")).toBe(false);
    expect(keeps("anything", "")).toBe(true);
  });
});

describe("toggledBox", () => {
  it("flips the first box in the markdown of the item or cell", () => {
    const md = "- [ ] one\n- [x] two";
    expect(toggledBox(md, 0, 9)).toBe("- [x] one\n- [x] two");
    expect(toggledBox(md, 10, md.length)).toBe("- [ ] one\n- [ ] two");
    expect(toggledBox(md, 2, 3)).toBe(md);
  });
});

describe("cardTitle", () => {
  it("is the heading's text, or a table's first header cell", () => {
    expect(cardTitle("# The plan\n\n1. a")).toBe("The plan");
    expect(cardTitle("| | Task |\n|---|---|")).toBe("Task");
  });
});
