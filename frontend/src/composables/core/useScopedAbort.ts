/**
 * AbortController tied to the current Vue scope (unmount / route leave).
 */
import { onScopeDispose, shallowRef } from 'vue'

export function useScopedAbort() {
  const controller = shallowRef<AbortController | null>(null)

  function beginRequest(): AbortSignal {
    controller.value?.abort()
    const next = new AbortController()
    controller.value = next
    return next.signal
  }

  function abort(): void {
    controller.value?.abort()
    controller.value = null
  }

  onScopeDispose(() => {
    abort()
  })

  return { beginRequest, abort }
}
