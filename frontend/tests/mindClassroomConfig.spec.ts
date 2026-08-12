import { beforeEach, describe, expect, it } from 'vitest'

import {
  loadMindClassroomMastery,
  loadMindClassroomPresentation,
  loadMindClassroomSlideStyle,
  loadMindClassroomTone,
  loadMindClassroomTourScope,
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
})
