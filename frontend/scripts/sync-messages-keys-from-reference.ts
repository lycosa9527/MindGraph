/**
 * Align every locale × namespace (except zh) with zh slices: add missing from en; drop extras.
 * Run from frontend/: npx tsx scripts/sync-messages-keys-from-reference.ts [--dry-run]
 *
 * Tier-27 only: `--tier27-only` (matches INTERFACE_LANGUAGE_PICKER_CODES minus zh reference).
 */
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '../src/locales/messages')

const NS_ORDER = [
  'common',
  'mindmate',
  'canvas',
  'workshop',
  'admin',
  'knowledge',
  'community',
  'sidebar',
  'auth',
  'notification',
] as const

const TIER_27_EXCEPT_ZH = [
  'zh-tw',
  'en',
  'es',
  'az',
  'th',
  'fr',
  'de',
  'sq',
  'ja',
  'ko',
  'pt',
  'ru',
  'ar',
  'fa',
  'uz',
  'nl',
  'it',
  'hi',
  'id',
  'tl',
  'vi',
  'tr',
  'pl',
  'uk',
  'ms',
  'af',
] as const

function escapeSq(s: string): string {
  return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r\n/g, '\n').replace(/\n/g, '\\n')
}

function formatRecord(keysInOrder: string[], out: Record<string, string>): string {
  const lines = keysInOrder.map((k) => `  '${escapeSq(k)}': '${escapeSq(out[k])}',`)
  return `{\n${lines.join('\n')}\n}`
}

function banner(locale: string, ns: string): string {
  return `/**\n * ${locale} UI — ${ns}\n */\n`
}

async function loadMod(locale: string, ns: string): Promise<Record<string, string>> {
  const abs = join(ROOT, locale, `${ns}.ts`)
  const url = `${pathToFileURL(abs).href}?import=${Date.now()}`
  const mod = await import(url)
  const d = mod.default as Record<string, string>
  return typeof d === 'object' && d !== null ? d : {}
}

function localeDirsTier27(): string[] {
  return [...TIER_27_EXCEPT_ZH]
}

function localeDirsAll(): string[] {
  return readdirSync(ROOT)
    .filter((name) => {
      if (name === 'zh') return false
      try {
        return statSync(join(ROOT, name)).isDirectory()
      } catch {
        return false
      }
    })
    .sort()
}

async function main(): Promise<void> {
  const dry = process.argv.includes('--dry-run')
  const tier27 = process.argv.includes('--tier27-only')
  const locales = tier27 ? localeDirsTier27() : localeDirsAll()

  let changed = 0
  for (const loc of locales) {
    for (const ns of NS_ORDER) {
      const zhMod = await loadMod('zh', ns)
      const enMod = await loadMod('en', ns)
      const locModPrev = await loadMod(loc, ns)
      const curPath = join(ROOT, loc, `${ns}.ts`)

      const zhKeysOrdered = Object.keys(zhMod)
      const out: Record<string, string> = {}
      for (const k of zhKeysOrdered) {
        if (locModPrev[k] !== undefined) out[k] = locModPrev[k] as string
        else out[k] = (enMod[k] ?? zhMod[k]) as string
      }

      const bodyNew = `export default ${formatRecord(zhKeysOrdered, out)}\n`
      const next = `${banner(loc, ns)}\n${bodyNew}`
      const rawPrev = readFileSync(curPath, 'utf8').trim()
      if (next.trim() !== rawPrev) {
        if (!dry) writeFileSync(curPath, next, 'utf8')
        changed += 1
      }
    }
  }

  console.log(`${dry ? 'DRY ' : ''}locales=${locales.length} files written: ${changed}`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
