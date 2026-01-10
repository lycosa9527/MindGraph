/**
 * useAsyncApi - VueUse-powered async API state management
 *
 * Provides simple wrappers for common API patterns using VueUse's useAsyncState.
 * Use this for simple one-shot API calls that need loading/error/ready states.
 *
 * For complex patterns (streaming, polling, parallel requests), continue using
 * manual state management with refs.
 *
 * Usage examples:
 *
 *   // Simple fetch with immediate execution
 *   const { data, isLoading, error } = useAsyncFetch('/api/data')
 *
 *   // Fetch with manual trigger
 *   const { data, isLoading, execute } = useAsyncFetch('/api/data', { immediate: false })
 *   await execute()
 *
 *   // Custom async function
 *   const { state, isLoading, execute } = useAsyncAction(
 *     async (id: string) => api.delete(id),
 *     { immediate: false }
 *   )
 */
import { useAsyncState } from '@vueuse/core'

import { authFetch } from '@/utils/api'

// ============================================================================
// Types
// ============================================================================

export interface AsyncFetchOptions<T> {
  /** Execute immediately on mount (default: true) */
  immediate?: boolean
  /** Initial value before first fetch */
  initialValue?: T
  /** Reset state on each execute (default: true) */
  resetOnExecute?: boolean
  /** Delay before execution (ms) */
  delay?: number
  /** Callback on success */
  onSuccess?: (data: T) => void
  /** Callback on error */
  onError?: (error: Error) => void
}

export interface AsyncActionOptions<T> {
  /** Execute immediately on mount (default: false for actions) */
  immediate?: boolean
  /** Initial value */
  initialValue?: T
  /** Reset state on each execute (default: true) */
  resetOnExecute?: boolean
  /** Callback on success */
  onSuccess?: (data: T) => void
  /** Callback on error */
  onError?: (error: Error) => void
}

// ============================================================================
// Composables
// ============================================================================

/**
 * Simple async fetch with automatic state management
 *
 * @param url - API endpoint URL
 * @param options - Fetch options
 * @returns Reactive state with loading, error, and data
 *
 * @example
 * const { data: user, isLoading } = useAsyncFetch<User>('/api/user')
 */
export function useAsyncFetch<T>(url: string, options: AsyncFetchOptions<T> = {}) {
  const {
    immediate = true,
    initialValue = null as T,
    resetOnExecute = true,
    delay = 0,
    onSuccess,
    onError,
  } = options

  return useAsyncState<T>(
    async () => {
      const response = await fetch(url, {
        credentials: 'same-origin',
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      onSuccess?.(data)
      return data
    },
    initialValue,
    {
      immediate,
      resetOnExecute,
      delay,
      onError: (e) => {
        console.error(`[useAsyncFetch] ${url}:`, e)
        onError?.(e instanceof Error ? e : new Error(String(e)))
      },
    }
  )
}

/**
 * Async fetch with authentication (uses authFetch)
 *
 * @param url - API endpoint URL
 * @param options - Fetch options
 * @returns Reactive state with loading, error, and data
 *
 * @example
 * const { data: diagrams, isLoading, execute: refresh } = useAuthFetch<Diagram[]>('/api/diagrams')
 */
export function useAuthFetch<T>(url: string, options: AsyncFetchOptions<T> = {}) {
  const {
    immediate = true,
    initialValue = null as T,
    resetOnExecute = true,
    delay = 0,
    onSuccess,
    onError,
  } = options

  return useAsyncState<T>(
    async () => {
      const response = await authFetch(url)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      onSuccess?.(data)
      return data
    },
    initialValue,
    {
      immediate,
      resetOnExecute,
      delay,
      onError: (e) => {
        console.error(`[useAuthFetch] ${url}:`, e)
        onError?.(e instanceof Error ? e : new Error(String(e)))
      },
    }
  )
}

/**
 * Generic async action with automatic state management
 *
 * @param asyncFn - Async function to execute
 * @param options - Action options
 * @returns Reactive state with loading, error, and result
 *
 * @example
 * const { isLoading, execute: deleteItem } = useAsyncAction(
 *   async (id: string) => {
 *     await api.delete(`/items/${id}`)
 *     return true
 *   },
 *   { onSuccess: () => notify.success('Deleted!') }
 * )
 *
 * // Later: await deleteItem(0, itemId)
 */
export function useAsyncAction<T, Args extends unknown[] = []>(
  asyncFn: (...args: Args) => Promise<T>,
  options: AsyncActionOptions<T> = {}
) {
  const {
    immediate = false, // Actions are typically not immediate
    initialValue = null as T,
    resetOnExecute = true,
    onSuccess,
    onError,
  } = options

  return useAsyncState<T, Args>(
    async (...args: Args) => {
      const result = await asyncFn(...args)
      onSuccess?.(result)
      return result
    },
    initialValue,
    {
      immediate,
      resetOnExecute,
      onError: (e) => {
        console.error('[useAsyncAction]:', e)
        onError?.(e instanceof Error ? e : new Error(String(e)))
      },
    }
  )
}

/**
 * POST request with automatic state management
 *
 * @param url - API endpoint URL
 * @param options - Action options
 * @returns Reactive state with execute function
 *
 * @example
 * const { isLoading, execute: createItem } = useAsyncPost<Item>('/api/items')
 * const newItem = await createItem(0, { name: 'New Item' })
 */
export function useAsyncPost<T, Body = Record<string, unknown>>(
  url: string,
  options: AsyncActionOptions<T> = {}
) {
  return useAsyncAction<T, [Body]>(async (body: Body) => {
    const response = await authFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    return response.json()
  }, options)
}
