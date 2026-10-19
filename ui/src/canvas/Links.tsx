import { memo, useCallback } from "react";

import type { LinkLayer, Register } from "~/canvas/useLinkLayer";
import { cx } from "~/lib/cx";
import { useStore } from "~/lib/store";
import type { LinkEl } from "~/protocol/schema";
import { select, uiStore } from "~/store/ui";

export const LinkPaths = ({ links, register }: LinkLayer) => {
  const selected = useStore(uiStore, (s) => s.selected);
  return (
    <svg className="links" width={1} height={1}>
      <defs>
        {(["agent", "user"] as const).map((author) => (
          <marker
            key={author}
            id={`arrowhead-${author}`}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" className={`arrowhead-${author}`} />
          </marker>
        ))}
      </defs>
      {links.map((link) => (
        <LinkPath
          key={link.id}
          link={link}
          selected={selected === link.id}
          register={register}
        />
      ))}
    </svg>
  );
};

export const LinkTexts = ({ links, register }: LinkLayer) => (
  <svg className="links links-text" width={1} height={1}>
    {links.map((link) =>
      link.text === null ? null : (
        <LinkText key={link.id} link={link} register={register} />
      ),
    )}
  </svg>
);

type PathProps = { link: LinkEl; selected: boolean; register: Register };

const LinkPath = memo(({ link, selected, register }: PathProps) => {
  const setLine = useCallback(
    (node: SVGPathElement | null) => {
      register(link.id, "line", node);
    },
    [register, link.id],
  );
  const setHit = useCallback(
    (node: SVGPathElement | null) => {
      register(link.id, "hit", node);
    },
    [register, link.id],
  );
  return (
    <g
      className={cx("link", `link-${link.author}`, selected && "link-selected")}
    >
      <path
        ref={setHit}
        className="link-hit"
        onPointerDown={(e) => {
          e.stopPropagation();
          select(link.id);
        }}
      />
      <path
        ref={setLine}
        className="link-line"
        markerEnd={`url(#arrowhead-${link.author})`}
      />
    </g>
  );
});
LinkPath.displayName = "LinkPath";

type TextProps = { link: LinkEl; register: Register };

const LinkText = memo(({ link, register }: TextProps) => {
  const setText = useCallback(
    (node: SVGTextElement | null) => {
      register(link.id, "text", node);
    },
    [register, link.id],
  );
  return (
    <text ref={setText} className={`link-text link-text-${link.author}`}>
      {link.text}
    </text>
  );
});
LinkText.displayName = "LinkText";
