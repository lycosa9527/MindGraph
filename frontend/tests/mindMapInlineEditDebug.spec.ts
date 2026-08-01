import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getMindMapInlineEditDebugRecent,
  isMindMapInlineEditDebugEnabled,
  markMindMapInlineEditStage,
  setMindMapInlineEditDebugEnabled,
} from '@/utils/mindMapInlineEditDebug'

describe('mindMapInlineEditDebug', () => {
  afterEach(() => {
    setMindMapInlineEditDebugEnabled(false)
    vi.restoreAllMocks()
  })

  it('records stages even when logging is disabled', () => {
    setMindMapInlineEditDebugEnabled(false)
    markMindMapInlineEditStage('pending:arm', { nodeId: 'branch-r-1-0' })
    const recent = getMindMapInlineEditDebugRecent()
    expect(recent.at(-1)?.stage).toBe('pending:arm')
    expect(recent.at(-1)?.payload.nodeId).toBe('branch-r-1-0')
  })

  it('logs to console when enabled', () => {
    const info = vi.spyOn(console, 'info').mockImplementation(() => {})
    setMindMapInlineEditDebugEnabled(true)
    expect(isMindMapInlineEditDebugEnabled()).toBe(true)
    markMindMapInlineEditStage('branch:session-open', { nodeId: 'branch-l-1-0' })
    expect(info).toHaveBeenCalled()
    const message = String(info.mock.calls.at(-1)?.[0] ?? '')
    expect(message).toContain('[MindMapInlineEdit]')
    expect(message).toContain('branch:session-open')
  })
})
