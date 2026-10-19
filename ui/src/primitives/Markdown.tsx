import { memo } from "react";
import type { ComponentProps } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const plugins = [remarkGfm];

const Link = ({
  node: _node,
  ...props
}: ComponentProps<"a"> & { node?: unknown }) => (
  <a {...props} target="_blank" rel="noreferrer" />
);

const components: Components = { a: Link };

type MarkdownProps = { text: string; inline?: boolean };

/** Markdown without raw HTML. `inline` lays a single paragraph out as running text. */
export const Markdown = memo(({ text, inline = false }: MarkdownProps) => (
  <div className={inline ? "md md-inline" : "md"}>
    <ReactMarkdown remarkPlugins={plugins} components={components}>
      {text}
    </ReactMarkdown>
  </div>
));
Markdown.displayName = "Markdown";
