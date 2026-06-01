/**
 * Distinguish user-facing query failures from abort/cancel (tab change, unmount).
 */
import { isCancelledError } from '@tanstack/query-core'

import { isAbortError } from '@/composables/nodePalette/errors'

export function isIgnorableQueryError(err: unknown): boolean {
  if (err == null) {
    return false
  }
  if (isAbortError(err)) {
    return true
  }
  if (isCancelledError(err)) {
    return true
  }
  return false
}
