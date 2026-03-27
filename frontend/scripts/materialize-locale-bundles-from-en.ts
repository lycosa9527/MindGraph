/**
 * Materialize `locales/messages/<code>/` from English namespaces + root re-export.
 * Skips: en, zh, zh-tw, az, th, fr, af (existing dedicated bundles).
 * Regenerates `src/i18n/index.ts` with one import per locale.
 * Run: npx tsx scripts/materialize-locale-bundles-from-en.ts
 */
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { SUPPORTED_UI_LOCALES } from '../src/i18n/supportedUiLocales'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '../src/locales/messages')
const EN = join(ROOT, 'en')

/** Locales that already have non–English-copy bundles; do not overwrite. */
const SKIP_COPY = new Set(['en', 'zh', 'zh-tw', 'az', 'th', 'fr', 'af'])

const NS_FILES = [
  'admin.ts',
  'auth.ts',
  'canvas.ts',
  'common.ts',
  'community.ts',
  'knowledge.ts',
  'mindmate.ts',
  'notification.ts',
  'sidebar.ts',
  'workshop.ts',
] as const

function patchNamespaceHeader(content: string, code: string): string {
  return content.replace(
    /^\/\*\* English UI — (.+) \*\//,
    `/** ${code} UI — $1 (English copy; translate values as needed) */`
  )
}

function messagesImportName(code: string): string {
  const parts = code.split('-')
  const camel =
    parts[0] +
    parts
      .slice(1)
      .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
      .join('')
  return `${camel}Messages`
}

function qc(code: string): string {
  return code.includes('-') ? `'${code}'` : code
}

function materializeLocale(code: string): void {
  const dest = join(ROOT, code)
  if (existsSync(dest)) {
    rmSync(dest, { recursive: true })
  }
  mkdirSync(dest, { recursive: true })
  for (const f of NS_FILES) {
    const raw = readFileSync(join(EN, f), 'utf8')
    writeFileSync(join(dest, f), patchNamespaceHeader(raw, code), 'utf8')
  }
  const indexRaw = readFileSync(join(EN, 'index.ts'), 'utf8')
  writeFileSync(
    join(dest, 'index.ts'),
    indexRaw.replace('en UI messages', `${code} UI messages`),
    'utf8'
  )
  writeFileSync(
    join(ROOT, `${code}.ts`),
    `/**
 * ${code} UI messages — re-export merged bundles.
 */
export { default } from './${code}/index'
`,
    'utf8'
  )
}

function writeI18nIndex(): void {
  const allCodes = SUPPORTED_UI_LOCALES.map((e) => e.code).sort((a, b) => a.localeCompare(b))

  const importLines: string[] = ["import { createI18n } from 'vue-i18n'", '']
  for (const code of allCodes) {
    const name = messagesImportName(code)
    importLines.push(`import ${name} from '@/locales/messages/${code}'`)
  }
  importLines.push(
    '',
    "import type { LocaleCode } from './locales'",
    "import { SUPPORTED_UI_LOCALES, htmlLangForUiCode } from './locales'",
    '',
    "export type { LocaleCode } from './locales'",
    "export { intlLocaleForUiCode } from './locales'",
    "export type { MessageSchema } from './messageSchema'",
    "export { loadElementPlusLocale } from './elementPlusLocale'",
    '',
    'const EN_FLAT = enMessages as Record<string, string>',
    '',
    '/**',
    ' * All UI locales registered for vue-i18n.',
    ' * Bundles cloned from English use the same keys until translated.',
    ' */',
    'const ALL_UI_MESSAGES: { [K in LocaleCode]: Record<string, string> } = {'
  )

  for (const code of allCodes) {
    const rhs = code === 'en' ? 'EN_FLAT' : `${messagesImportName(code)} as Record<string, string>`
    importLines.push(`  ${qc(code)}: ${rhs},`)
  }
  importLines.push(
    '}',
    '',
    "/** Typed keys for `t()` — use `import type { MessageSchema } from '@/i18n/messageSchema'`. */",
    'export const i18n = createI18n({',
    '  legacy: false,',
    '  globalInjection: true,',
    "  locale: 'zh',",
    "  fallbackLocale: 'en',",
    '  messages: ALL_UI_MESSAGES,',
    '  missingWarn: import.meta.env.DEV,',
    '  fallbackWarn: import.meta.env.DEV,',
    '})',
    '',
    'const loadedLocales = new Set<LocaleCode>(SUPPORTED_UI_LOCALES.map((e) => e.code) as LocaleCode[])',
    '',
    'export async function loadLocaleMessages(locale: LocaleCode): Promise<void> {',
    '  if (loadedLocales.has(locale)) return',
    '  const mod = await import(`../locales/messages/${locale}.ts`)',
    '  i18n.global.setLocaleMessage(locale, mod.default as Record<string, string>)',
    '  loadedLocales.add(locale)',
    '}',
    '',
    'export function setI18nLocale(locale: LocaleCode): void {',
    '  const loc = i18n.global.locale as { value: LocaleCode }',
    '  loc.value = locale',
    '}',
    '',
    '/** BCP 47–friendly value for the document element. */',
    'export function htmlLangForLocale(locale: LocaleCode): string {',
    '  return htmlLangForUiCode(locale)',
    '}',
    ''
  )

  writeFileSync(join(__dirname, '../src/i18n/index.ts'), importLines.join('\n'), 'utf8')
}

function main(): void {
  for (const { code } of SUPPORTED_UI_LOCALES) {
    if (SKIP_COPY.has(code)) continue
    materializeLocale(code)
    console.log('materialized', code)
  }
  writeI18nIndex()
  console.log('wrote src/i18n/index.ts')
}

main()
