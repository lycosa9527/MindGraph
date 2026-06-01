/**
 * Typed event-bus wrapper for admin panel events (onWithOwner cleanup).
 */
import { onUnmounted } from 'vue'

import {
  eventBus,
  type EventHandler,
  type EventTypes,
} from '@/composables/core/useEventBus'

type AdminEventKey = Extract<
  keyof EventTypes,
  | 'admin:tab_activated'
  | 'admin:org_selected'
  | 'admin:refresh_requested'
  | 'admin:mutation_completed'
  | 'admin:toolbar_action'
>

export type AdminEventPayload<K extends AdminEventKey> = EventTypes[K]

export function useAdminEventBus(owner?: string) {
  const unsubscribers: (() => void)[] = []
  const composableOwner =
    owner ?? `admin_${Date.now()}_${Math.random().toString(36).slice(2)}`

  function on<K extends AdminEventKey>(
    event: K,
    handler: EventHandler<K>
  ): () => void {
    const unsubscribe = eventBus.onWithOwner(event, handler, composableOwner)
    unsubscribers.push(unsubscribe)
    return unsubscribe
  }

  function once<K extends AdminEventKey>(
    event: K,
    handler: EventHandler<K>
  ): () => void {
    const wrapped: EventHandler<K> = (data) => {
      off(event, wrapped)
      handler(data)
    }
    return on(event, wrapped)
  }

  function emit<K extends AdminEventKey>(event: K, data: EventTypes[K]): void {
    eventBus.emit(event, data)
  }

  function off<K extends AdminEventKey>(event: K, handler?: EventHandler<K>): void {
    eventBus.off(event, handler)
  }

  onUnmounted(() => {
    unsubscribers.forEach((unsub) => unsub())
    unsubscribers.length = 0
    eventBus.removeAllListenersForOwner(composableOwner)
  })

  return {
    on,
    once,
    emit,
    off,
  }
}
