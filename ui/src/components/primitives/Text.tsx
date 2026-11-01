import type { ReactNode } from "react";

type TTextSize = "xs" | "sm" | "md" | "lg" | "xl";

type TTextTone =
  | "ink"
  | "soft"
  | "muted"
  | "faint"
  | "ghost"
  | "accent"
  | "warning"
  | "danger"
  | "onAccent";

type TTextWeight = 400 | 500 | 600;

type TTextElement = "span" | "p" | "h1" | "h2" | "h3" | "dd" | "li";

const sizes: Record<TTextSize, string> = {
  xs: "text-xs",
  sm: "text-sm",
  md: "text-md",
  lg: "text-lg",
  xl: "text-xl",
};

const tones: Record<TTextTone, string> = {
  ink: "text-ink",
  soft: "text-ink-soft",
  muted: "text-ink-muted",
  faint: "text-ink-faint",
  ghost: "text-ink-ghost",
  accent: "text-accent-strong",
  warning: "text-warning-strong",
  danger: "text-danger-strong",
  onAccent: "text-on-accent",
};

const weights: Record<TTextWeight, string> = {
  400: "font-normal",
  500: "font-medium",
  600: "font-semibold",
};

type TTextProps = {
  as?: TTextElement;
  size?: TTextSize;
  tone?: TTextTone;
  weight?: TTextWeight;
  mono?: boolean;
  truncate?: boolean;
  children: ReactNode;
};

export const Text = ({
  as: Element = "span",
  size,
  tone,
  weight,
  mono = false,
  truncate = false,
  children,
}: TTextProps) => (
  <Element
    className={[
      size === undefined ? "" : sizes[size],
      tone === undefined ? "" : tones[tone],
      weight === undefined ? "" : weights[weight],
      mono ? "font-mono" : "",
      truncate ? "truncate" : "",
    ]
      .filter((name) => name !== "")
      .join(" ")}
  >
    {children}
  </Element>
);
