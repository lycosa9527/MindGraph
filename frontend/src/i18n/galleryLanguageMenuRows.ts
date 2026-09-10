/**
 * Shared gallery language-menu rows (landing switcher + canvas translate picker).
 */
import { formatGalleryLanguageMenuLabel } from '@/i18n/galleryLanguageMenuLabel'
import {
  type LocaleCode,
  getLocalesForInterfaceLanguagePicker,
  getPromptLanguageOptionsForPicker,
} from '@/i18n/locales'

export interface GalleryLanguageMenuRow {
  code: LocaleCode
  label: string
}

export function getGalleryLanguageMenuRows(
  currentLanguage: string,
  allowZh: boolean
): GalleryLanguageMenuRow[] {
  const promptOpts = getPromptLanguageOptionsForPicker(allowZh)
  const enabled = getLocalesForInterfaceLanguagePicker(currentLanguage, allowZh)
  const orderIndex = (code: string) => {
    const i = promptOpts.findIndex((p) => p.code === code)
    return i === -1 ? 9999 : i
  }
  enabled.sort((a, b) => orderIndex(a.code) - orderIndex(b.code) || a.code.localeCompare(b.code))
  return enabled.map((entry) => {
    const prompt = promptOpts.find((p) => p.code === entry.code)
    const nativeLabel = prompt ? prompt.label : entry.nativeName
    return {
      code: entry.code,
      label: formatGalleryLanguageMenuLabel(entry.code, nativeLabel),
    }
  })
}
