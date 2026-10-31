import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CardBody } from "~/components/CardBody";

const renderCard = (md: string, sections: string[] | null) =>
  renderToStaticMarkup(
    createElement(CardBody, {
      md,
      folds:
        sections === null
          ? null
          : {
              sections,
              toggle: () => undefined,
            },
    }),
  );

describe("CardBody", () => {
  const md = "Lead.\n\n## Steps\n\nDo it.\n\n## Risks\n\nNone.";

  it("gives each heading a triangle that folds its section where the card folds", () => {
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

  it("shows no triangles on a card that does not fold, such as an earlier version", () => {
    expect(renderCard(md, null)).not.toContain("<button");
  });
});
