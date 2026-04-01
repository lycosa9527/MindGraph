/**
 * Report INTERFACE_LANGUAGE_PICKER_CODES locales whose common.ts still has the materialize stub
 * ('English copy; translate values as needed'). Parses the picker list from src/i18n/locales.ts.
 *
 * Default: print warnings, exit 0 (repo may still list picker locales being translated).
 * Strict: `npx tsx scripts/check-i18n-picker-stubs.ts --strict` exits 1 if any stub remains.
 *
 * Run from frontend/: npm run i18n:check-picker-stubs
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const STUB = 'English copy; translate values as needed'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, '..')

function parsePickerCodes(localesTs: string): string[] {
  const m = localesTs.match(
    /export const INTERFACE_LANGUAGE_PICKER_CODES:\s*readonly LocaleCode\[\]\s*=\s*(\[[\s\S]*?\])\s*as const/
  )
  if (m === undefined) {
    throw new Error('Could not find INTERFACE_LANGUAGE_PICKER_CODES in locales.ts')
  }
  const arr = m[1]
  const codes: string[] = []
  for (const g of arr.matchAll(/'([a-z0-9-]+)'/g)) {
    codes.push(g[1])
  }
  if (codes.length === 0) {
    throw new Error('Parsed zero picker codes from locales.ts')
  }
  return codes
}

function main(): void {
  const localesPath = join(root, 'src', 'i18n', 'locales.ts')
  const localesText = readFileSync(localesPath, 'utf8')
  const pickerCodes = parsePickerCodes(localesText)

  const bad: string[] = []
  for (const code of pickerCodes) {
    if (code === 'en') {
      continue
    }
    const commonPath = join(root, 'src', 'locales', 'messages', code, 'common.ts')
    let body: string
    try {
      body = readFileSync(commonPath, 'utf8')
    } catch {
      bad.push(`${code} (missing ${commonPath})`)
      continue
    }
    if (body.includes(STUB)) {
      bad.push(code)
    }
  }

  const strict = process.argv.includes('--strict')

  if (bad.length > 0) {
    const msg =
      'Interface language picker includes locales whose common.ts still has the materialize stub:\n' +
      STUB +
      '\n' +
      bad.map((b) => `  - ${b}`).join('\n') +
      '\n\nTranslate or remove stub lines, or drop the locale from INTERFACE_LANGUAGE_PICKER_CODES.\n' +
      'See docs/i18n-belt-and-road-master-plan.md (§5 full translation / picker)'

    if (strict) {
      console.error(msg)
      process.exit(1)
    }
    console.warn(msg)
    console.warn(`\n(${bad.length} locale(s); exiting 0 — use --strict to fail the process)`)
    process.exit(0)
  }

  console.log(`OK: picker locales (${pickerCodes.length}) have no materialize stub in common.ts`)
}

main()
