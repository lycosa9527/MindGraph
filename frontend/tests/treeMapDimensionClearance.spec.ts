/**
 * Tree-map classification label and wrapped node text stay in their own boxes.
 */
import { describe, expect, it } from 'vitest'

import { loadTreeMapSpec, recalculateTreeMapLayout } from '@/stores/specLoader/treeMap'
import type { DiagramNode } from '@/types'
import {
  TREE_MAP_DIMENSION_GAP_BELOW,
  measureTreeMapDimensionLabelBox,
} from '@/utils/treeMapLabelLayout'
import { measureTreeMapNodeBox } from '@/utils/treeMapNodeBox'

function nodeByText(nodes: DiagramNode[], text: string): DiagramNode {
  const found = nodes.find((node) => node.text === text)
  if (!found?.position) throw new Error(`missing node ${text}`)
  return found
}

function bottom(node: DiagramNode): number {
  return (node.position?.y ?? 0) + (typeof node.style?.height === 'number' ? node.style.height : 0)
}

const LONG_DIMENSION = '服务机制与组织形态以及社区参与和资源调配方式的进一步说明'

describe('tree map dimension label clearance', () => {
  it('places categories below a long classification label', () => {
    const loaded = loadTreeMapSpec({
      topic: '志愿服务活动',
      dimension: LONG_DIMENSION,
      children: [
        {
          text: '临时劫费响应型',
          children: [{ text: '突发公共事件街头募捐' }],
        },
      ],
    })
    const nodes = recalculateTreeMapLayout(loaded.nodes, {})
    const label = nodeByText(nodes, LONG_DIMENSION)
    const category = nodeByText(nodes, '临时劫费响应型')
    const leaf = nodeByText(nodes, '突发公共事件街头募捐')
    const labelBox = measureTreeMapDimensionLabelBox(LONG_DIMENSION)
    const shortLabel = measureTreeMapDimensionLabelBox('类型')
    expect(labelBox.height).toBeGreaterThan(shortLabel.height)

    expect(category.position?.y ?? 0).toBeGreaterThanOrEqual(
      (label.position?.y ?? 0) + labelBox.height + TREE_MAP_DIMENSION_GAP_BELOW - 0.5
    )
    expect(leaf.position?.y ?? 0).toBeGreaterThanOrEqual(bottom(category) - 0.5)
  })

  it('drops the category row when the painted label is taller than the estimate', () => {
    const loaded = loadTreeMapSpec({
      topic: '志愿服务活动',
      dimension: '服务机制',
      children: [{ text: '响应型', children: [{ text: '募捐' }] }],
    })
    const shortLayout = recalculateTreeMapLayout(loaded.nodes, {})
    const tallLayout = recalculateTreeMapLayout(loaded.nodes, {
      'dimension-label': { width: 240, height: 96 },
    })
    const shortCategory = nodeByText(shortLayout, '响应型')
    const tallCategory = nodeByText(tallLayout, '响应型')
    const tallLabel = nodeByText(tallLayout, '服务机制')

    expect(tallCategory.position?.y ?? 0).toBeGreaterThan(shortCategory.position?.y ?? 0)
    expect(tallCategory.position?.y ?? 0).toBeGreaterThanOrEqual(
      (tallLabel.position?.y ?? 0) + 96 + TREE_MAP_DIMENSION_GAP_BELOW - 0.5
    )
  })

  it('keeps a fitting category on one line and clear of the label', () => {
    const dimension = '服务机制与组织形态'
    const categoryText = '临时劫费响应型'
    const loaded = loadTreeMapSpec({
      topic: '志愿服务活动',
      dimension,
      children: [{ text: categoryText, children: [{ text: '大型赛会短期招募' }] }],
    })
    const nodes = recalculateTreeMapLayout(loaded.nodes, {})
    const label = nodeByText(nodes, dimension)
    const category = nodeByText(nodes, categoryText)
    const labelBox = measureTreeMapDimensionLabelBox(dimension)
    const categoryBox = measureTreeMapNodeBox(categoryText, { role: 'category', fontSize: 16 })
    const oneLine = measureTreeMapNodeBox('类型', { role: 'category', fontSize: 16 })

    expect(categoryBox.height).toBe(oneLine.height)
    expect(category.position?.y ?? 0).toBeGreaterThanOrEqual(
      (label.position?.y ?? 0) + labelBox.height + TREE_MAP_DIMENSION_GAP_BELOW - 0.5
    )
  })

  it('grows a long category to its wrapped lines instead of overlapping the leaf', () => {
    const text = '突发公共事件街头募捐以及连续多日的社区值守和物资分发安排说明'
    const box = measureTreeMapNodeBox(text, { role: 'category', fontSize: 16 })
    const oneLine = measureTreeMapNodeBox('募捐', { role: 'category', fontSize: 16 })
    expect(box.height).toBeGreaterThan(oneLine.height)
    expect(box.width).toBeGreaterThan(oneLine.width)

    const loaded = loadTreeMapSpec({
      topic: '活动',
      dimension: '类型',
      children: [{ text, children: [{ text: '下一行' }] }],
    })
    const nodes = recalculateTreeMapLayout(loaded.nodes, {})
    const category = nodeByText(nodes, text)
    const leaf = nodeByText(nodes, '下一行')
    expect(leaf.position?.y ?? 0).toBeGreaterThanOrEqual(bottom(category) - 0.5)
  })
})
