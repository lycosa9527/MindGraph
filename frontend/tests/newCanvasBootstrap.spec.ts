import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { LocationQuery } from 'vue-router'

import {
  clearBlankCanvasLoadDedupe,
  getDiagramDataType,
  isNewCanvasTypeQuery,
  loadBlankCanvasForType,
  normalizeDiagramTypeKey,
  resetBlankCanvasLoadDedupeForTests,
  resolveDiagramTypeFromQuery,
  shouldPriority3LoadDefaultTemplate,
} from '@/composables/canvasPage/newCanvasBootstrap'
import type { DiagramType } from '@/types'

function query(partial: Record<string, string | string[] | undefined>): LocationQuery {
  return partial as LocationQuery
}

describe('resolveDiagramTypeFromQuery / isNewCanvasTypeQuery', () => {
  it('resolves string and array type query values', () => {
    expect(resolveDiagramTypeFromQuery(query({ type: 'mindmap' }))).toBe('mindmap')
    expect(resolveDiagramTypeFromQuery(query({ type: ['circle_map'] }))).toBe('circle_map')
    expect(resolveDiagramTypeFromQuery(query({ type: 'nope' }))).toBeNull()
  })

  it('is true for ?type= without diagram id', () => {
    expect(isNewCanvasTypeQuery(query({ type: 'mindmap' }))).toBe(true)
    expect(isNewCanvasTypeQuery(query({ type: 'mind_map' }))).toBe(true)
  })

  it('is false when a library diagram id is present', () => {
    expect(isNewCanvasTypeQuery(query({ type: 'mindmap', diagramId: 'abc' }))).toBe(false)
    expect(isNewCanvasTypeQuery(query({ type: 'mindmap', diagram_id: 'abc' }))).toBe(false)
  })
})

describe('shouldPriority3LoadDefaultTemplate', () => {
  it('loads when Pinia is empty (unbound or bound)', () => {
    expect(
      shouldPriority3LoadDefaultTemplate({
        hasActiveDiagramId: false,
        hasDiagramData: false,
        selectedDiagramType: 'mindmap',
        dataDiagramType: null,
      })
    ).toBe(true)
    expect(
      shouldPriority3LoadDefaultTemplate({
        hasActiveDiagramId: true,
        hasDiagramData: false,
        selectedDiagramType: 'mindmap',
        dataDiagramType: null,
      })
    ).toBe(true)
  })

  it('keeps landing-generated in-memory spec when data.type matches chrome type', () => {
    expect(
      shouldPriority3LoadDefaultTemplate({
        hasActiveDiagramId: false,
        hasDiagramData: true,
        selectedDiagramType: 'mindmap',
        dataDiagramType: 'mindmap',
      })
    ).toBe(false)
    expect(
      shouldPriority3LoadDefaultTemplate({
        hasActiveDiagramId: false,
        hasDiagramData: true,
        selectedDiagramType: 'mindmap',
        dataDiagramType: 'mind_map',
      })
    ).toBe(false)
  })

  it('blanks wrong-type leftovers using data.type', () => {
    expect(
      shouldPriority3LoadDefaultTemplate({
        hasActiveDiagramId: false,
        hasDiagramData: true,
        selectedDiagramType: 'mindmap',
        dataDiagramType: 'circle_map',
      })
    ).toBe(true)
  })

  it('does not blank a bound library diagram that already has data', () => {
    expect(
      shouldPriority3LoadDefaultTemplate({
        hasActiveDiagramId: true,
        hasDiagramData: true,
        selectedDiagramType: 'mindmap',
        dataDiagramType: 'mindmap',
      })
    ).toBe(false)
  })
})

describe('loadBlankCanvasForType', () => {
  beforeEach(() => {
    resetBlankCanvasLoadDedupeForTests()
  })

  it('clears active diagram, syncs chrome, and loads the default template once', () => {
    const setDiagramType = vi.fn(() => true)
    const clearActiveDiagram = vi.fn()
    const loadDefaultTemplate = vi.fn(() => true)
    const setSelectedChartType = vi.fn()

    expect(
      loadBlankCanvasForType({
        diagramType: 'mindmap',
        setDiagramType,
        clearActiveDiagram,
        loadDefaultTemplate,
        setSelectedChartType,
      })
    ).toBe(true)

    expect(setSelectedChartType).toHaveBeenCalledWith('思维导图')
    expect(setDiagramType).toHaveBeenCalledWith('mindmap')
    expect(clearActiveDiagram).toHaveBeenCalledTimes(1)
    expect(loadDefaultTemplate).toHaveBeenCalledWith('mindmap')
  })

  it('dedupes same-type blank loads within the short window (switch + route watch)', () => {
    const loadDefaultTemplate = vi.fn(() => true)
    const opts = {
      diagramType: 'mindmap' as DiagramType,
      setDiagramType: () => true,
      clearActiveDiagram: () => undefined,
      loadDefaultTemplate,
      hasDiagramData: true,
    }

    expect(loadBlankCanvasForType(opts)).toBe(true)
    expect(loadBlankCanvasForType(opts)).toBe(true)
    expect(loadDefaultTemplate).toHaveBeenCalledTimes(1)
  })

  it('does not dedupe when the session has no diagram data (leave → re-enter)', () => {
    const loadDefaultTemplate = vi.fn(() => true)
    const opts = {
      diagramType: 'mindmap' as DiagramType,
      setDiagramType: () => true,
      clearActiveDiagram: () => undefined,
      loadDefaultTemplate,
      hasDiagramData: true,
    }

    expect(loadBlankCanvasForType(opts)).toBe(true)
    expect(
      loadBlankCanvasForType({
        ...opts,
        hasDiagramData: false,
      })
    ).toBe(true)
    expect(loadDefaultTemplate).toHaveBeenCalledTimes(2)
  })

  it('clearBlankCanvasLoadDedupe allows an immediate same-type reload', () => {
    const loadDefaultTemplate = vi.fn(() => true)
    const opts = {
      diagramType: 'mindmap' as DiagramType,
      setDiagramType: () => true,
      clearActiveDiagram: () => undefined,
      loadDefaultTemplate,
      hasDiagramData: true,
    }

    expect(loadBlankCanvasForType(opts)).toBe(true)
    clearBlankCanvasLoadDedupe()
    expect(loadBlankCanvasForType(opts)).toBe(true)
    expect(loadDefaultTemplate).toHaveBeenCalledTimes(2)
  })

  it('force bypasses dedupe (canvas reset)', () => {
    const loadDefaultTemplate = vi.fn(() => true)
    const opts = {
      diagramType: 'mindmap' as DiagramType,
      setDiagramType: () => true,
      clearActiveDiagram: () => undefined,
      loadDefaultTemplate,
      hasDiagramData: true,
    }

    expect(loadBlankCanvasForType(opts)).toBe(true)
    expect(loadBlankCanvasForType({ ...opts, force: true })).toBe(true)
    expect(loadDefaultTemplate).toHaveBeenCalledTimes(2)
  })

  it('loads again when the diagram type changes', () => {
    const loadDefaultTemplate = vi.fn(() => true)
    const base = {
      setDiagramType: () => true,
      clearActiveDiagram: () => undefined,
      loadDefaultTemplate,
      hasDiagramData: true,
    }

    expect(loadBlankCanvasForType({ ...base, diagramType: 'mindmap' })).toBe(true)
    expect(loadBlankCanvasForType({ ...base, diagramType: 'circle_map' })).toBe(true)
    expect(loadDefaultTemplate).toHaveBeenCalledTimes(2)
  })
})

describe('helpers', () => {
  it('normalizes mind_map to mindmap', () => {
    expect(normalizeDiagramTypeKey('mind_map')).toBe('mindmap')
    expect(normalizeDiagramTypeKey('mindmap')).toBe('mindmap')
  })

  it('reads data.type safely', () => {
    expect(getDiagramDataType({ type: 'bubble_map' })).toBe('bubble_map')
    expect(getDiagramDataType({ type: 1 })).toBeNull()
    expect(getDiagramDataType(null)).toBeNull()
  })
})
