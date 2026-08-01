import { describe, expect, it } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import {
  armInlineEditEnterGuard,
  clearMindMapPostEditSiblingAnchor,
  consumeMindMapPostEditSiblingAnchor,
  initInlineEditEnterGuard,
  isInlineDiagramEditDomActive,
  isInlineDiagramEditKeyEvent,
  isInlineDiagramEditOpen,
  isInlineEditEnterGuarded,
  reconcileOpenInlineEditorsWithDom,
  setMindMapPostEditSiblingAnchor,
  shouldBlockCanvasEnterShortcut,
} from '@/composables/mindMap/mindMapCanvasEnterGuard'

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

  it('uses selection when it differs from post-edit anchor (side switch)', () => {
    initInlineEditEnterGuard()
    clearMindMapPostEditSiblingAnchor()
    // Edited a left branch, then selected a right branch — Enter must stay on right.
    setMindMapPostEditSiblingAnchor('branch-l-1-0')
    expect(consumeMindMapPostEditSiblingAnchor('branch-r-1-0')).toBe('branch-r-1-0')
  })

  it('uses post-edit anchor when selection is empty after edit', () => {
    initInlineEditEnterGuard()
    clearMindMapPostEditSiblingAnchor()
    setMindMapPostEditSiblingAnchor('branch-r-1-0')
    expect(consumeMindMapPostEditSiblingAnchor(undefined)).toBe('branch-r-1-0')
    expect(consumeMindMapPostEditSiblingAnchor('branch-l-1-0')).toBe('branch-l-1-0')
  })

  it('clears post-edit sibling anchor on pane click', () => {
    initInlineEditEnterGuard()
    setMindMapPostEditSiblingAnchor('branch-r-1-0')
    eventBus.emit('canvas:pane_clicked', {})
    expect(consumeMindMapPostEditSiblingAnchor('branch-l-1-0')).toBe('branch-l-1-0')
  })

  it('self-heals zombie open-edit ownership when editor DOM is gone', () => {
    initInlineEditEnterGuard()
    eventBus.emit('node_editor:opening', { nodeId: 'branch-zombie' })
    expect(isInlineDiagramEditOpen()).toBe(true)

    // No .inline-edit-wrapper in document — Enter must not stay wedged.
    reconcileOpenInlineEditorsWithDom()
    expect(isInlineDiagramEditOpen()).toBe(false)

    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    expect(shouldBlockCanvasEnterShortcut(event)).toBe(false)
  })

  it('clears open ownership on node_editor:closed for that nodeId', () => {
    initInlineEditEnterGuard()
    // Ensure clean slate from prior tests.
    reconcileOpenInlineEditorsWithDom()
    eventBus.emit('node_editor:opening', { nodeId: 'branch-a' })
    eventBus.emit('node_editor:opening', { nodeId: 'branch-b' })
    expect(isInlineDiagramEditOpen()).toBe(true)
    eventBus.emit('node_editor:closed', { nodeId: 'branch-a' })
    expect(isInlineDiagramEditOpen()).toBe(true)
    eventBus.emit('node_editor:closed', { nodeId: 'branch-b' })
    expect(isInlineDiagramEditOpen()).toBe(false)
  })
})
