import rehypeShikiFromHighlighter from "@shikijs/rehype/core";
import type { Root } from "hast";
import type { VFile } from "vfile";
import {
  createBundledHighlighter,
  createSingletonShorthands,
} from "shiki/core";
import { createOnigurumaEngine } from "shiki/engine/oniguruma";
import { bundledLanguages } from "shiki/langs";

const theme = "github-dark";

const { getSingletonHighlighter } = createSingletonShorthands(
  createBundledHighlighter({
    langs: bundledLanguages,
    themes: { [theme]: () => import("shiki/themes/github-dark.mjs") },
    engine: () => createOnigurumaEngine(import("shiki/wasm")),
  }),
);

/**
 * A rehype plugin that colours fenced code blocks.
 * The first code block loads the one chunk with Shiki's grammars, theme and WebAssembly; a language Shiki does not know shows as plain text.
 */
export const highlight = () => async (tree: Root, file: VFile) => {
  const highlighter = await getSingletonHighlighter({
    themes: [theme],
    langs: [],
  });
  await rehypeShikiFromHighlighter(highlighter, {
    theme,
    lazy: true,
    fallbackLanguage: "text",
  })(tree, file, () => undefined);
};
