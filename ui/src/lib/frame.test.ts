import { describe, expect, it } from "vitest";

import { FrameMode, findFrameStyle } from "~/lib/frame";
import { columnWidth } from "~/lib/geometry";

describe("findFrameStyle", () => {
  const box = { place: { x: 10, y: 20 }, width: 300, height: 200, layer: 2 };

  it("holds an open card at its height", () => {
    expect(findFrameStyle(FrameMode.enum.open, box)).toMatchObject({
      left: 10,
      top: 20,
      width: 300,
      height: 200,
      zIndex: 2,
      visibility: "visible",
    });
  });

  it("lets a folded card and the editor take the height of what they show", () => {
    expect(findFrameStyle(FrameMode.enum.folded, box).height).toBe("auto");
    expect(findFrameStyle(FrameMode.enum.editing, box).height).toBe("auto");
  });

  it("makes a card without a width as wide as its text, up to a column", () => {
    expect(
      findFrameStyle(FrameMode.enum.open, { ...box, width: null }),
    ).toMatchObject({ width: "max-content", maxWidth: columnWidth });
  });

  it("hides a card without a place", () => {
    expect(
      findFrameStyle(FrameMode.enum.open, { ...box, place: null }).visibility,
    ).toBe("hidden");
  });
});
