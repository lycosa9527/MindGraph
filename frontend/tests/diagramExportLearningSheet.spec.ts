import { createPinia, setActivePinia } from 'pinia'

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { LEARNING_SHEET_BLANK_TEXT } from '@/stores/specLoader/utils'
import {
  LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS,
  isLearningSheetRasterCapture,
  learningSheetAnswerRowVisible,
  learningSheetIncludeAnswers,
  prepareLearningSheetAnswersForFit,
  runAsShownRasterCapture,
  runLearningSheetRasterCapture,
} from '@/utils/diagramExportLearningSheet'

describe('diagramExportLearningSheet', () => {
  beforeEach(() => {
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
    setActivePinia(createPinia())
  })

  it('detects learning sheet capture only when blanks exist', () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    expect(isLearningSheetRasterCapture(store)).toBe(false)

    store.setLearningSheetMode(true)
    const branch = store.data?.nodes.find((node) => node.type === 'branch')
    if (!branch) throw new Error('missing branch')
    store.emptyNodeForLearningSheet(branch.id)
    expect(isLearningSheetRasterCapture(store)).toBe(true)
  })

  it('treats the answer row as visible only while the canvas is showing it', () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    store.setLearningSheetMode(true)
    const branch = store.data?.nodes.find((node) => node.type === 'branch')
    if (!branch) throw new Error('missing branch')
    store.emptyNodeForLearningSheet(branch.id)

    store.setLearningSheetShowAnswers(false)
    expect(learningSheetAnswerRowVisible(store)).toBe(false)
    store.setLearningSheetShowAnswers(true)
    expect(learningSheetAnswerRowVisible(store)).toBe(true)
  })

  it('honors answerMode include flag', () => {
    expect(
      learningSheetIncludeAnswers({
        colorMode: 'color',
        layout: 'landscape',
        answerMode: 'include',
      })
    ).toBe(true)
    expect(
      learningSheetIncludeAnswers({
        colorMode: 'color',
        layout: 'landscape',
        answerMode: 'exclude',
      })
    ).toBe(false)
  })

  it('hides answers during exclude capture', async () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    store.setLearningSheetMode(true)
    const branch = store.data?.nodes.find((node) => node.type === 'branch')
    if (!branch) throw new Error('missing branch')
    store.emptyNodeForLearningSheet(branch.id)

    await runLearningSheetRasterCapture(
      store,
      { colorMode: 'color', layout: 'landscape', answerMode: 'exclude' },
      () => {
        expect(store.learningSheetShowAnswers).toBe(false)
        return 'ok'
      }
    )

    const blanked = store.data?.nodes.find((node) => node.id === branch.id)
    expect(blanked?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
  })

  it('hides knocked-out text and the answer row on the capture root', async () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('circle_map')
    store.setLearningSheetMode(true)
    const bubble = store.data?.nodes.find((node) => node.type === 'bubble')
    if (!bubble) throw new Error('missing bubble')
    store.emptyNodeForLearningSheet(bubble.id)
    const root = document.createElement('div')

    await runLearningSheetRasterCapture(
      store,
      { colorMode: 'wireframe', layout: 'landscape', answerMode: 'exclude' },
      () => {
        expect(root.classList.contains(LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS)).toBe(true)
        expect(store.learningSheetShowAnswers).toBe(false)
        return 'ok'
      },
      'below',
      root
    )

    expect(root.classList.contains(LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS)).toBe(false)
    expect(store.learningSheetShowAnswers).toBe(true)
  })

  it('clears the hide class when an exclude capture fails', async () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('circle_map')
    store.setLearningSheetMode(true)
    const bubble = store.data?.nodes.find((node) => node.type === 'bubble')
    if (!bubble) throw new Error('missing bubble')
    store.emptyNodeForLearningSheet(bubble.id)
    store.setLearningSheetShowAnswers(true)
    const root = document.createElement('div')

    await expect(
      runLearningSheetRasterCapture(
        store,
        { colorMode: 'color', layout: 'landscape', answerMode: 'exclude' },
        () => {
          throw new Error('capture failed')
        },
        'below',
        root
      )
    ).rejects.toThrow('capture failed')

    expect(root.classList.contains(LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS)).toBe(false)
    expect(store.learningSheetShowAnswers).toBe(true)
  })

  it('leaves the capture root unmarked when the sheet includes answers', async () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('circle_map')
    store.setLearningSheetMode(true)
    const bubble = store.data?.nodes.find((node) => node.type === 'bubble')
    if (!bubble) throw new Error('missing bubble')
    store.emptyNodeForLearningSheet(bubble.id)
    const root = document.createElement('div')

    await runLearningSheetRasterCapture(
      store,
      { colorMode: 'wireframe', layout: 'landscape', answerMode: 'include' },
      () => {
        expect(root.classList.contains(LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS)).toBe(false)
        expect(store.learningSheetShowAnswers).toBe(true)
        return 'ok'
      },
      'below',
      root
    )

    expect(root.classList.contains(LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS)).toBe(false)
  })

  it('drops the answer row and knocked-out labels from painted export styles', () => {
    const css = readFileSync(
      resolve(
        dirname(fileURLToPath(import.meta.url)),
        '../src/components/diagram/diagramCanvas.css'
      ),
      'utf8'
    )
    const style = document.createElement('style')
    style.textContent = css
    document.head.appendChild(style)
    const root = document.createElement('div')
    root.className = `vue-flow-wrapper ${LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS}`
    const overlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    overlay.setAttribute('class', 'learning-sheet-overlay')
    const label = document.createElement('div')
    label.className = 'learning-sheet-blanked'
    label.textContent = '校园有百年历史'
    root.append(overlay, label)
    document.body.append(root)

    expect(getComputedStyle(overlay).display).toBe('none')
    expect(getComputedStyle(label).visibility).toBe('hidden')

    root.classList.remove(LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS)
    expect(getComputedStyle(overlay).display).not.toBe('none')
    expect(getComputedStyle(label).visibility).toBe('visible')

    root.remove()
    style.remove()
  })

  it('as-shown capture leaves knocked-out nodes and answer visibility unchanged', async () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    store.setLearningSheetMode(true)
    const branch = store.data?.nodes.find((node) => node.type === 'branch')
    if (!branch) throw new Error('missing branch')
    store.emptyNodeForLearningSheet(branch.id)
    store.setLearningSheetShowAnswers(false)

    await runAsShownRasterCapture(() => {
      expect(store.learningSheetShowAnswers).toBe(false)
      const blanked = store.data?.nodes.find((node) => node.id === branch.id)
      expect(blanked?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
      return 'ok'
    })

    expect(store.learningSheetShowAnswers).toBe(false)
    const after = store.data?.nodes.find((node) => node.id === branch.id)
    expect(after?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
  })

  it('shows the answer row before an include-answers fit, then restores it', async () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    store.setLearningSheetMode(true)
    const branch = store.data?.nodes.find((node) => node.type === 'branch')
    if (!branch) throw new Error('missing branch')
    store.emptyNodeForLearningSheet(branch.id)
    store.setLearningSheetShowAnswers(false)

    const restore = await prepareLearningSheetAnswersForFit(store, {
      colorMode: 'color',
      layout: 'landscape',
      answerMode: 'include',
    })
    expect(store.learningSheetShowAnswers).toBe(true)
    restore()
    expect(store.learningSheetShowAnswers).toBe(false)
  })

  it('leaves answer visibility unchanged for an as-shown fit', async () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    store.setLearningSheetMode(true)
    const branch = store.data?.nodes.find((node) => node.type === 'branch')
    if (!branch) throw new Error('missing branch')
    store.emptyNodeForLearningSheet(branch.id)
    store.setLearningSheetShowAnswers(false)

    const restore = await prepareLearningSheetAnswersForFit(
      store,
      { colorMode: 'color', layout: 'landscape', answerMode: 'include' },
      true
    )
    expect(store.learningSheetShowAnswers).toBe(false)
    restore()
    expect(store.learningSheetShowAnswers).toBe(false)
  })
})
