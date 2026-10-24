/**
 * Deadline pickers share one pattern. A native date or datetime input
 * follows the browser locale, so Chinese Chrome shows `yyyy/mm/日 --:--`.
 */

/** Shown in the field once a deadline is chosen. */
export const DEADLINE_PICKER_FORMAT = 'YYYY/MM/DD HH:mm'

/** Empty-field hint. Fixed text, not a locale format. */
export const DEADLINE_PICKER_PLACEHOLDER = 'yyyy/mm/dd hh:mm'

export const DEADLINE_PICKER_TIME_FORMAT = 'HH:mm'

/** Value emitted by the picker. The form stores `YYYY-MM-DDTHH:mm`. */
export const DEADLINE_VALUE_FORMAT = 'YYYY-MM-DD HH:mm'

/** `YYYY-MM-DDTHH:mm` form value → picker value, or null when empty. */
export function deadlineModelToPicker(value: string): string | null {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(value.trim())
  if (!match) return null
  return `${match[1]} ${match[2]}`
}

/** Picker value → `YYYY-MM-DDTHH:mm`. Empty when cleared or incomplete. */
export function deadlinePickerToModel(value: string | null | undefined): string {
  const match = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})$/.exec((value ?? '').trim())
  if (!match) return ''
  return `${match[1]}T${match[2]}`
}
