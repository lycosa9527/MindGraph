/**
 * Tracks who has read the seminar and tells the server when this screen has caught up.
 */
import { type Ref, onMounted, onUnmounted, ref, watch } from 'vue'

import { collabMaxSavedId } from '@/utils/mindmateCollabGap'
import {
  type CollabReadCursor,
  applyCollabReadCursor,
  applyCollabReadCursorList,
  collabReadCursorFromFrame,
} from '@/utils/mindmateCollabRead'

export function useMindmateCollabRead(options: {
  messages: Ref<readonly { id?: number }[]>
  connected: Ref<boolean>
  isDisposed: () => boolean
  send: (body: string) => boolean
}) {
  const readCursors = ref<CollabReadCursor[]>([])
  let readQueued = false
  let lastReadSent = 0

  function resetReadCursors(): void {
    readQueued = false
    lastReadSent = 0
    readCursors.value = []
  }

  function noteReadCursorFrame(parsed: Record<string, unknown>): void {
    const cursor = collabReadCursorFromFrame(parsed)
    if (!cursor) {
      return
    }
    readCursors.value = applyCollabReadCursor(readCursors.value, cursor)
  }

  function noteReadCursorList(raw: unknown): void {
    readCursors.value = applyCollabReadCursorList(readCursors.value, raw)
  }

  function queueReadReceipt(): void {
    if (readQueued) {
      return
    }
    readQueued = true
    queueMicrotask(() => {
      readQueued = false
      if (options.isDisposed() || !options.connected.value) {
        return
      }
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        return
      }
      const latest = collabMaxSavedId(options.messages.value)
      if (latest <= lastReadSent) {
        return
      }
      if (!options.send(JSON.stringify({ type: 'read', message_id: latest }))) {
        return
      }
      lastReadSent = latest
    })
  }

  function onVisibility(): void {
    if (document.visibilityState === 'visible') {
      queueReadReceipt()
    }
  }

  watch(options.messages, () => {
    queueReadReceipt()
  })

  onMounted(() => {
    document.addEventListener('visibilitychange', onVisibility)
  })

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onVisibility)
    readQueued = false
  })

  return {
    readCursors,
    noteReadCursorFrame,
    noteReadCursorList,
    resetReadCursors,
  }
}
