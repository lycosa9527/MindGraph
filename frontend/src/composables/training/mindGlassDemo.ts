/**
 * Three slides for the MindGlass playback demo.
 * A spoken welcome, a bubble map that enters clockwise, then a double bubble to highlight.
 */
import type { TrainingCourseStep } from '@/types/training'

const THINKING_MAPS = [
  'Circle Map',
  'Bubble Map',
  'Double Bubble Map',
  'Tree Map',
  'Brace Map',
  'Flow Map',
  'Multi-Flow Map',
  'Bridge Map',
]

function base(position: number): TrainingCourseStep {
  return {
    position,
    type: 'slide',
    page_key: null,
    pull_users: true,
    diagram_type: null,
    topic_options: [],
    overlays: [],
    notes: '',
    mark_step: 1,
    mark_steps: 1,
    glasses_line: '',
    glasses_reveal: '',
    glasses_pace: 280,
    glasses_rate: 1,
  }
}

export function mindGlassDemoSteps(start: number): TrainingCourseStep[] {
  const welcome = base(start)
  welcome.glasses_line = 'Welcome to MindGlass demo, please tap to continue.'

  const bubble = base(start + 1)
  bubble.type = 'canvas'
  bubble.page_key = 'canvas'
  bubble.diagram_type = 'bubble_map'
  bubble.diagram_spec = { topic: 'Thinking Maps', attributes: THINKING_MAPS }
  bubble.glasses_line = 'Thinking Maps. Eight maps, one by one.'
  bubble.glasses_reveal = 'clockwise'

  const compared = base(start + 2)
  compared.type = 'canvas'
  compared.page_key = 'canvas'
  compared.diagram_type = 'double_bubble_map'
  compared.diagram_spec = {
    left: 'Bubble Map',
    right: 'Double Bubble Map',
    similarities: ['Uses bubbles', 'A thinking map'],
    leftDifferences: ['One topic'],
    rightDifferences: ['Two topics'],
  }
  compared.glasses_line = 'A double bubble map compares two ideas. The center is what they share.'
  compared.glasses_reveal = 'stages'
  return [welcome, bubble, compared]
}
