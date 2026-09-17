/**
 * Fail if an enabled UI locale has no `messages/<code>.ts` (or `<code>/index.ts`) entry.
 * Run from frontend/: node scripts/check-lazy-locale-loaders.ts
 */
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { UI_LOCALE_CODES } from '../src/i18n/locales.ts'

const MESSAGE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '../src/locales/messages')

function hasMessageEntry(code: string): boolean {
  return existsSync(join(MESSAGE_ROOT, `${code}.ts`)) || existsSync(join(MESSAGE_ROOT, code, 'index.ts'))
}

function main(): void {
  const missing = UI_LOCALE_CODES.filter((code) => !hasMessageEntry(code))

  if (missing.length > 0) {
    console.error(
      'Enabled UI locales missing a message bundle entry:\n' +
        missing.map((code) => `  - ${code} (expected ${MESSAGE_ROOT}/${code}.ts)`).join('\n')
    )
    process.exit(1)
  }

  console.log(`OK: message bundles exist for ${UI_LOCALE_CODES.length} enabled UI locales.`)
}

main()
