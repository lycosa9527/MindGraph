/**
 * Materialize `locales/messages/<code>/` from English namespaces + root re-export.
 * Creates a new English-fill locale dir only when it does not exist.
 * Never deletes or overwrites an existing `messages/<code>/` tree (that is how
 * 5.180.80 wiped picker translations). Add missing keys with sync-messages; fill
 * English leftovers from zh with `i18n:gap-fill`.
 *
 * Does not modify `src/i18n/index.ts` — locale loading is lazy via `import.meta.glob`.
 *
 * Run: node scripts/materialize-locale-bundles-from-en.ts
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { SUPPORTED_UI_LOCALES } from '../src/i18n/supportedUiLocales.ts'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '../src/locales/messages')
const EN = join(ROOT, 'en')

const SKIP_COPY = new Set(['en', 'zh', 'zh-tw'])

const NS_FILES = [
  'admin.ts',
  'auth.ts',
  'canvas.ts',
  'showcase.ts',
  'common.ts',
  'community.ts',
  'knowledge.ts',
  'mindmate.ts',
  'maite.ts',
  'notification.ts',
  'sidebar.ts',
  'thinkingCoins.ts',
  'workshop.ts',
  'training.ts',
] as const

function patchNamespaceHeader(content: string, code: string): string {
  return content.replace(
    /^\/\*\* English UI â€?(.+) \*\//,
    `/** ${code} UI â€?$1 (English copy; translate values as needed) */`
  )
}

function materializeLocale(code: string): void {
  const dest = join(ROOT, code)
  if (existsSync(dest)) {
    console.warn(
      `skip existing ${code} (will not overwrite). Add missing keys only; do not rematerialize from English.`
    )
    return
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
 * ${code} UI messages â€?re-export merged bundles.
 */
export { default } from './${code}/index.ts'
`,
    'utf8'
  )
}

function main(): void {
  for (const { code } of SUPPORTED_UI_LOCALES) {
    if (SKIP_COPY.has(code)) continue
    materializeLocale(code)
    console.log('materialized', code)
  }
  console.log('done (locale loading is import.meta.glob in src/i18n/index.ts)')
}

main()
