/**
 * Optional second language for a full-diagram generate request.
 * Branch expand, node palette, and explain stay primary-only.
 */
import { useUIStore } from '@/stores/ui'

export function diagramSecondaryLanguage(): string | undefined {
  const ui = useUIStore()
  if (!ui.bilingualUiEnabled) return undefined
  const secondary = ui.presenterUiLocale.trim()
  const primary = ui.promptLanguage.trim()
  if (!secondary || secondary === primary) return undefined
  return secondary
}
