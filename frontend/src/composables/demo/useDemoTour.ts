/**
 * Runs one diagram tour on the preview session's private view bus.
 * The deck advances only when this tour reports that the last hold finished.
 */
import { type Ref, onBeforeUnmount, ref, watch } from 'vue'

import {
  DEMO_CAMERA_MS,
  DEMO_MISSING_SPEC_MS,
  DEMO_TOUR_PADDING,
  DEMO_VIEWPORT_LANE,
  type DemoTourBeat,
  buildDemoTour,
  demoFocusMaxZoom,
} from '@/composables/demo/demoTour'
import type { DiagramViewBus } from '@/stores/diagram/diagramViewBus'
import type { Connection, DiagramNode } from '@/types'
import { cancelViewportTransition } from '@/utils/viewportTransition'

export interface DemoTourSession {
  data: { nodes?: DiagramNode[]; connections?: Connection[] } | null
  nodeDimensions: Record<string, { width: number; height: number }>
  viewBus: DiagramViewBus
}

type HoldPhase = 'idle' | 'travel' | 'hold'

const MEASURE_RETRY_MS = 120
const MEASURE_ATTEMPTS = 25

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function useDemoTour(options: {
  active: Ref<boolean>
  paused: Ref<boolean>
  diagramType: Ref<string>
  ready: Ref<boolean>
  failed: Ref<boolean>
  getSession: () => DemoTourSession | null
  canvasHeight: () => number
  onDone: () => void
}) {
  const focusNodeId = ref<string | null>(null)
  const brightNodeIds = ref<Set<string> | null>(null)

  let generation = 0
  let holdTimer = 0
  const pendingWaits: { id: number; resolve: (open: boolean) => void }[] = []
  let holdEndsAt = 0
  let holdRemaining = 0
  let beatIndex = 0
  let beats: DemoTourBeat[] = []
  let holdPhase: HoldPhase = 'idle'

  function clearHold(): void {
    window.clearTimeout(holdTimer)
    holdTimer = 0
  }

  function clearWaits(): void {
    for (const pending of pendingWaits) {
      window.clearTimeout(pending.id)
      pending.resolve(false)
    }
    pendingWaits.length = 0
  }

  function stop(emitDone: boolean): void {
    const wasMoving = holdPhase !== 'idle'
    generation += 1
    clearHold()
    clearWaits()
    if (wasMoving) cancelViewportTransition(DEMO_VIEWPORT_LANE)
    holdPhase = 'idle'
    focusNodeId.value = null
    brightNodeIds.value = null
    beats = []
    if (emitDone) options.onDone()
  }

  function wait(ms: number, gen: number): Promise<boolean> {
    return new Promise((resolve) => {
      const pending = {
        id: 0,
        resolve: (open: boolean): void => {
          resolve(open && gen === generation)
        },
      }
      pending.id = window.setTimeout(() => {
        const index = pendingWaits.indexOf(pending)
        if (index >= 0) pendingWaits.splice(index, 1)
        pending.resolve(true)
      }, ms)
      pendingWaits.push(pending)
    })
  }

  async function waitUntilMeasured(gen: number): Promise<boolean> {
    for (let attempt = 0; attempt < MEASURE_ATTEMPTS; attempt += 1) {
      if (gen !== generation) return false
      const session = options.getSession()
      const nodes = session?.data?.nodes ?? []
      const dims = session?.nodeDimensions ?? {}
      const measured = nodes.filter((node) => (dims[node.id]?.width ?? 0) > 0).length
      if (nodes.length > 0 && measured >= Math.ceil(nodes.length * 0.6)) return true
      const still = await wait(MEASURE_RETRY_MS, gen)
      if (!still) return false
    }
    return gen === generation && (options.getSession()?.data?.nodes?.length ?? 0) > 0
  }

  async function waitWhilePaused(gen: number): Promise<boolean> {
    while (options.paused.value) {
      const still = await wait(80, gen)
      if (!still) return false
    }
    return gen === generation
  }

  function applyBeat(index: number, animate: boolean): void {
    const beat = beats[index]
    const session = options.getSession()
    if (!beat || !session || beat.nodeIds.length === 0) return
    focusNodeId.value = beat.focusNodeId
    if (beat.kind === 'overview') {
      brightNodeIds.value = null
    } else {
      brightNodeIds.value = new Set(beat.nodeIds)
    }
    session.viewBus.emit('view:fit_to_nodes_requested', {
      nodeIds: beat.nodeIds,
      animate,
      duration: DEMO_CAMERA_MS,
      maxZoom: demoFocusMaxZoom(options.canvasHeight()),
      padding: DEMO_TOUR_PADDING,
      transitionLane: DEMO_VIEWPORT_LANE,
      userInitiated: true,
    })
  }

  function finishHold(gen: number): void {
    if (gen !== generation || options.paused.value) return
    if (beats.length === 0) {
      stop(true)
      return
    }
    beatIndex += 1
    if (beatIndex >= beats.length) {
      stop(true)
      return
    }
    beginBeat(gen)
  }

  function scheduleHold(ms: number, gen: number): void {
    holdPhase = 'hold'
    holdRemaining = ms
    holdEndsAt = Date.now() + ms
    clearHold()
    holdTimer = window.setTimeout(() => finishHold(gen), ms)
  }

  function beginBeat(gen: number): void {
    if (gen !== generation || options.paused.value) return
    const beat = beats[beatIndex]
    if (!beat) {
      stop(true)
      return
    }
    const reduce = prefersReducedMotion()
    applyBeat(beatIndex, !reduce)
    if (reduce) {
      scheduleHold(beat.ms, gen)
      return
    }
    holdPhase = 'travel'
    holdRemaining = beat.ms
    clearHold()
    holdTimer = window.setTimeout(() => {
      if (gen !== generation || options.paused.value) return
      scheduleHold(beat.ms, gen)
    }, DEMO_CAMERA_MS)
  }

  async function start(): Promise<void> {
    const gen = ++generation
    clearHold()
    clearWaits()
    cancelViewportTransition(DEMO_VIEWPORT_LANE)
    holdPhase = 'idle'
    focusNodeId.value = null
    brightNodeIds.value = null
    beats = []
    beatIndex = 0

    if (!options.ready.value) {
      scheduleHold(DEMO_MISSING_SPEC_MS, gen)
      return
    }

    const measured = await waitUntilMeasured(gen)
    if (!measured) return
    const canStart = await waitWhilePaused(gen)
    if (!canStart) return

    const session = options.getSession()
    const nodes = session?.data?.nodes ?? []
    const connections = session?.data?.connections ?? []
    beats = buildDemoTour(options.diagramType.value, nodes, connections)
    if (prefersReducedMotion()) beats = beats.slice(0, 1)
    beatIndex = 0
    if (beats.length === 0) {
      scheduleHold(DEMO_MISSING_SPEC_MS, gen)
      return
    }
    beginBeat(gen)
  }

  watch(options.paused, (isPaused) => {
    if (holdPhase === 'idle') return
    if (isPaused) {
      clearHold()
      if (holdPhase === 'hold') holdRemaining = Math.max(0, holdEndsAt - Date.now())
      if (holdPhase === 'travel') cancelViewportTransition(DEMO_VIEWPORT_LANE)
      return
    }
    const gen = generation
    if (holdPhase === 'travel') {
      beginBeat(gen)
      return
    }
    if (holdPhase === 'hold') scheduleHold(holdRemaining, gen)
  })

  watch(
    [options.active, options.ready, options.failed, options.diagramType],
    () => {
      if (!options.active.value) {
        stop(false)
        return
      }
      if (!options.ready.value && !options.failed.value) {
        stop(false)
        return
      }
      void start()
    },
    { immediate: true }
  )

  onBeforeUnmount(() => {
    stop(false)
  })

  return { focusNodeId, brightNodeIds }
}
