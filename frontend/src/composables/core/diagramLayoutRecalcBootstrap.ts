/**
 * Registers diagram layout recalc listener (deferred from main.ts to first diagram mount).
 */
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores/diagram'

let registered = false

export function registerDiagramLayoutRecalcBootstrap(): void {
  if (registered) {
    return
  }
  registered = true
  eventBus.on('diagram:layout_recalc_bump', () => {
    useDiagramStore().layoutRecalcTrigger += 1
  })
}
