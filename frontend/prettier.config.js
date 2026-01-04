/** @type {import('prettier').Config} */
export default {
  // Basic formatting
  printWidth: 100,
  tabWidth: 2,
  useTabs: false,
  semi: false,
  singleQuote: true,
  quoteProps: 'as-needed',

  // JSX
  jsxSingleQuote: false,

  // Trailing commas
  trailingComma: 'es5',

  // Brackets
  bracketSpacing: true,
  bracketSameLine: false,

  // Arrow functions
  arrowParens: 'always',

  // Line endings
  endOfLine: 'lf',

  // Vue specific
  vueIndentScriptAndStyle: false,
  singleAttributePerLine: true,

  // HTML whitespace
  htmlWhitespaceSensitivity: 'css',

  // Import sorting
  plugins: ['@trivago/prettier-plugin-sort-imports'],
  importOrder: [
    '^vue',
    '^@vue',
    '^pinia',
    '^vue-router',
    '^element-plus',
    '^@element-plus',
    '^d3',
    '<THIRD_PARTY_MODULES>',
    '^@/(.*)$',
    '^[./]',
  ],
  importOrderSeparation: true,
  importOrderSortSpecifiers: true,
}
