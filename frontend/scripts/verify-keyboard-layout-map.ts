/**
 * Smoke-test UI locale → simple-keyboard preset mapping (run: npx tsx scripts/verify-keyboard-layout-map.ts).
 */
import {
  getLayoutPresetKeyForUiLocale,
  loadLayoutForPreset,
} from '../src/i18n/keyboardLayoutForUiLocale'
import { INTERFACE_LANGUAGE_PICKER_CODES } from '../src/i18n/locales'
import type { LocaleCode } from '../src/i18n/supportedUiLocales'

async function main(): Promise<void> {
  const presets = new Set<string>()
  for (const code of INTERFACE_LANGUAGE_PICKER_CODES) {
    const preset = getLayoutPresetKeyForUiLocale(code)
    presets.add(preset)
    const bundle = await loadLayoutForPreset(preset)
    if (!bundle.layout?.default?.length) {
      throw new Error(`Empty layout for locale ${code} -> preset ${preset}`)
    }
  }
  const unknown = getLayoutPresetKeyForUiLocale('zz' as LocaleCode)
  if (unknown !== 'english') {
    throw new Error('Catch-all locale should fall back to english preset')
  }
  console.log('keyboard layout map ok', {
    pickerLocales: INTERFACE_LANGUAGE_PICKER_CODES.length,
    uniquePresets: presets.size,
  })
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
