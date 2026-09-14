import { eventBus } from '@/composables/core/useEventBus'
import { clearWorkshopSessionStorage } from '@/utils/workshopSessionStorage'

/**
 * Drop the live canvas-collab room and its tab-scoped restore keys.
 * Used when opening a new map, switching library diagrams, or resetting.
 */
export function leaveCanvasCollabRoom(): void {
  clearWorkshopSessionStorage()
  eventBus.emit('workshop:code-changed', { code: null, visibility: null })
}
