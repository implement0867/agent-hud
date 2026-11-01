import js from "@eslint/js";
import betterTailwind from "eslint-plugin-better-tailwindcss";
import { getDefaultSelectors } from "eslint-plugin-better-tailwindcss/defaults";
import eslintConfigPrettier from "eslint-config-prettier/flat";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/**", "node_modules/**"] },

  js.configs.recommended,

  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      ...tseslint.configs.strictTypeChecked,
      ...tseslint.configs.stylisticTypeChecked,
      react.configs.flat.recommended,
      react.configs.flat["jsx-runtime"],
      reactHooks.configs.flat.recommended,
    ],
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: {
        project: ["./tsconfig.app.json", "./tsconfig.node.json"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-refresh": reactRefresh,
      "better-tailwindcss": betterTailwind,
    },
    settings: {
      react: { version: "detect" },
      "better-tailwindcss": {
        entryPoint: "src/index.css",
        detectComponentClasses: true,
        selectors: [
          ...getDefaultSelectors(),
          // The variables that hold class strings, so that their classes are checked as a className's are.
          {
            kind: "variable",
            name: "^(?:\\w*Tones?|\\w*Shape|variants|place|ring|belowAnchor|agentDots|sizes|tones|weights)$",
            match: [
              { type: "strings" },
              { type: "objectValues" },
              {
                type: "anonymousFunctionReturn",
                match: [{ type: "strings" }],
              },
            ],
          },
        ],
      },
    },
    linterOptions: {
      // Exceptions go in this file, where review sees them.
      noInlineConfig: true,
    },
    rules: {
      // TypeScript
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/consistent-type-definitions": ["error", "type"],
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/naming-convention": [
        "error",
        { selector: "typeAlias", format: ["PascalCase"], prefix: ["T"] },
        { selector: "interface", format: ["PascalCase"], prefix: ["I"] },
      ],
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/ban-ts-comment": [
        "error",
        {
          "ts-expect-error": true,
          "ts-ignore": true,
          "ts-nocheck": true,
          "ts-check": false,
        },
      ],
      "@typescript-eslint/no-unused-expressions": [
        "error",
        { allowShortCircuit: true, allowTernary: true },
      ],
      "no-console": "warn",
      // const arrow functions over function declarations
      "func-style": ["error", "expression"],
      "prefer-arrow-callback": "error",

      // React
      "react/prop-types": "off",
      "react/self-closing-comp": "error",
      "react/jsx-boolean-value": ["error", "never"],
      "react/jsx-no-useless-fragment": "warn",
      "react/jsx-no-target-blank": "off",
      "react/no-array-index-key": "error",
      "react/no-unstable-nested-components": "error",
      "react/jsx-no-leaked-render": "error",
      "react/jsx-no-constructed-context-values": "error",
      "react/no-danger": "error",
      "react/void-dom-elements-no-children": "warn",

      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],

      "react-hooks/exhaustive-deps": "error",

      // Tailwind
      "better-tailwindcss/no-unknown-classes": "error",
      "better-tailwindcss/enforce-canonical-classes": "error",
      "better-tailwindcss/enforce-shorthand-classes": "error",
      "better-tailwindcss/no-deprecated-classes": "error",
      "better-tailwindcss/no-conflicting-classes": "error",
      "better-tailwindcss/no-duplicate-classes": "error",
    },
  },

  eslintConfigPrettier,
);
