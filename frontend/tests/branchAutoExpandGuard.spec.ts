import { describe, expect, it } from 'vitest'

import {
  type BranchAutoExpandState,
  TOPIC_NODE_ID,
  shouldAutoExpandBranch,
} from '@/composables/editor/branchAutoExpandGuard'

function baseState(overrides: Partial<BranchAutoExpandState> = {}): BranchAutoExpandState {
  return {
    enabled: true,
    isMindMap: true,
    collabActive: false,
    isGenerating: false,
    alreadyAttempted: false,
    completedSourceCount: 1,
    trimmedText: 'Chapter 5',
    isPlaceholder: false,
    nodeId: 'branch_1',
    isTopLevelBranch: true,
    hasChildren: false,
    diagramSaved: true,
    liveTranslationActive: false,
    ...overrides,
  }
}

describe('shouldAutoExpandBranch', () => {
  it('expands a committed top-level branch when the package has sources', () => {
    expect(shouldAutoExpandBranch(baseState())).toBe(true)
  })

  it('does not expand when the feature flag is off', () => {
    expect(shouldAutoExpandBranch(baseState({ enabled: false }))).toBe(false)
  })

  it('does not expand non-mind-map diagrams', () => {
    expect(shouldAutoExpandBranch(baseState({ isMindMap: false }))).toBe(false)
  })

  it('does not expand during a collab session', () => {
    expect(shouldAutoExpandBranch(baseState({ collabActive: true }))).toBe(false)
  })

  it('does not expand while another generation is in flight', () => {
    expect(shouldAutoExpandBranch(baseState({ isGenerating: true }))).toBe(false)
  })

  it('expands a branch only once (cost guard)', () => {
    expect(shouldAutoExpandBranch(baseState({ alreadyAttempted: true }))).toBe(false)
  })

  it('does not expand when the package has no indexed sources', () => {
    expect(shouldAutoExpandBranch(baseState({ completedSourceCount: 0 }))).toBe(false)
  })

  it('does not expand placeholder or empty labels', () => {
    expect(shouldAutoExpandBranch(baseState({ isPlaceholder: true }))).toBe(false)
    expect(shouldAutoExpandBranch(baseState({ trimmedText: '' }))).toBe(false)
  })

  it('never expands the topic node itself', () => {
    expect(shouldAutoExpandBranch(baseState({ nodeId: TOPIC_NODE_ID }))).toBe(false)
  })

  it('does not expand when the diagram is not saved yet', () => {
    expect(shouldAutoExpandBranch(baseState({ diagramSaved: false }))).toBe(false)
  })

  it('does not expand when live translation is active', () => {
    expect(shouldAutoExpandBranch(baseState({ liveTranslationActive: true }))).toBe(false)
  })

  it('does not expand non-top-level nodes or branches that already have children', () => {
    expect(shouldAutoExpandBranch(baseState({ isTopLevelBranch: false }))).toBe(false)
    expect(shouldAutoExpandBranch(baseState({ hasChildren: true }))).toBe(false)
  })
})
