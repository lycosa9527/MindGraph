/**
 * Collaboration guards for diagram mutations (delete vs foreign edit lock).
 */
import { eventBus } from '@/composables/core/useEventBus'

import type { DiagramContext } from './types'

export function emitCollabDeleteBlocked(): void {
  eventBus.emit('diagram:collab_delete_blocked', {})
}

export function collabForeignLockBlocksAnyId(
  ctx: DiagramContext,
  nodeIds: Iterable<string>
): boolean {
  if (!ctx.collabSessionActive.value) {
    return false
  }
  const locked = ctx.collabForeignLockedNodeIds.value
  if (locked.size === 0) {
    return false
  }
  for (const id of nodeIds) {
    if (locked.has(id)) {
      return true
    }
  }
  return false
}
