/**
 * SSE stream handler for node palette start/next_batch endpoints.
 */
import type { Ref } from 'vue'

import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import type { usePanelsStore } from '@/stores'
import { authFetch } from '@/utils/api'

export type PanelsStoreForStream = ReturnType<typeof usePanelsStore>

export interface NodePaletteStreamDeps {
  panelsStore: PanelsStoreForStream
  promptLanguage: Ref<string>
  abortController: Ref<AbortController | null>
  errorMessage: Ref<string | null>
  onError?: (msg: string) => void
  paletteStreamPhase: Ref<'idle' | 'requesting' | 'streaming'>
  /** Mutable nesting depth for concurrent streamBatch calls */
  streamBatchDepth: { value: number }
  /** Mutable: first node in current outermost batch */
  firstNodeReceivedInBatch: { value: boolean }
}

export interface StreamNodePaletteBatchOptions {
  append?: boolean
  sharedExistingIds?: Set<string>
  useGlobalAbort?: boolean
  onConceptMapDomains?: (domains: string[]) => void
}

export async function streamNodePaletteBatch(
  deps: NodePaletteStreamDeps,
  url: string,
  payload: Record<string, unknown>,
  options?: StreamNodePaletteBatchOptions
): Promise<number> {
  const {
    panelsStore,
    promptLanguage,
    abortController,
    errorMessage,
    onError,
    paletteStreamPhase,
    streamBatchDepth,
    firstNodeReceivedInBatch,
  } = deps

  streamBatchDepth.value += 1
  if (streamBatchDepth.value === 1) {
    firstNodeReceivedInBatch.value = false
    paletteStreamPhase.value = 'requesting'
  }

  const useGlobalAbort = options?.useGlobalAbort !== false
  const controller = new AbortController()
  if (useGlobalAbort) {
    abortController.value = controller
  }

  const decoder = new TextDecoder()
  let nodeCount = 0
  const onConceptMapDomains = options?.onConceptMapDomains
  const existingIds =
    options?.sharedExistingIds ?? new Set(panelsStore.nodePalettePanel.suggestions.map((s) => s.id))
  const doAppend = options?.append ?? false

  try {
    await ensureFontsForLanguageCode(promptLanguage.value)
    const response = await authFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    if (!response.ok) {
      const errText = await response.text()
      throw new Error(errText || `Request failed: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6)) as {
              event?: string
              domains?: string[]
              node?: {
                id: string
                text: string
                type?: string
                source_llm?: string
              }
              error_type?: string
              message?: string
            }

            if (data.event === 'concept_map_domains' && Array.isArray(data.domains)) {
              onConceptMapDomains?.(data.domains)
            } else if (data.event === 'node_generated' && data.node) {
              const node = data.node as {
                id: string
                text: string
                type?: string
                source_llm?: string
                mode?: string
                parent_id?: string
                left?: string
                right?: string
                dimension?: string
                relationship_label?: string
              }
              if (existingIds.has(node.id)) continue
              existingIds.add(node.id)
              nodeCount++

              if (!firstNodeReceivedInBatch.value) {
                firstNodeReceivedInBatch.value = true
                paletteStreamPhase.value = 'streaming'
              }

              const suggestion = {
                id: node.id,
                text: node.text,
                type: (node.type ?? 'bubble') as 'bubble' | 'branch' | 'label',
                source_llm: node.source_llm,
                mode: node.mode,
                parent_id: node.parent_id,
                left: node.left,
                right: node.right,
                dimension: node.dimension,
                relationship_label: node.relationship_label,
              }
              if (doAppend) {
                panelsStore.appendNodePaletteSuggestion(suggestion)
              } else {
                panelsStore.setNodePaletteSuggestions([
                  ...panelsStore.nodePalettePanel.suggestions,
                  suggestion,
                ])
              }
              await new Promise<void>((r) => requestAnimationFrame(() => r()))
            } else if (data.event === 'error') {
              const msg = data.message ?? 'Unknown error'
              errorMessage.value = msg
              onError?.(msg)
            } else if (data.event === 'batch_complete') {
              // Stream finished for this batch
            }
          } catch {
            // Skip malformed lines
          }
        }
      }
    } finally {
      try {
        reader.releaseLock()
      } catch {
        // Stream may already be closed; ignore
      }
    }

    return nodeCount
  } finally {
    streamBatchDepth.value -= 1
    if (streamBatchDepth.value === 0) {
      paletteStreamPhase.value = 'idle'
    }
    if (useGlobalAbort) {
      abortController.value = null
    }
  }
}
