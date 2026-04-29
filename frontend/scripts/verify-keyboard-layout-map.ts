/**
 * Smoke-test UI locale → simple-keyboard preset mapping (run: npx tsx scripts/verify-keyboard-layout-map.ts).
 */
import {
  ALL_LAYOUT_PRESET_NAMES,
  PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE,
  getLayoutPresetKeyForUiLocale,
  loadLayoutForPreset,
} from '../src/i18n/keyboardLayoutForUiLocale'
import {
  INTERFACE_LANGUAGE_PICKER_CODES,
  INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT,
} from '../src/i18n/locales'
import type { LocaleCode } from '../src/i18n/supportedUiLocales'

async function main(): Promise<void> {
  if (INTERFACE_LANGUAGE_PICKER_CODES.length !== INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT) {
    throw new Error(
      'INTERFACE_LANGUAGE_PICKER_CODES length !== INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT'
    )
  }
  const pickerMapKeys = Object.keys(PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE)
  if (pickerMapKeys.length !== INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT) {
    throw new Error(
      `PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE has ${pickerMapKeys.length} keys, expected ${INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT}`
    )
  }
  for (const code of INTERFACE_LANGUAGE_PICKER_CODES) {
    if (PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE[code] === undefined) {
      throw new Error(
        `Picker locale ${code} missing from PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE`
      )
    }
  }

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

  for (const preset of ALL_LAYOUT_PRESET_NAMES) {
    const bundle = await loadLayoutForPreset(preset)
    if (!bundle.layout?.default?.length) {
      throw new Error(`Empty layout for preset ${preset}`)
    }
  }

  console.log('keyboard layout map ok', {
    pickerLocales: INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT,
    uniquePresetsUsedByPicker: presets.size,
    presetsBundledInSimpleKeyboardLayouts: ALL_LAYOUT_PRESET_NAMES.length,
  })
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
