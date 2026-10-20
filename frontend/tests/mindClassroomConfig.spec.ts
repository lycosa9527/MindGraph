import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { beforeEach, describe, expect, it } from 'vitest'

import {
  diagramSupportsSlideDeck,
  loadMindClassroomMastery,
  loadMindClassroomPresentation,
  loadMindClassroomSlideStyle,
  loadMindClassroomTone,
  loadMindClassroomTourScope,
  resolveMindClassroomPresentation,
} from '@/config/mindClassroom'

describe('mind classroom preferences', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('uses safe defaults for missing and invalid values', () => {
    localStorage.setItem('mg-mind-classroom-mastery', 'invalid')
    localStorage.setItem('mg-mind-classroom-tone', 'invalid')

    expect(loadMindClassroomMastery()).toBe('first_look')
    expect(loadMindClassroomPresentation()).toBe('canvas_tour')
    expect(loadMindClassroomTourScope()).toBe('main_branch')
    expect(loadMindClassroomSlideStyle()).toBe('general')
    expect(loadMindClassroomTone()).toBe('classroom')
  })

  it('migrates retired presentation and tour values', () => {
    localStorage.setItem('mg-mind-classroom-presentation', 'node_focus')

    expect(loadMindClassroomPresentation()).toBe('canvas_tour')
    expect(loadMindClassroomTourScope()).toBe('each_node')
  })

  it('migrates legacy style values to current presentation and slide styles', () => {
    localStorage.setItem('mg-mind-classroom-style', 'ppt')
    localStorage.setItem('mg-mind-classroom-slide-style', 'journal')

    expect(loadMindClassroomPresentation()).toBe('slide_deck')
    expect(loadMindClassroomTourScope()).toBe('main_branch')
    expect(loadMindClassroomSlideStyle()).toBe('handdrawn')
    expect(localStorage.getItem('mg-mind-classroom-slide-style')).toBe('handdrawn')
  })

  it('keeps slide lecture only when the feature is enabled', () => {
    expect(resolveMindClassroomPresentation('slide_deck', false)).toBe('canvas_tour')
    expect(resolveMindClassroomPresentation('slide_deck', true)).toBe('slide_deck')
    expect(resolveMindClassroomPresentation('canvas_tour', false)).toBe('canvas_tour')
  })

  it('keeps slide lecture on mind maps only', () => {
    expect(diagramSupportsSlideDeck('mindmap')).toBe(true)
    expect(diagramSupportsSlideDeck('mind_map')).toBe(true)
    expect(diagramSupportsSlideDeck('circle_map')).toBe(false)
    expect(diagramSupportsSlideDeck('bubble_map')).toBe(false)
    expect(diagramSupportsSlideDeck('concept_map')).toBe(false)
    expect(diagramSupportsSlideDeck(null)).toBe(false)
  })

  it('gates slide lecture in the shared launch UI used by every map type', () => {
    const text = readFileSync(
      resolve(__dirname, '../src/components/canvas/MindClassroomLaunchContent.vue'),
      'utf8'
    )
    expect(text).toContain("gated: id === 'slide_deck' && !slideDeckSelectable.value")
    expect(text).toContain('queueBusy || option.gated')
    expect(text).toContain('canvas.mindClassroom.settings.presentation.slide_deck.comingSoon')
    expect(text).toContain(':disabled="!option.gated"')
  })
})
