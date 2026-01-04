/**
 * SSE Composable - Server-Sent Events for streaming
 * Migrated from sse-client.js
 */
import { onUnmounted, ref } from 'vue'

export interface SSEOptions {
  onMessage?: (data: unknown) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
  retryOnError?: boolean
  maxRetries?: number
  retryDelay?: number
}

export function useSSE() {
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const error = ref<Event | null>(null)

  let eventSource: EventSource | null = null
  let retryCount = 0

  function connect(url: string, options: SSEOptions = {}): EventSource {
    const {
      onMessage,
      onError,
      onOpen,
      onClose,
      retryOnError = true,
      maxRetries = 3,
      retryDelay = 1000,
    } = options

    if (eventSource) {
      close()
    }

    isConnecting.value = true
    error.value = null

    eventSource = new EventSource(url, { withCredentials: true })

    eventSource.onopen = () => {
      isConnected.value = true
      isConnecting.value = false
      retryCount = 0
      onOpen?.()
    }

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch {
        onMessage?.(event.data)
      }
    }

    eventSource.onerror = (e) => {
      error.value = e
      isConnected.value = false
      isConnecting.value = false
      onError?.(e)

      if (retryOnError && retryCount < maxRetries) {
        retryCount++
        setTimeout(() => {
          if (!isConnected.value) {
            connect(url, options)
          }
        }, retryDelay * retryCount)
      } else {
        close()
        onClose?.()
      }
    }

    return eventSource
  }

  function close(): void {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    isConnected.value = false
    isConnecting.value = false
  }

  function addEventListener(event: string, handler: (event: MessageEvent) => void): void {
    if (eventSource) {
      eventSource.addEventListener(event, handler)
    }
  }

  function removeEventListener(event: string, handler: (event: MessageEvent) => void): void {
    if (eventSource) {
      eventSource.removeEventListener(event, handler)
    }
  }

  onUnmounted(() => {
    close()
  })

  return {
    isConnected,
    isConnecting,
    error,
    connect,
    close,
    addEventListener,
    removeEventListener,
  }
}

/**
 * Fetch-based SSE for more control (supports POST, headers, etc.)
 */
export function useFetchSSE() {
  const isStreaming = ref(false)
  const error = ref<Error | null>(null)

  let abortController: AbortController | null = null

  async function stream(
    url: string,
    options: RequestInit & {
      onChunk?: (chunk: string) => void
      onComplete?: () => void
      onError?: (error: Error) => void
    } = {}
  ): Promise<void> {
    const { onChunk, onComplete, onError, ...fetchOptions } = options

    if (abortController) {
      abortController.abort()
    }

    abortController = new AbortController()
    isStreaming.value = true
    error.value = null

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        signal: abortController.signal,
        credentials: 'same-origin',
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          if (buffer) {
            onChunk?.(buffer)
          }
          break
        }

        buffer += decoder.decode(value, { stream: true })

        // Process SSE format
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') {
              break
            }
            onChunk?.(data)
          }
        }
      }

      onComplete?.()
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        error.value = e as Error
        onError?.(e as Error)
      }
    } finally {
      isStreaming.value = false
      abortController = null
    }
  }

  function abort(): void {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    isStreaming.value = false
  }

  onUnmounted(() => {
    abort()
  })

  return {
    isStreaming,
    error,
    stream,
    abort,
  }
}
