import { reactive } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  TRAINING_DRAG_MARK_BAD_MS,
  TRAINING_DRAG_MARK_OK_MS,
  bindTrainingDragSurface,
  clearTrainingDragMarks,
  clearTrainingDragSurface,
  noteTrainingDragWrongDrop,
  setTrainingDragPicking,
  trainingDragBlankIds,
  trainingDragDropActive,
  trainingDragDropOnNode,
  trainingDragFilledIds,
  trainingDragHint,
  trainingDragKnockActive,
  trainingDragKnockNode,
  trainingDragMarks,
  trainingDragPicking,
} from '@/composables/training/trainingDragKnock'
import { toggleInteractBlank } from '@/composables/training/trainingInteract'
import type { TrainingCourseStep, TrainingInteractBlank } from '@/types/training'

function dragStep(blanks: TrainingInteractBlank[], saved = true): TrainingCourseStep {
  return {
    position: 0,
    type: 'canvas',
    page_key: 'canvas',
    interact: {
      mode: 'drag',
      read_order: [],
      blanks,
      quizzes: [],
      sequence_saved: saved,
      node_extras: [],
    },
  }
}

describe('trainingDragKnock', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    clearTrainingDragSurface()
  })

  afterEach(() => {
    clearTrainingDragSurface()
    vi.useRealTimers()
  })

  it('grades a drop only while the word bank is open', () => {
    bindTrainingDragSurface(dragStep([{ node_id: 'a', answer: '主题A' }]))
    expect(trainingDragDropOnNode('a', '主题A')).toBe(false)
    trainingDragDropActive.value = true
    expect(trainingDragDropOnNode('a', '主题A')).toBe(true)
    expect(trainingDragMarks.value.a).toBe(true)
    expect(trainingDragFilledIds.value).toEqual(['a'])
    expect(trainingDragDropOnNode('a', '别的')).toBe(false)
    expect(trainingDragMarks.value.a).toBe(true)
    expect(trainingDragDropOnNode('missing', '主题A')).toBe(false)
  })

  it('keeps a correct word and fades the check, then the cross', () => {
    bindTrainingDragSurface(
      dragStep([
        { node_id: 'a', answer: '主题A' },
        { node_id: 'b', answer: '主题B' },
      ])
    )
    trainingDragDropActive.value = true
    expect(trainingDragDropOnNode('a', '主题A')).toBe(true)
    expect(trainingDragDropOnNode('b', '别的')).toBe(false)
    vi.advanceTimersByTime(TRAINING_DRAG_MARK_BAD_MS - 1)
    expect(trainingDragMarks.value.b).toBe(false)
    vi.advanceTimersByTime(1)
    expect(trainingDragMarks.value.b).toBeUndefined()
    expect(trainingDragFilledIds.value).toEqual(['a'])
    expect(trainingDragMarks.value.a).toBe(true)
    vi.advanceTimersByTime(TRAINING_DRAG_MARK_OK_MS - TRAINING_DRAG_MARK_BAD_MS)
    expect(trainingDragMarks.value.a).toBeUndefined()
    expect(trainingDragFilledIds.value).toEqual(['a'])
  })

  it('opens the node hint after a wrong drop', () => {
    bindTrainingDragSurface(dragStep([{ node_id: 'a', answer: '主题A', hint: '想想主题' }]))
    trainingDragDropActive.value = true
    expect(trainingDragDropOnNode('a', '别的')).toBe(false)
    noteTrainingDragWrongDrop('a')
    expect(trainingDragHint.value).toEqual({
      nodeId: 'a',
      text: '想想主题',
      editable: false,
    })
  })

  it('keeps the diagram blanks on the same list the dock shows', () => {
    const row = reactive(dragStep([], false))
    bindTrainingDragSurface(row)
    expect(trainingDragBlankIds.value).toEqual([])
    toggleInteractBlank(row, { id: 'n1', text: '子项1.1' })
    expect(trainingDragBlankIds.value).toEqual(['n1'])
    toggleInteractBlank(row, { id: 'n2', text: '分支4' })
    expect(trainingDragBlankIds.value).toEqual(['n1', 'n2'])
  })

  it('ignores hammer clicks until drag-to-build is on', () => {
    expect(trainingDragKnockNode('a')).toBe(false)
    trainingDragKnockActive.value = true
    expect(trainingDragKnockNode('a')).toBe(false)
  })

  it('turns the hammer off after finish picking and clears drop marks', () => {
    trainingDragKnockActive.value = true
    trainingDragMarks.value = { a: true }
    setTrainingDragPicking(false)
    expect(trainingDragPicking.value).toBe(false)
    expect(trainingDragKnockActive.value).toBe(false)
    expect(trainingDragKnockNode('a')).toBe(false)
    clearTrainingDragMarks()
    expect(trainingDragMarks.value).toEqual({})
    setTrainingDragPicking(true)
    expect(trainingDragPicking.value).toBe(true)
  })
})
