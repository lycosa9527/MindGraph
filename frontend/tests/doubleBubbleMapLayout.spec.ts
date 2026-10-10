/**
 * Double-bubble difference columns size from their own text.
 */
import { describe, expect, it } from 'vitest'

import { DEFAULT_COLUMN_SPACING, DEFAULT_PADDING } from '@/composables/diagrams/layoutConfig'
import { loadDoubleBubbleMapSpec } from '@/stores/specLoader/doubleBubbleMap'
import type { DiagramNode } from '@/types'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'

function roleNodes(nodes: DiagramNode[], role: 'leftDiff' | 'rightDiff'): DiagramNode[] {
  return nodes.filter((node) => readDoubleBubbleRole(node) === role)
}

function boxWidth(node: DiagramNode): number {
  return node.style?.width ?? 0
}

function boxHeight(node: DiagramNode): number {
  return node.style?.height ?? 0
}

function loadDiffs(
  leftDifferences: string[],
  rightDifferences: string[],
  extra: Record<string, unknown> = {}
) {
  return loadDoubleBubbleMapSpec({
    left: 'Apple',
    right: 'Banana',
    similarities: ['fruit'],
    leftDifferences,
    rightDifferences,
    ...extra,
  })
}

describe('double bubble difference column widths', () => {
  it('keeps a long left column wider than a short right column', () => {
    const { nodes } = loadDoubleBubbleMapSpec({
      left: 'Apple',
      right: 'Banana',
      similarities: ['fruit', 'sweet'],
      leftDifferences: ['a very long unique trait that should widen only the left column', 'short'],
      rightDifferences: ['red', 'soft'],
    })

    const left = roleNodes(nodes, 'leftDiff')
    const right = roleNodes(nodes, 'rightDiff')
    const leftTopic = nodes.find((node) => node.id === 'left-topic')
    const rightTopic = nodes.find((node) => node.id === 'right-topic')
    expect(left).toHaveLength(2)
    expect(right).toHaveLength(2)
    expect(leftTopic).toBeTruthy()
    expect(rightTopic).toBeTruthy()

    const leftWidth = boxWidth(left[0])
    const rightWidth = boxWidth(right[0])
    expect(leftWidth).toBeGreaterThan(rightWidth)
    expect(left.map(boxWidth)).toEqual([leftWidth, leftWidth])
    expect(right.map(boxWidth)).toEqual([rightWidth, rightWidth])

    const leftGap = (leftTopic?.position.x ?? 0) - ((left[0].position.x ?? 0) + leftWidth)
    const rightGap =
      (right[0].position.x ?? 0) - ((rightTopic?.position.x ?? 0) + (rightTopic?.style?.size ?? 0))
    expect(leftGap).toBe(DEFAULT_COLUMN_SPACING)
    expect(rightGap).toBe(DEFAULT_COLUMN_SPACING)
    expect(left[0].position.x).toBe(DEFAULT_PADDING)
    expect(nodes.every((node) => node.position.x >= DEFAULT_PADDING)).toBe(true)

    for (let index = 0; index < left.length; index += 1) {
      const leftCenter = left[index].position.y + boxHeight(left[index]) / 2
      const rightCenter = right[index].position.y + boxHeight(right[index]) / 2
      expect(leftCenter).toBe(rightCenter)
    }
  })

  it('keeps a long right column wider than a short left column', () => {
    const { nodes } = loadDiffs(
      ['red'],
      ['a very long unique trait that should widen only the right column']
    )
    const left = roleNodes(nodes, 'leftDiff')
    const right = roleNodes(nodes, 'rightDiff')
    expect(boxWidth(right[0])).toBeGreaterThan(boxWidth(left[0]))
    expect(left[0].position.x).toBe(DEFAULT_PADDING)
    expect(nodes.every((node) => node.position.x >= DEFAULT_PADDING)).toBe(true)
  })

  it('keeps matching labels the same width', () => {
    const { nodes } = loadDiffs(['same label'], ['same label'])
    const left = roleNodes(nodes, 'leftDiff')
    const right = roleNodes(nodes, 'rightDiff')
    expect(boxWidth(left[0])).toBe(boxWidth(right[0]))
    expect(boxHeight(left[0])).toBe(boxHeight(right[0]))
  })

  it('measures live text instead of a saved radius shared by both columns', () => {
    const { nodes } = loadDiffs(['a very long unique trait on the left only'], ['red'], {
      _doubleBubbleMapNodeSizes: {
        leftDiffRadii: [200],
        rightDiffRadii: [200],
      },
    })
    const left = roleNodes(nodes, 'leftDiff')
    const right = roleNodes(nodes, 'rightDiff')
    expect(boxWidth(left[0])).toBeGreaterThan(boxWidth(right[0]))
    expect(boxWidth(right[0])).toBeLessThan(200)
  })

  it('does not let an empty column stretch the other column', () => {
    const { nodes } = loadDiffs(['x', 'x'], [])
    const left = roleNodes(nodes, 'leftDiff')
    expect(left).toHaveLength(2)
    expect(roleNodes(nodes, 'rightDiff')).toHaveLength(0)
    const pitch = left[1].position.y - left[0].position.y
    expect(pitch).toBe(boxHeight(left[0]) + 10)
    expect(nodes.every((node) => node.position.x >= DEFAULT_PADDING)).toBe(true)
  })
})
