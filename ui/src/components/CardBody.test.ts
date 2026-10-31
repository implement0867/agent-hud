import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CardBody, VersionBody } from "~/components/CardBody";

const renderCard = (md: string, sections: string[]) =>
  renderToStaticMarkup(
    createElement(CardBody, {
      md,
      before: null,
      diffStyle: "word",
      toggle: () => undefined,
      folds: {
        label: "card plan",
        toggleCard: () => undefined,
        sections,
        toggleSection: () => undefined,
      },
    }),
  );

describe("CardBody", () => {
  const md = "Lead.\n\n## Steps\n\nDo it.\n\n## Risks\n\nNone.";

  it("gives each heading a triangle that folds its section", () => {
    const html = renderCard(md, []);
    expect(html).toContain('<section data-section="0:Steps">');
    expect(html).toContain('aria-label="Fold the section Steps"');
    expect(html).toContain('aria-label="Fold the section Risks"');
  });

  it("marks a folded section, whose triangle opens it", () => {
    const html = renderCard(md, ["0:Risks"]);
    expect(html).toContain('<section data-section="0:Risks" data-folded="">');
    expect(html).toContain('aria-label="Open the section Risks"');
    expect(html).toContain('<section data-section="0:Steps">');
  });

  it("gives a heading that is the card's first block the card's triangle, not a section's", () => {
    const html = renderCard("# Plan\n\nText.\n\n## Steps\n\nDo.", []);
    expect(html).toContain('aria-label="Fold card plan"');
    expect(html).not.toContain('aria-label="Fold the section Plan"');
    expect(html).toContain('aria-label="Fold the section Steps"');
  });

  it("renders a footnote's section and a nested heading, which have no fold", () => {
    const html = renderCard("Text.[^1]\n\n> ### Aside\n\n[^1]: A note.", []);
    expect(html).toContain("data-footnotes");
    expect(html).not.toContain('aria-label="Fold the section Aside"');
  });

  it("lets a click flip a box", () => {
    expect(renderCard("- [ ] Do it", [])).not.toContain("disabled");
  });
});

describe("VersionBody", () => {
  it("shows no triangles on an earlier version, whose sections stay open", () => {
    const html = renderToStaticMarkup(
      createElement(VersionBody, {
        md: "Lead.\n\n## Steps\n\nDo it.",
      }),
    );
    expect(html).toContain('<section data-section="0:Steps">');
    expect(html).not.toContain("<button");
  });

  it("shows an earlier version's task boxes, which do not flip", () => {
    const html = renderToStaticMarkup(
      createElement(VersionBody, { md: "- [x] Done" }),
    );
    expect(html).toContain('disabled="" checked=""');
  });

  it("shows an earlier version's boxes, which do not flip", () => {
    const html = renderToStaticMarkup(
      createElement(VersionBody, { md: "| Done |\n| --- |\n| [x] |" }),
    );
    expect(html).toContain('type="checkbox"');
    expect(html).toContain("disabled");
  });
});
