import { existsSync, readFileSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

import {
  ATTRIBUTIONS_PATH,
  ECHOES_REF,
  EXTRACTED_ECHOES_EN,
  EXTRACTED_ECHOES_MANIFEST,
  EXTRACTED_ECHOES_ZH,
  MIN_EN_QUOTES,
  MIN_EXTRACTED_ECHOES_EN,
  MIN_EXTRACTED_ECHOES_ZH,
  MIN_ZH_QUOTES,
  OUTPUT_EN,
  OUTPUT_ZH,
  VENDOR_LOCK_PATH,
  VENDOR_WISDOM_EN,
  VENDOR_WISDOM_ZH,
  WISDOM_QUOTES_REF,
} from './import-sidebar-quotes/config.ts'

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const PICKER_PATH = resolve(frontendDir, 'src/composables/sidebar/sidebarQuotePicker.ts')
const VITE_CONFIG_PATH = resolve(frontendDir, 'vite.config.ts')

interface ShippedQuoteRow {
  id?: string
  text?: string
}

function readQuotePool(path: string): ShippedQuoteRow[] {
  if (!existsSync(path)) {
    throw new Error(`Missing shipped sidebar quote asset: ${path}`)
  }
  const parsed = JSON.parse(readFileSync(path, 'utf8')) as unknown
  if (!Array.isArray(parsed)) {
    throw new Error(`Sidebar quote asset is not a JSON array: ${path}`)
  }
  return parsed as ShippedQuoteRow[]
}

function assertRequiredFile(path: string, label: string): void {
  if (!existsSync(path)) {
    throw new Error(`Missing ${label}: ${path}`)
  }
}

function assertQuotePool(path: string, minimum: number, locale: 'zh' | 'en'): number {
  const rows = readQuotePool(path)
  if (rows.length < minimum) {
    throw new Error(
      `Sidebar quote asset ${path} has ${rows.length} ${locale} rows; expected at least ${minimum}`
    )
  }
  const sample = rows[0]
  if (!sample?.id || !sample.text?.trim()) {
    throw new Error(`Sidebar quote asset ${path} has invalid row shape`)
  }
  return rows.length
}

function assertLazyLoadImplementation(): void {
  assertRequiredFile(PICKER_PATH, 'sidebar quote picker module')
  assertRequiredFile(VITE_CONFIG_PATH, 'vite config')

  const picker = readFileSync(PICKER_PATH, 'utf8')
  if (!picker.includes("@/assets/sidebar-quotes-zh.json?url")) {
    throw new Error('sidebarQuotePicker must load zh quotes via ?url dynamic import')
  }
  if (!picker.includes("@/assets/sidebar-quotes-en.json?url")) {
    throw new Error('sidebarQuotePicker must load en quotes via ?url dynamic import')
  }
  if (!picker.includes('fetch(')) {
    throw new Error('sidebarQuotePicker must fetch quote JSON at runtime')
  }
  const eagerJsonImport =
    /import\s*\(\s*['"]@\/assets\/sidebar-quotes-(?:zh|en)\.json['"]\s*\)/.test(picker)
  if (eagerJsonImport) {
    throw new Error('sidebarQuotePicker must not use eager JSON dynamic import (use ?url + fetch)')
  }
  const staticJsonImport =
    /from\s+['"]@\/assets\/sidebar-quotes-(?:zh|en)\.json['"]/.test(picker)
  if (staticJsonImport) {
    throw new Error('sidebarQuotePicker must not statically import quote JSON')
  }

  const viteConfig = readFileSync(VITE_CONFIG_PATH, 'utf8')
  if (!viteConfig.includes("globIgnores: ['**/sidebar-quotes-*']")) {
    throw new Error('vite PWA workbox must globIgnore sidebar-quotes assets')
  }
}

assertLazyLoadImplementation()

assertRequiredFile(VENDOR_WISDOM_ZH, 'wisdom-quotes vendor snapshot')
assertRequiredFile(VENDOR_WISDOM_EN, 'wisdom-quotes vendor snapshot')
assertRequiredFile(VENDOR_LOCK_PATH, 'sidebar quote vendor lock')
assertRequiredFile(ATTRIBUTIONS_PATH, 'sidebar quote attributions')
assertRequiredFile(EXTRACTED_ECHOES_ZH, 'extracted echoes zh snapshot')
assertRequiredFile(EXTRACTED_ECHOES_EN, 'extracted echoes en snapshot')
assertRequiredFile(EXTRACTED_ECHOES_MANIFEST, 'extracted echoes manifest')

const vendorLock = JSON.parse(readFileSync(VENDOR_LOCK_PATH, 'utf8')) as {
  'wisdom-quotes'?: { ref?: string }
}
if (vendorLock['wisdom-quotes']?.ref !== WISDOM_QUOTES_REF) {
  throw new Error(`VENDOR_LOCK.json wisdom-quotes ref mismatch: expected ${WISDOM_QUOTES_REF}`)
}

const echoesManifest = JSON.parse(readFileSync(EXTRACTED_ECHOES_MANIFEST, 'utf8')) as {
  source?: { ref?: string }
  zhCount?: number
  enCount?: number
}
if (echoesManifest.source?.ref !== ECHOES_REF) {
  throw new Error(`echoes-extract-manifest.json ref mismatch: expected ${ECHOES_REF}`)
}

const extractedZhCount = assertQuotePool(EXTRACTED_ECHOES_ZH, MIN_EXTRACTED_ECHOES_ZH, 'zh')
const extractedEnCount = assertQuotePool(EXTRACTED_ECHOES_EN, MIN_EXTRACTED_ECHOES_EN, 'en')
if (echoesManifest.zhCount !== extractedZhCount) {
  throw new Error(
    `echoes-extract-manifest zhCount ${echoesManifest.zhCount} != file rows ${extractedZhCount}`
  )
}
if (echoesManifest.enCount !== extractedEnCount) {
  throw new Error(
    `echoes-extract-manifest enCount ${echoesManifest.enCount} != file rows ${extractedEnCount}`
  )
}

const zhCount = assertQuotePool(OUTPUT_ZH, MIN_ZH_QUOTES, 'zh')
const enCount = assertQuotePool(OUTPUT_EN, MIN_EN_QUOTES, 'en')

console.log(`sidebar quotes shipped in repo: zh=${zhCount}, en=${enCount}`)
console.log(`echoes extract shipped: zh=${extractedZhCount}, en=${extractedEnCount}`)
