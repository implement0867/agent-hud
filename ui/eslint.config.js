import js from "@eslint/js";
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
        project: [
          "./tsconfig.app.json",
          "./tsconfig.node.json",
          "./tsconfig.test.json",
        ],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-refresh": reactRefresh,
    },
    settings: {
      react: { version: "detect" },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
    rules: {
      // TypeScript
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/consistent-type-definitions": ["error", "type"],
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/ban-ts-comment": [
        "error",
        {
          "ts-expect-error": "allow-with-description",
          "ts-ignore": true,
          "ts-nocheck": true,
          "ts-check": false,
        },
      ],
      "no-unused-expressions": "off",
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
      "react/jsx-key": "error",
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

      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "error",
    },
  },

  {
    files: ["**/*.js"],
    extends: [tseslint.configs.disableTypeChecked],
  },

  eslintConfigPrettier,
);
