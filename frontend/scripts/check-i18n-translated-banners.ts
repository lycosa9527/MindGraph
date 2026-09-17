/**
 * Require i18n file-header markers on Settings picker locales (and zh / en / zh-tw).
 * Run before adding or rewriting keys so English fill cannot wipe translations.
 *
 *   node scripts/check-i18n-translated-banners.ts
 *   node scripts/check-i18n-translated-banners.ts --write
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { INTERFACE_LANGUAGE_PICKER_CODES } from '../src/i18n/locales.ts'
import {
  applyIndexBanner,
  applyNamespaceBanner,
  fileHasExpectedBanner,
  I18N_NS_FILES,
} from './i18nFileBanner.ts'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '../src/locales/messages')

function nsPath(code: string, ns: string): string {
  return join(ROOT, code, `${ns}.ts`)
}

function indexPath(code: string): string {
  return join(ROOT, code, 'index.ts')
}

function main(): void {
  const write = process.argv.includes('--write')
  const missing: string[] = []
  let stamped = 0

  for (const code of INTERFACE_LANGUAGE_PICKER_CODES) {
    for (const ns of I18N_NS_FILES) {
      const abs = nsPath(code, ns)
      if (!existsSync(abs)) {
        missing.push(`${code}/${ns}.ts (missing file)`)
        continue
      }
      const raw = readFileSync(abs, 'utf8')
      if (fileHasExpectedBanner(raw, code)) {
        continue
      }
      if (write) {
        writeFileSync(abs, applyNamespaceBanner(raw, code, ns), 'utf8')
        stamped += 1
        continue
      }
      missing.push(`${code}/${ns}.ts`)
    }
    const idx = indexPath(code)
    if (!existsSync(idx)) {
      missing.push(`${code}/index.ts (missing file)`)
      continue
    }
    const rawIdx = readFileSync(idx, 'utf8')
    if (fileHasExpectedBanner(rawIdx, code)) {
      continue
    }
    if (write) {
      writeFileSync(idx, applyIndexBanner(rawIdx, code), 'utf8')
      stamped += 1
      continue
    }
    missing.push(`${code}/index.ts`)
  }

  if (write) {
    console.log(`stamped ${stamped} picker i18n file headers`)
  }

  if (missing.length > 0) {
    console.error(
      'i18n file headers missing the overwrite-guard comment. ' +
        'Read the header before changing keys. Run:\n' +
        '  node scripts/check-i18n-translated-banners.ts --write\n\n' +
        missing.map((row) => `  - ${row}`).join('\n')
    )
    process.exit(1)
  }

  console.log(
    `OK: picker locale file headers (${INTERFACE_LANGUAGE_PICKER_CODES.length} locales × ` +
      `${I18N_NS_FILES.length} namespaces + index) include overwrite-guard comments`
  )
}

main()
