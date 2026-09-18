/**
 * Host Google gap-fill CLI.
 *
 * Windows host only (VPN / system proxy). WSL cannot reach Google.
 *
 *   node i18n-google/cli.ts --dry-run
 *   node i18n-google/cli.ts --locale=ta
 *   node i18n-google/cli.ts --locale=ar,pt,ru,fa
 *   node i18n-google/cli.ts --all-enabled
 */
import {
  htmlLangForUiCode,
  INTERFACE_LANGUAGE_PICKER_CODES,
  UI_LOCALE_CODES,
  type LocaleCode,
} from '../src/i18n/locales.ts'
import { fillNamespace } from './gapFill.ts'
import { googleToForLocale } from './googleBatch.ts'
import { NS_FILES, type Namespace } from './namespaces.ts'
import { setupFetchProxy } from './proxy.ts'

const SKIP_LOCALES = new Set<string>(['en', 'zh', 'zh-tw'])
const TIER_A = ['ar', 'pt', 'ru', 'fa'] as const

function pickerLocaleOrder(): LocaleCode[] {
  const rest = INTERFACE_LANGUAGE_PICKER_CODES.filter(
    (code) => !SKIP_LOCALES.has(code) && !TIER_A.includes(code as (typeof TIER_A)[number])
  )
  return [...TIER_A, ...rest] as LocaleCode[]
}

function allEnabledLocaleOrder(): LocaleCode[] {
  const picker = new Set<string>(pickerLocaleOrder())
  const rest = UI_LOCALE_CODES.filter((code) => !SKIP_LOCALES.has(code) && !picker.has(code))
  return [...pickerLocaleOrder(), ...rest]
}

export function parseArgs(argv: readonly string[] = process.argv): {
  locales: LocaleCode[]
  dryRun: boolean
  onlyNs: Set<Namespace> | null
} {
  const dryRun = argv.includes('--dry-run')
  const allEnabled = argv.includes('--all-enabled')
  const locArg = argv.find((a) => a.startsWith('--locale='))
  const onlyArg = argv.find((a) => a.startsWith('--only-ns='))
  let locales = allEnabled ? allEnabledLocaleOrder() : pickerLocaleOrder()
  if (locArg !== undefined) {
    locales = locArg
      .slice('--locale='.length)
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && !SKIP_LOCALES.has(s)) as LocaleCode[]
  }
  let onlyNs: Set<Namespace> | null = null
  if (onlyArg !== undefined) {
    onlyNs = new Set(
      onlyArg
        .slice('--only-ns='.length)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean) as Namespace[]
    )
  }
  return { locales, dryRun, onlyNs }
}

export async function runGapFill(argv: readonly string[] = process.argv): Promise<void> {
  const { locales, dryRun, onlyNs } = parseArgs(argv)
  const nsList = NS_FILES.filter((ns) => onlyNs === null || onlyNs.has(ns))
  if (locales.length === 0 || nsList.length === 0) {
    console.error('No locales or namespaces to process.')
    process.exit(1)
  }

  if (!dryRun) {
    setupFetchProxy(argv)
  }

  console.log(
    dryRun ? 'DRY RUN (no Google)' : 'Translating zh-CN → target locales',
    locales.join(','),
    '| ns:',
    nsList.join(',')
  )

  let totalGap = 0
  let totalFailed = 0
  for (const locale of locales) {
    const to = googleToForLocale(locale, htmlLangForUiCode(locale))
    let locGap = 0
    let locFailed = 0
    let sample: string | null = null
    for (const ns of nsList) {
      const row = await fillNamespace(locale, ns, to, dryRun)
      locGap += row.gap
      locFailed += row.failed
      if (sample === null && row.sample !== null) {
        sample = row.sample
      }
      if (!dryRun && row.gap > 0) {
        console.log(`  ${locale}/${ns}: filled ${row.kept}/${row.gap} failed ${row.failed}`)
      }
    }
    totalGap += locGap
    totalFailed += locFailed
    console.log(`${locale} -> ${to}: gap ${locGap} failed ${locFailed} sample=${sample ?? ''}`)
  }
  console.log(`done. gap=${totalGap} failed=${totalFailed}`)
}

const entry = (process.argv[1] ?? '').replaceAll('\\', '/')
if (entry.endsWith('/i18n-google/cli.ts') || entry.endsWith('/i18n-google/cli.js')) {
  runGapFill().catch((err: unknown) => {
    console.error(err)
    process.exit(1)
  })
}
