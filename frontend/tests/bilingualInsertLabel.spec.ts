import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { applyVoiceDiagramAddNodes } from '@/composables/editor/diagramVoiceMutations'
import { addKittyNodeForInlineRec } from '@/composables/kitty/kittyAddNodeWithRecommendations'
import { diagramInsertLabel, insertLabelFields } from '@/diagramBilingual/insertLabel'
import { loadLocaleMessages } from '@/i18n'
import { useDiagramStore } from '@/stores/diagram'
import { braceMapRootId } from '@/stores/diagram/braceMapParentResolve'
import { orderFlowStepNodes } from '@/stores/specLoader/flowMapSubsteps'
import { useUIStore } from '@/stores/ui'
import type { DiagramType } from '@/types'
import { treeMapColumnsOf } from '@/utils/treeMapIdentity'

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

function loadBilingual(type: DiagramType): ReturnType<typeof useDiagramStore> {
  const ui = useUIStore()
  ui.language = 'zh'
  ui.bilingualUiEnabled = true
  ui.presenterUiLocale = 'en'
  const store = useDiagramStore()
  expect(store.loadDefaultTemplate(type), type).toBe(true)
  expect(store.data?.languages).toEqual({ primary: 'zh', secondary: 'en' })
  return store
}

function label(key: string, named?: Record<string, unknown>) {
  return diagramInsertLabel(useDiagramStore().data?.languages, key, named)
}

function glossOf(text: string): string | undefined {
  return useDiagramStore().data?.nodes.find((node) => node.text === text)?.textSecondary
}

describe('bilingual inserted node labels', () => {
  beforeEach(async () => {
    stubMatchMedia()
    setActivePinia(createPinia())
    await loadLocaleMessages('zh')
    await loadLocaleMessages('en')
  })

  it('stays one line on a single-language diagram', () => {
    const ui = useUIStore()
    ui.language = 'zh'
    ui.bilingualUiEnabled = false
    const store = useDiagramStore()
    expect(store.loadDefaultTemplate('mindmap')).toBe(true)
    expect(label('canvas.toolbar.newBranch').textSecondary).toBeUndefined()
  })

  it('uses the file language pair, not the interface language', () => {
    loadBilingual('mindmap')
    useUIStore().language = 'en'
    expect(label('canvas.toolbar.newBranch')).toEqual({
      text: '新分支',
      textSecondary: 'New Branch',
    })
  })

  it('adds a mind-map branch, its default children, and a child with both lines', () => {
    const store = loadBilingual('mindmap')
    expect(
      store.addMindMapBranch(
        undefined,
        label('canvas.toolbar.newBranch'),
        label('canvas.toolbar.newChild')
      )
    ).toBe(true)
    expect(glossOf('新分支')).toBe('New Branch')
    const branchId = store.data?.nodes.find((node) => node.text === '新分支')?.id ?? ''
    expect(store.addMindMapChild(branchId, label('canvas.toolbar.newChild'))).toBe(true)
    expect(glossOf('新子项')).toBe('New Child')
  })

  it('adds flow steps and substeps with both lines', () => {
    const store = loadBilingual('flow_map')
    expect(store.addFlowMapStep(label('canvas.toolbar.newStep'))).toBe(true)
    expect(glossOf('新步骤')).toBe('New Step')
    expect(glossOf('步骤1')).toBe('Step 1')
    const step = orderFlowStepNodes(store.data?.nodes ?? [])[0]
    expect(
      store.addFlowMapSubstep(step.text ?? '', label('canvas.toolbar.newSubstep'), 0, step.id)
    ).toBe(true)
    expect(glossOf('新子步骤')).toBe('New Substep')
    expect(glossOf('子步骤1.1')).toBe('Substep 1.1')
  })

  it('adds tree categories and items with both lines', () => {
    const store = loadBilingual('tree_map')
    expect(store.addTreeMapCategory(label('canvas.toolbar.newBranch'))).toBe(true)
    expect(glossOf('新分支')).toBe('New Branch')
    const categoryId = treeMapColumnsOf(store.data?.nodes ?? [])[0]?.category.id ?? ''
    expect(store.addTreeMapChild(categoryId, label('canvas.toolbar.newChild'))).toBe(true)
    expect(glossOf('新子项')).toBe('New Child')
  })

  it('adds brace parts with both lines', () => {
    const store = loadBilingual('brace_map')
    const rootId = braceMapRootId(store.data?.nodes ?? [], store.data?.connections ?? []) ?? ''
    expect(store.addBraceMapPart(rootId, label('canvas.toolbar.newPart'))).toBe(true)
    expect(glossOf('新部分')).toBe('New Part')
  })

  it('adds double-bubble similarities and difference pairs with both lines', () => {
    const store = loadBilingual('double_bubble_map')
    expect(
      store.addDoubleBubbleMapNode(
        'similarity',
        label('canvas.toolbar.similarityWithIndex', { n: 3 })
      )
    ).toBe(true)
    expect(glossOf('相似点 3')).toBe('Similarity 3')
    expect(glossOf('相似点 1')).toBe('Similarity 1')
    expect(
      store.addDoubleBubbleMapNode(
        'leftDiff',
        label('canvas.toolbar.differenceAWithIndex', { n: 4 }),
        label('canvas.toolbar.differenceBWithIndex', { n: 4 })
      )
    ).toBe(true)
    const added = store.data?.nodes.filter((node) => node.text.endsWith('4')) ?? []
    expect(added).toHaveLength(2)
    expect(added.every((node) => Boolean(node.textSecondary?.endsWith('4')))).toBe(true)
  })

  it('adds bubble, circle, and multi-flow nodes with both lines', () => {
    const cases: Array<{ type: DiagramType; key: string; nodeType: 'bubble' | 'flow' }> = [
      { type: 'bubble_map', key: 'canvas.toolbar.newAttribute', nodeType: 'bubble' },
      { type: 'circle_map', key: 'canvas.toolbar.newAssociation', nodeType: 'bubble' },
      { type: 'multi_flow_map', key: 'canvas.toolbar.newCause', nodeType: 'flow' },
    ]
    for (const row of cases) {
      const store = loadBilingual(row.type)
      const fields = insertLabelFields(label(row.key))
      store.addNode({
        id: '',
        ...fields,
        type: row.nodeType,
        position: { x: 0, y: 0 },
        ...(row.type === 'multi_flow_map' ? { category: 'causes' } : {}),
      } as Parameters<typeof store.addNode>[0])
      expect(fields.textSecondary, row.type).toBeTruthy()
      expect(glossOf(fields.text), row.type).toBe(fields.textSecondary)
    }
  })

  it('glosses placeholders from voice, Kitty, and an empty multi-flow add', () => {
    const flow = loadBilingual('flow_map')
    expect(applyVoiceDiagramAddNodes(flow, [{ text: '蒸发' }])).toBe(1)
    expect(glossOf('蒸发')).toBeUndefined()
    expect(glossOf('子步骤3.1')).toBe('Substep 3.1')

    setActivePinia(createPinia())
    loadBilingual('flow_map')
    expect(addKittyNodeForInlineRec(useDiagramStore(), (key) => key)).toBeTruthy()
    expect(glossOf('新属性')).toBe('New Attribute')
    expect(glossOf('子步骤3.2')).toBe('Substep 3.2')

    setActivePinia(createPinia())
    const multiFlow = loadBilingual('multi_flow_map')
    multiFlow.addNode({
      id: '',
      text: '',
      type: 'flow',
      position: { x: 0, y: 0 },
      category: 'effects',
    } as Parameters<typeof multiFlow.addNode>[0])
    expect(glossOf(label('diagram.flow.newEffect').text)).toBe(
      label('diagram.flow.newEffect').textSecondary
    )
    expect(label('diagram.flow.newEffect').textSecondary).toBeTruthy()
  })
})
