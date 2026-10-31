import Markdown, { MarkdownHooks } from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { PluggableList } from "unified";

import { markBoxCells } from "~/lib/boxes";
import { markCodeLines } from "~/lib/codeLines";
import { highlight } from "~/lib/highlight";

const remarkPlugins = [remarkGfm];

/** Whether the markdown has a fenced code block, which the colouring loads the highlighter for. */
const hasFence = (md: string) => /^\s*(```|~~~)/m.test(md);

type TCardMarkdownProps = {
  md: string;
  plugins: PluggableList;
  components: Components;
};

/**
 * The card's markdown on the design's scale, through the plugins that run on its own elements before the colouring and
 * the components that render them:
 * code blocks on the sunken ground and a table's boxes as checkboxes. A card with a code block shows plain until the
 * highlighter loads.
 */
export const CardMarkdown = ({
  md,
  plugins,
  components,
}: TCardMarkdownProps) => {
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
