import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
import jsxA11y from 'eslint-plugin-jsx-a11y';

// DESIGN.md rule 1: semantic tokens only — no raw Tailwind palette classes in class strings.
const RAW_PALETTE = String.raw`/\b(bg|text|border|ring|from|to|via|fill|stroke)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/`;
const PALETTE_MESSAGE = 'Use a semantic colour token from tailwind.config.js (see DESIGN.md), not a raw palette class.';

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // The jsx-a11y plugin is registered by eslint-config-next; enable its full recommended set.
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      'no-restricted-syntax': [
        'error',
        { selector: `Literal[value=${RAW_PALETTE}]`, message: PALETTE_MESSAGE },
        { selector: `TemplateElement[value.raw=${RAW_PALETTE}]`, message: PALETTE_MESSAGE },
      ],
    },
  },
  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts']),
]);
