/**
 * Canvas and course-builder save clock: just now, seconds, minutes, then a clock time.
 */
import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { formatInBeijing } from '@/utils/beijingClock'

export type EditorSavedAgo =
  | { key: 'editor.savedJustNow' }
  | { key: 'editor.savedSecondsAgo'; n: number }
  | { key: 'editor.savedMinutesAgo'; n: number }
  | { key: 'editor.autoSavedAt'; time: string }

export function editorSavedAgo(date: Date, locale: string): EditorSavedAgo {
  const diffSec = Math.floor((Date.now() - date.getTime()) / 1000)
  if (diffSec < 10) return { key: 'editor.savedJustNow' }
  if (diffSec < 60) return { key: 'editor.savedSecondsAgo', n: diffSec }
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return { key: 'editor.savedMinutesAgo', n: diffMin }
  return {
    key: 'editor.autoSavedAt',
    time: formatInBeijing(date, intlLocaleForUiCode(locale as LocaleCode), {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }),
  }
}
