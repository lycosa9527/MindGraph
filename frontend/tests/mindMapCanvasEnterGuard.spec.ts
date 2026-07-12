import { describe, expect, it } from 'vitest'

import {
  armInlineEditEnterGuard,
  clearMindMapPostEditSiblingAnchor,
  consumeMindMapPostEditSiblingAnchor,
  initInlineEditEnterGuard,
  isInlineDiagramEditDomActive,
  isInlineDiagramEditKeyEvent,
  isInlineDiagramEditOpen,
  isInlineEditEnterGuarded,
  setMindMapPostEditSiblingAnchor,
  shouldBlockCanvasEnterShortcut,
} from '@/composables/mindMap/mindMapCanvasEnterGuard'
import { eventBus } from '@/composables/core/useEventBus'

describe('inlineEditEnterGuard', () => {
  it('tracks open editors via node_editor events', () => {
    initInlineEditEnterGuard()
    eventBus.emit('node_editor:opening', { nodeId: 'branch-1' })
    expect(isInlineDiagramEditOpen()).toBe(true)
    eventBus.emit('node_editor:closed', { nodeId: 'branch-1' })
    expect(isInlineDiagramEditOpen()).toBe(false)
  })

  it('blocks canvas Enter while guard frames are armed', async () => {
    armInlineEditEnterGuard()
    expect(isInlineEditEnterGuarded()).toBe(true)
    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    expect(shouldBlockCanvasEnterShortcut(event)).toBe(true)
    await new Promise((resolve) => requestAnimationFrame(resolve))
    await new Promise((resolve) => requestAnimationFrame(resolve))
    expect(isInlineEditEnterGuarded()).toBe(false)
  })

  it('detects inline edit key targets', () => {
    const wrapper = document.createElement('div')
    wrapper.className = 'inline-edit-wrapper'
    const input = document.createElement('textarea')
    input.className = 'inline-edit-input'
    wrapper.appendChild(input)
    document.body.appendChild(wrapper)

    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    Object.defineProperty(event, 'target', { value: input })
    expect(isInlineDiagramEditKeyEvent(event)).toBe(true)
    expect(isInlineDiagramEditDomActive()).toBe(true)

    document.body.removeChild(wrapper)
  })

  it('prefers post-edit sibling anchor over stale selection', () => {
    initInlineEditEnterGuard()
    setMindMapPostEditSiblingAnchor('branch-r-1-0')
    expect(consumeMindMapPostEditSiblingAnchor('branch-l-1-0')).toBe('branch-r-1-0')
    expect(consumeMindMapPostEditSiblingAnchor('branch-l-1-0')).toBe('branch-l-1-0')
  })

  it('clears post-edit sibling anchor on pane click', () => {
    initInlineEditEnterGuard()
    setMindMapPostEditSiblingAnchor('branch-r-1-0')
    eventBus.emit('canvas:pane_clicked', {})
    expect(consumeMindMapPostEditSiblingAnchor('branch-l-1-0')).toBe('branch-l-1-0')
  })
})
