import { X } from "lucide-react";

import { IconButton } from "~/components/IconButton";
import { lookSchema } from "~/lib/look";
import type { TLook } from "~/lib/look";
import { Row } from "~/components/primitives/Flex";
import { Text } from "~/components/primitives/Text";

/** The swatch of each accent, in its light value. */
const swatches: Record<TLook["accent"], string> = {
  sky: "#0284c7",
  violet: "#7c3aed",
  emerald: "#059669",
  amber: "#d97706",
};

/** Each choice of the look, with its options in order and the name of each. */
const rows: { key: keyof TLook; title: string; options: [string, string][] }[] =
  [
    {
      key: "theme",
      title: "Theme",
      options: [
        ["light", "light"],
        ["dark", "dark"],
      ],
    },
    {
      key: "accent",
      title: "Accent",
      options: [
        ["sky", "sky"],
        ["violet", "violet"],
        ["emerald", "emerald"],
        ["amber", "amber"],
      ],
    },
    {
      key: "density",
      title: "Density",
      options: [
        ["comfortable", "comfortable"],
        ["compact", "compact"],
      ],
    },
    {
      key: "radius",
      title: "Radius",
      options: [
        ["8", "8"],
        ["12", "12"],
        ["16", "16"],
      ],
    },
    {
      key: "text",
      title: "Text",
      options: [
        ["0.75", "12"],
        ["0.875", "14"],
        ["1", "16"],
        ["1.0625", "17"],
      ],
    },
    {
      key: "marks",
      title: "Threads",
      options: [
        ["margin", "margin"],
        ["inline", "in line"],
      ],
    },
    {
      key: "diff",
      title: "Changes",
      options: [
        ["word", "words"],
        ["line", "lines"],
      ],
    },
  ];

type TLookMenuProps = {
  look: TLook;
  change: (patch: Partial<TLook>) => void;
  close: () => void;
};

/** The viewer's look: the theme, the accent, the density, the radius, the text size, and how threads and changes show. The browser keeps it. */
export const LookMenu = ({ look, change, close }: TLookMenuProps) => (
  <section
    role="dialog"
    aria-label="Look"
    className="panel pointer-events-auto absolute bottom-full left-1/2 mb-2 w-72 -translate-x-1/2 animate-pop p-3 text-md"
    onKeyDown={(event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close();
      }
    }}
  >
    <header className="mb-2 flex items-center justify-between">
      <Text as="h2" size="xl" tone="ink" weight={600}>
        Look
      </Text>
      <IconButton variant="close" label="Close the look" onClick={close}>
        <X className="size-4" />
      </IconButton>
    </header>
    <div className="grid grid-cols-[4.5rem_1fr] items-center gap-x-3 gap-y-2">
      {rows.map(({ key, title, options }) => (
        <div
          key={key}
          role="radiogroup"
          aria-label={title}
          className="contents"
        >
          <Text tone="muted">{title}</Text>
          <Row as="span" wrap gap={1}>
            {options.map(([option, name]) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={look[key] === option}
                aria-label={key === "accent" ? option : undefined}
                title={key === "accent" ? option : undefined}
                className={
                  key === "accent"
                    ? "grid size-6 place-items-center rounded-full ring-offset-2 ring-offset-surface aria-checked:ring-2 aria-checked:ring-ink-muted"
                    : "rounded-bar px-2 py-0.5 text-ink-soft hover:bg-surface-sunken aria-checked:bg-accent-soft aria-checked:text-accent-strong"
                }
                onClick={() => {
                  change(lookSchema.parse({ ...look, [key]: option }));
                }}
              >
                {key === "accent" ? (
                  <span
                    className="size-4 rounded-full"
                    style={{ background: swatches[option as TLook["accent"]] }}
                  />
                ) : (
                  name
                )}
              </button>
            ))}
          </Row>
        </div>
      ))}
    </div>
  </section>
);
