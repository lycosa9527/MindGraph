/**
 * Compare flattened message keys across zh / en / az bundles (fail on drift).
 * Run from frontend/: npx tsx scripts/check-i18n-keys.ts
 */
import az from '../src/locales/messages/az'
import en from '../src/locales/messages/en'
import zh from '../src/locales/messages/zh'

function keySet(messages: Record<string, string>): Set<string> {
  return new Set(Object.keys(messages))
}

function reportMissing(label: string, missing: string[]): void {
  if (missing.length === 0) {
    return
  }
  console.error(`${label} (${missing.length}):`)
  for (const k of missing.sort()) {
    console.error(`  - ${k}`)
  }
}

function main(): void {
  const kZh = keySet(zh as Record<string, string>)
  const kEn = keySet(en as Record<string, string>)
  const kAz = keySet(az as Record<string, string>)

  const onlyEn = [...kZh].filter((k) => !kEn.has(k))
  const onlyAz = [...kZh].filter((k) => !kAz.has(k))
  const extraEn = [...kEn].filter((k) => !kZh.has(k))
  const extraAz = [...kAz].filter((k) => !kZh.has(k))

  reportMissing('Missing in en (vs zh)', onlyEn)
  reportMissing('Missing in az (vs zh)', onlyAz)
  reportMissing('Extra in en (not in zh)', extraEn)
  reportMissing('Extra in az (not in zh)', extraAz)

  const failed =
    onlyEn.length + onlyAz.length + extraEn.length + extraAz.length > 0
  if (failed) {
    process.exit(1)
  }
  console.log(`OK: i18n key parity (${kZh.size} keys × 3 locales).`)
}

main()
