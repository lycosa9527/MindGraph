/**
 * Materialize `locales/messages/<code>/` from English namespaces + root re-export.
 * Skips: en, zh, zh-tw, az, th, fr, af (existing dedicated bundles).
 *
 * Does not modify `src/i18n/index.ts` â€?locale loading is lazy via `import.meta.glob`
 * in that file (eager bundles: en + zh only).
 *
 * Run: node scripts/materialize-locale-bundles-from-en.ts
 */
import { execSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { SUPPORTED_UI_LOCALES } from '../src/i18n/supportedUiLocales.ts'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '../src/locales/messages')
const EN = join(ROOT, 'en')

/** Locales that already have nonâ€“English-copy bundles; do not overwrite. */
const SKIP_COPY = new Set(['en', 'zh', 'zh-tw', 'az', 'th', 'fr', 'af'])

const NS_FILES = [
  'admin.ts',
  'auth.ts',
  'canvas.ts',
  'caseSquare.ts',
  'common.ts',
  'community.ts',
  'knowledge.ts',
  'mindmate.ts',
  'notification.ts',
  'sidebar.ts',
  'thinkingCoins.ts',
  'workshop.ts',
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
  console.log('done (src/i18n/index.ts is hand-maintained for lazy loading)')
  execSync('node scripts/generate-lazy-locale-loaders.js', {
    cwd: join(__dirname, '..'),
    stdio: 'inherit',
  })
}

main()
