/**
 * Generate src/i18n/lazyLocaleLoaders.ts — dynamic imports for non-eager locales.
 * Locales whose message values are identical to `en` share `import('@/locales/messages/en')`
 * so Vite emits one chunk instead of dozens of duplicates.
 *
 * Run: npx tsx scripts/generate-lazy-locale-loaders.js
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, '..')
const MESSAGE_ROOT = join(root, 'src/locales/messages')

function extractCodes(filePath) {
  const text = readFileSync(filePath, 'utf8')
  const codes = []
  for (const match of text.matchAll(/code: '([^']+)'/g)) {
    codes.push(match[1])
  }
  return codes
}

/** Locales with real translations — always keep a dedicated chunk. */
const ALWAYS_DEDICATED_LOCALES = new Set(['zh', 'zh-tw', 'az', 'th', 'fr', 'af'])

/**
 * English-copy locales: same strings as `en` (materialized bundles). Allow up to
 * {@link MAX_EN_COPY_VALUE_DRIFT} value mismatches from stale materialized copies.
 */
const MAX_EN_COPY_VALUE_DRIFT = 6

function classifyLocaleBundle(code, loc, enMerged) {
  if (ALWAYS_DEDICATED_LOCALES.has(code)) {
    return 'dedicated'
  }
  const keys = Object.keys(loc)
  if (keys.length === 0) {
    return 'dedicated'
  }
  let missingInEn = 0
  let valueDrift = 0
  for (const k of keys) {
    if (!(k in enMerged)) {
      missingInEn++
      continue
    }
    if (loc[k] !== enMerged[k]) {
      valueDrift++
    }
  }
  if (missingInEn > 0 || valueDrift > MAX_EN_COPY_VALUE_DRIFT) {
    return 'dedicated'
  }
  return 'en-copy'
}

async function loadMerged(code) {
  const href = pathToFileURL(join(MESSAGE_ROOT, `${code}.ts`)).href
  const mod = await import(href)
  return mod.default
}

async function main() {
  const codes = [
    ...extractCodes(join(root, 'src/i18n/supportedUiLocales.ts')),
    ...extractCodes(join(root, 'src/i18n/supportedUiLocalesExtra.ts')),
  ]
  const lazy = [...new Set(codes)].filter((c) => c !== 'en').sort()

  const enMerged = await loadMerged('en')
  const enCopyCodes = []
  const dedicatedCodes = []

  for (const code of lazy) {
    try {
      const loc = await loadMerged(code)
      if (classifyLocaleBundle(code, loc, enMerged) === 'en-copy') {
        enCopyCodes.push(code)
      } else {
        dedicatedCodes.push(code)
      }
    } catch (err) {
      console.warn(`skip ${code}: ${err instanceof Error ? err.message : err}`)
    }
  }

  const dedicatedLines = dedicatedCodes
    .sort()
    .map((code) => `  '${code}': () => import('@/locales/messages/${code}'),`)

  const output = `/**
 * Per-locale dynamic imports (generated — run: npx tsx scripts/generate-lazy-locale-loaders.js).
 * \`en\` is eager in i18n/index.ts. LOCALE_EN_COPY_CODES reuse those messages (no import here).
 */
import type { LocaleCode } from './locales'

type LocaleModule = { default: Record<string, string> }

/** UI locale codes that reuse eager English strings (see loadLocaleMessages in i18n/index.ts). */
export const LOCALE_EN_COPY_CODES = ${JSON.stringify(enCopyCodes, null, 2)} as const satisfies readonly LocaleCode[]

const enCopySet = new Set<string>(LOCALE_EN_COPY_CODES)

export function isLocaleEnCopy(code: LocaleCode): boolean {
  return enCopySet.has(code)
}

export const lazyLocaleLoaders: Partial<Record<LocaleCode, () => Promise<LocaleModule>>> = {
${dedicatedLines.join('\n')}
}
`

  writeFileSync(join(root, 'src/i18n/lazyLocaleLoaders.ts'), output, 'utf8')
  writeFileSync(
    join(root, 'src/i18n/localeEnCopyCodes.json'),
    `${JSON.stringify({ enCopyCodes, dedicatedCodes }, null, 2)}\n`,
    'utf8'
  )
  console.log(
    `wrote lazyLocaleLoaders.ts: ${lazy.length} loaders (${enCopyCodes.length} en-copy, ${dedicatedCodes.length} dedicated)`
  )
  console.log('en-copy:', enCopyCodes.join(', '))
  console.log('dedicated:', dedicatedCodes.join(', '))
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
