import { describe, expect, it } from 'vitest'

import {
  estimateNumberedBranchWidth,
  measureNumberedBranchHeight,
  measureNumberedBranchUnderlineHeight,
} from '@/stores/specLoader/mindMap'
import { estimateMindMapBranchSizes } from '@/stores/specLoader/mindMapNumberingEstimate'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'
import type { Connection, DiagramNode } from '@/types'
import { buildMindMapBranchNumberMap } from '@/utils/mindMapBranchNumbering'
import { resolveNodeShape } from '@/utils/nodeShapeStyle'

function node(
  id: string,
  text: string,
  type: DiagramNode['type'] = 'branch',
  style?: DiagramNode['style']
): DiagramNode {
  return { id, text, type, position: { x: 0, y: 0 }, ...(style ? { style } : {}) }
}

function edge(id: string, source: string, target: string): Connection {
  return { id, source, target }
}

describe('estimateMindMapBranchSizes', () => {
  it('matches per-node width and height, including wrap and underline', () => {
    const long = '这是一段足够长的思维导图分支文字用来触发换行限制检查一二三四五六七八九十'
    const nodes = [
      node('topic', '主题', 'topic'),
      node('a', '短'),
      node('b', long),
      node('c', '子节点'),
      node('d', long, 'branch', { nodeShape: 'underline' }),
      node('e', '加粗标题', 'branch', { fontSize: 20, fontWeight: 'bold' }),
    ]
    const connections = [
      edge('e1', 'topic', 'a'),
      edge('e2', 'topic', 'b'),
      edge('e3', 'a', 'c'),
      edge('e4', 'topic', 'd'),
      edge('e5', 'topic', 'e'),
    ]
    const numberMap = buildMindMapBranchNumberMap(nodes, connections, 'decimal', 'outline')
    const sizes = estimateMindMapBranchSizes(nodes, numberMap)

    expect(sizes.has('topic')).toBe(false)
    for (const branch of nodes) {
      if (branch.id === 'topic') continue
      const prefix = numberMap.get(branch.id) ?? ''
      const shape = resolveNodeShape(branch.style, true)
      const height =
        shape === 'underline'
          ? measureNumberedBranchUnderlineHeight(branch.text, prefix, branch.id, branch.style)
          : measureNumberedBranchHeight(branch.text, prefix, branch.id, branch.style)
      expect(sizes.get(branch.id)).toEqual({
        width: estimateNumberedBranchWidth(branch.text, prefix, branch.id, branch.style),
        height,
      })
    }
  })

  it('does not leave measured widths cached after the batch', () => {
    const nodes = [node('topic', 'T', 'topic'), node('a', '编号')]
    const connections = [edge('e1', 'topic', 'a')]
    const numberMap = buildMindMapBranchNumberMap(nodes, connections)
    estimateMindMapBranchSizes(nodes, numberMap)
    const first = measureTextWidth('编号', 16)
    const second = measureTextWidth('编号', 16)
    expect(second).toBe(first)
  })
})
