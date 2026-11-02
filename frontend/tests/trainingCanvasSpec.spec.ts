import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  bindBuilderDiagramSession,
  builderDiagramSession,
  isBoundToStep,
  noteBuilderStepRemoved,
  noteBuilderStepsInserted,
  sameBoundStep,
} from '@/composables/training/builderDiagramBridge'
import {
  flushPublishedBuilderSpec,
  isTrainingDiagramSpec,
  preferMindMapTreeIfRicher,
  readStepDiagramSpec,
  releaseBuilderDiagramBinding,
  shouldReplaceDiagramSpec,
  writeStepDiagramSpec,
} from '@/composables/training/trainingCanvasSpec'
import { asDiagramSession, createDiagramSession } from '@/stores/diagram'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import type { TrainingCourseStep } from '@/types/training'

function stubMatchMedia(): void {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({
      matches: false,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  )
}

function canvasStep(): TrainingCourseStep {
  return { position: 0, type: 'canvas', page_key: 'canvas', diagram_type: 'mindmap' }
}

describe('trainingCanvasSpec', () => {
  beforeEach(() => {
    stubMatchMedia()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    const published = builderDiagramSession.value
    bindBuilderDiagramSession(null, null)
    published?.dispose()
  })

  it('keeps a position-only bind on the same unsaved slide after insert or delete', () => {
    const session = asDiagramSession(
      createDiagramSession({
        mode: 'edit',
        vueFlowId: 'test-course-shift',
        emitDiagramEvents: false,
      })
    )
    const step = { ...canvasStep(), position: 1 }
    bindBuilderDiagramSession(session, step)
    noteBuilderStepsInserted(0, 1)
    expect(isBoundToStep({ position: 2 })).toBe(true)
    noteBuilderStepRemoved(0)
    expect(isBoundToStep({ position: 1 })).toBe(true)
    noteBuilderStepRemoved(1)
    expect(builderDiagramSession.value).toBeNull()
    session.dispose()
  })

  it('treats a saved id as the same slide as its position', () => {
    const draft = canvasStep()
    const saved = { ...draft, id: 'saved-slide' }
    expect(sameBoundStep(draft, saved)).toBe(true)
    expect(sameBoundStep(saved, { ...canvasStep(), id: 'other', position: 1 })).toBe(false)
  })

  it('reads a stored spec and ignores non-objects', () => {
    const step = canvasStep()
    step.diagram_spec = { type: 'mindmap', topic: 'AI' }
    expect(isTrainingDiagramSpec(step.diagram_spec)).toBe(true)
    expect(readStepDiagramSpec(step)?.topic).toBe('AI')
    expect(readStepDiagramSpec({ ...step, diagram_spec: null })).toBeNull()
  })

  it('writes the live session onto the course step', () => {
    const step = canvasStep()
    const session = asDiagramSession(
      createDiagramSession({
        mode: 'edit',
        vueFlowId: 'test-course-spec',
        emitDiagramEvents: false,
      })
    )
    expect(session.loadDefaultTemplate('mindmap')).toBe(true)
    expect(writeStepDiagramSpec(step, session)).toBe(true)
    expect(step.diagram_spec?.type).toBe('mindmap')
    expect(step.diagram_spec?.nodes).not.toBe(session.data?.nodes)
    expect(writeStepDiagramSpec(step, session)).toBe(false)
  })

  it('flushes the published builder session onto the bound slide only', () => {
    const builder = useTrainingBuilderStore()
    const bound = { ...canvasStep(), id: 'slide-a', position: 0 }
    const selected = { ...canvasStep(), id: 'slide-b', position: 1 }
    builder.steps = [bound, selected]
    builder.selected = 1
    const session = asDiagramSession(
      createDiagramSession({
        mode: 'edit',
        vueFlowId: 'test-course-flush',
        emitDiagramEvents: false,
      })
    )
    expect(session.loadDefaultTemplate('mindmap')).toBe(true)
    bindBuilderDiagramSession(session, bound)
    flushPublishedBuilderSpec()
    expect(isTrainingDiagramSpec(bound.diagram_spec)).toBe(true)
    expect(selected.diagram_spec).toBeUndefined()
  })

  it('does not flush onto the selected slide when no session is bound', () => {
    const builder = useTrainingBuilderStore()
    const step = { ...canvasStep(), id: 'slide-open' }
    builder.steps = [step]
    builder.selected = 0
    const session = asDiagramSession(
      createDiagramSession({
        mode: 'edit',
        vueFlowId: 'test-course-unbound',
        emitDiagramEvents: false,
      })
    )
    expect(session.loadDefaultTemplate('mindmap')).toBe(true)
    builderDiagramSession.value = session
    flushPublishedBuilderSpec()
    expect(step.diagram_spec).toBeUndefined()
  })

  it('does not drop a newer bound session when an old canvas unmounts', () => {
    const builder = useTrainingBuilderStore()
    const first = { ...canvasStep(), id: 'slide-old', position: 0 }
    const second = { ...canvasStep(), id: 'slide-new', position: 1 }
    builder.steps = [first, second]
    const oldSession = asDiagramSession(
      createDiagramSession({
        mode: 'edit',
        vueFlowId: 'test-course-old-session',
        emitDiagramEvents: false,
      })
    )
    const nextSession = asDiagramSession(
      createDiagramSession({
        mode: 'edit',
        vueFlowId: 'test-course-new-session',
        emitDiagramEvents: false,
      })
    )
    bindBuilderDiagramSession(nextSession, second)
    releaseBuilderDiagramBinding(oldSession, first)
    expect(builderDiagramSession.value).toBe(nextSession)
    oldSession.dispose()
  })

  it('still flushes after the bound slide receives a saved id', () => {
    const builder = useTrainingBuilderStore()
    const step = canvasStep()
    builder.steps = [step]
    const session = asDiagramSession(
      createDiagramSession({
        mode: 'edit',
        vueFlowId: 'test-course-saved-id',
        emitDiagramEvents: false,
      })
    )
    expect(session.loadDefaultTemplate('mindmap')).toBe(true)
    bindBuilderDiagramSession(session, step)
    step.id = 'saved-slide'
    flushPublishedBuilderSpec()
    expect(isTrainingDiagramSpec(step.diagram_spec)).toBe(true)
  })

  it('does not replace a saved tree with a topic-only snapshot', () => {
    const tree = {
      type: 'mindmap',
      topic: 'AI',
      children: [{ text: '分支', children: [] }],
      nodes: [
        { id: 'topic', text: 'AI' },
        { id: 'a', text: '分支' },
      ],
      connections: [{ source: 'topic', target: 'a' }],
    }
    const topicOnly = {
      type: 'mindmap',
      nodes: [{ id: 'topic', text: '中心主题' }],
      connections: [],
    }
    expect(shouldReplaceDiagramSpec(tree, topicOnly)).toBe(false)
    expect(
      preferMindMapTreeIfRicher({ ...topicOnly, children: tree.children }).nodes
    ).toBeUndefined()
  })
})
