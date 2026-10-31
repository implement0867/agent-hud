import { createContext, useCallback, useContext, useState } from "react";
import { z } from "zod";

/** The viewer's look of the page, which the browser keeps: the theme, the accent, the density, the radius and the card text. */
export const lookSchema = z.object({
  theme: z.enum(["light", "dark"]).describe("The light or the dark theme"),
  accent: z
    .enum(["sky", "violet", "emerald", "amber"])
    .describe("The colour of selection, threads and links"),
  density: z
    .enum(["comfortable", "compact"])
    .describe("The padding and the leading of the cards"),
  radius: z.enum(["8", "12", "16"]).describe("The corner radius of a card"),
  text: z
    .enum(["0.75", "0.875", "1", "1.0625"])
    .describe("The size of a card's body text, in rem"),
  marks: z
    .enum(["margin", "inline"])
    .describe(
      "Where a thread's bubble shows: in the card's margin, or after its words",
    ),
  diff: z
    .enum(["word", "line"])
    .describe("How a new version shows its changes: words, or whole lines"),
});

export type TLook = z.infer<typeof lookSchema>;

export const lookKey = "agent-hud-look";

const systemTheme = (): TLook["theme"] =>
  window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

const defaults = (): TLook => ({
  theme: systemTheme(),
  accent: "sky",
  density: "comfortable",
  radius: "12",
  text: "0.875",
  marks: "margin",
  diff: "word",
});

/** The look the browser keeps, with the default for each choice it does not have or cannot read. */
export const readLook = (): TLook => {
  const look = defaults();
  try {
    const kept = z
      .record(z.string(), z.unknown())
      .safeParse(JSON.parse(localStorage.getItem(lookKey) ?? "{}"));
    if (!kept.success) return look;
    const fields = lookSchema.shape;
    return {
      theme: fields.theme.catch(look.theme).parse(kept.data["theme"]),
      accent: fields.accent.catch(look.accent).parse(kept.data["accent"]),
      density: fields.density.catch(look.density).parse(kept.data["density"]),
      radius: fields.radius.catch(look.radius).parse(kept.data["radius"]),
      text: fields.text.catch(look.text).parse(kept.data["text"]),
      marks: fields.marks.catch(look.marks).parse(kept.data["marks"]),
      diff: fields.diff.catch(look.diff).parse(kept.data["diff"]),
    };
  } catch {
    return look;
  }
};

/** Sets the look on the root element, where the stylesheet reads it. */
export const applyLook = (look: TLook) => {
  const root = document.documentElement;
  root.dataset["theme"] = look.theme;
  root.dataset["accent"] = look.accent;
  root.dataset["density"] = look.density;
  root.dataset["radius"] = look.radius;
  root.style.setProperty("--text-body", `${look.text}rem`);
};

/** The viewer's look and a setter that applies a change and keeps it in the browser. */
export const useLook = () => {
  const [look, setLook] = useState(readLook);
  const change = useCallback((patch: Partial<TLook>) => {
    setLook((current) => {
      const next = { ...current, ...patch };
      applyLook(next);
      try {
        localStorage.setItem(lookKey, JSON.stringify(next));
      } catch {
        // A browser that keeps nothing shows the look until the page reloads.
      }
      return next;
    });
  }, []);
  return [look, change] as const;
};

/** The look, for the cards that show their marks and changes as the viewer chose. */
export const LookContext = createContext<TLook | null>(null);

export const useLookChoice = (): TLook => {
  const look = useContext(LookContext);
  return look ?? readLook();
};
