/**
 * Per-tool presentation pointer sizes (laser dot, spotlight hole, highlighter/pen stroke).
 * Persisted to localStorage so sizes survive refresh and stay consistent per browser.
 */
import { ref } from 'vue'

import { defineStore } from 'pinia'

import type { PresentationToolId } from '@/types/diagram'

const STORAGE_KEY = 'mindgraph_presentation_pointer_scales'

export const PRESENTATION_POINTER_SCALE_MIN = 0.5
export const PRESENTATION_POINTER_SCALE_MAX = 2.5
export const PRESENTATION_POINTER_SCALE_STEP = 0.1

interface PersistedScales {
  laser: number
  spotlight: number
  highlighter: number
  pen: number
}

function clampScale(n: number): number {
  const rounded = Math.round(n * 10) / 10
  return Math.min(PRESENTATION_POINTER_SCALE_MAX, Math.max(PRESENTATION_POINTER_SCALE_MIN, rounded))
}

function readPersisted(): PersistedScales | null {
  if (typeof localStorage === 'undefined') {
    return null
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return null
    }
    const o = JSON.parse(raw) as Partial<PersistedScales>
    return {
      laser: typeof o.laser === 'number' ? clampScale(o.laser) : 1,
      spotlight: typeof o.spotlight === 'number' ? clampScale(o.spotlight) : 1,
      highlighter: typeof o.highlighter === 'number' ? clampScale(o.highlighter) : 1,
      pen: typeof o.pen === 'number' ? clampScale(o.pen) : 1,
    }
  } catch {
    return null
  }
}

function writePersisted(s: PersistedScales): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
}

export const usePresentationPointerStore = defineStore('presentationPointer', () => {
  const laserScale = ref(1)
  const spotlightScale = ref(1)
  const highlighterScale = ref(1)
  const penScale = ref(1)

  function hydrate(): void {
    const p = readPersisted()
    if (!p) {
      return
    }
    laserScale.value = p.laser
    spotlightScale.value = p.spotlight
    highlighterScale.value = p.highlighter
    penScale.value = p.pen
  }

  function persist(): void {
    writePersisted({
      laser: laserScale.value,
      spotlight: spotlightScale.value,
      highlighter: highlighterScale.value,
      pen: penScale.value,
    })
  }

  /**
   * Ctrl/Cmd +/-/= : adjust size for the active presentation tool only.
   */
  function adjustScaleForTool(tool: PresentationToolId, delta: number): void {
    if (tool === 'timer') {
      return
    }
    if (tool === 'laser') {
      laserScale.value = clampScale(laserScale.value + delta)
    } else if (tool === 'spotlight') {
      spotlightScale.value = clampScale(spotlightScale.value + delta)
    } else if (tool === 'highlighter') {
      highlighterScale.value = clampScale(highlighterScale.value + delta)
    } else if (tool === 'pen') {
      penScale.value = clampScale(penScale.value + delta)
    } else {
      return
    }
    persist()
  }

  hydrate()

  return {
    laserScale,
    spotlightScale,
    highlighterScale,
    penScale,
    adjustScaleForTool,
  }
})
