import type { ComponentProps } from "react";
import Markdown, { MarkdownHooks } from "react-markdown";
import type { ExtraProps } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { PluggableList } from "unified";

import { Anchor } from "~/components/markdown/Anchor";
import { Cell, HeaderCell, TaskBox } from "~/components/markdown/Boxes";
import { Pre, Span } from "~/components/markdown/Code";
import { Heading, Section } from "~/components/markdown/Sections";
import { markBoxCells } from "~/lib/boxes";
import { markCodeLines } from "~/lib/codeLines";
import { highlight } from "~/lib/highlight";

const components = {
  section: Section,
  h1: (props: ComponentProps<"h1"> & ExtraProps) => (
    <Heading tag="h1" {...props} />
  ),
  h2: (props: ComponentProps<"h2"> & ExtraProps) => (
    <Heading tag="h2" {...props} />
  ),
  h3: (props: ComponentProps<"h3"> & ExtraProps) => (
    <Heading tag="h3" {...props} />
  ),
  h4: (props: ComponentProps<"h4"> & ExtraProps) => (
    <Heading tag="h4" {...props} />
  ),
  h5: (props: ComponentProps<"h5"> & ExtraProps) => (
    <Heading tag="h5" {...props} />
  ),
  h6: (props: ComponentProps<"h6"> & ExtraProps) => (
    <Heading tag="h6" {...props} />
  ),
  a: Anchor,
  span: Span,
  pre: Pre,
  td: Cell,
  th: HeaderCell,
  input: TaskBox,
};

const remarkPlugins = [remarkGfm];

/** Whether the markdown has a fenced code block, which the colouring loads the highlighter for. */
const hasFence = (md: string) => /^\s*(```|~~~)/m.test(md);

type TCardMarkdownProps = {
  md: string;
  plugins: PluggableList;
};

/**
 * The card's markdown on the design's scale, through the plugins that run on its own elements before the colouring:
 * code blocks on the sunken ground and a table's boxes as checkboxes. A card with a code block shows plain until the
 * highlighter loads.
 */
export const CardMarkdown = ({ md, plugins }: TCardMarkdownProps) => {
  const plain = [markBoxCells, ...plugins, markCodeLines];
  const markdown = (
    <Markdown
      remarkPlugins={remarkPlugins}
      rehypePlugins={plain}
      components={components}
    >
      {md}
    </Markdown>
  );
  return (
    <div data-text-root="" className="markdown select-text">
      {hasFence(md) ? (
        <MarkdownHooks
          remarkPlugins={remarkPlugins}
          rehypePlugins={[markBoxCells, ...plugins, highlight, markCodeLines]}
          components={components}
          fallback={markdown}
        >
          {md}
        </MarkdownHooks>
      ) : (
        markdown
      )}
    </div>
  );
};
