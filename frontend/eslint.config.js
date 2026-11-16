import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/dist/**", "**/node_modules/**", "playwright-report/**", "test-results/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Batas antarbagian: aplikasi hanya memakai API publik paket avatar & api-client.
      "no-restricted-imports": ["error", {
        patterns: [
          { group: ["@zoi/avatar/*", "@zoi/api-client/*"], message: "Impor hanya dari indeks paket (@zoi/avatar)." },
          { group: ["**/packages/**"], message: "Gunakan nama paket (@zoi/...), bukan path relatif ke packages/." },
        ],
      }],
    },
  },
);
