import { describe, expect, it } from 'vitest'

import type { DiagramNode } from '@/types'
import {
  TREE_TOPIC_NODE_ID,
  stampTreeCategoryData,
  stampTreeLeafData,
} from '@/utils/treeMapIdentity'
import { buildTreeMapSlides } from '@/utils/treeMapSlides'

function topic(text: string): DiagramNode {
  return {
    id: TREE_TOPIC_NODE_ID,
    text,
    type: 'topic',
    position: { x: 0, y: 0 },
  }
}

function category(id: string, text: string, index: number): DiagramNode {
  return {
    id,
    text,
    type: 'branch',
    position: { x: 0, y: 0 },
    data: stampTreeCategoryData(index, { treeMapUid: id }),
  }
}

function leaf(
  id: string,
  text: string,
  categoryIndex: number,
  leafIndex: number,
  parentCategoryId: string
): DiagramNode {
  return {
    id,
    text,
    type: 'branch',
    position: { x: 0, y: 0 },
    data: stampTreeLeafData(categoryIndex, leafIndex, parentCategoryId, { treeMapUid: id }),
  }
}

describe('buildTreeMapSlides', () => {
  const nodes: DiagramNode[] = [
    topic('动物'),
    category('cat-a', '哺乳类', 0),
    category('cat-b', '鸟类', 1),
    leaf('leaf-a1', '猫', 0, 0, 'cat-a'),
    leaf('leaf-a2', '狗', 0, 1, 'cat-a'),
    leaf('leaf-b1', '麻雀', 1, 0, 'cat-b'),
  ]

  it('firstLevel walks overview → each category with its leaves focused', () => {
    const slides = buildTreeMapSlides(nodes, 'firstLevel')
    expect(slides.map((slide) => slide.id)).toEqual(['overview', 'cat-a', 'cat-b'])
    expect(slides[0]?.title).toBe('动物')
    expect(slides[0]?.focusNodeIds).toHaveLength(nodes.length)
    expect(slides.find((slide) => slide.id === 'cat-a')?.focusNodeIds).toEqual([
      'cat-a',
      'leaf-a1',
      'leaf-a2',
    ])
    expect(slides.find((slide) => slide.id === 'cat-b')?.focusNodeIds).toEqual(['cat-b', 'leaf-b1'])
    expect(slides.find((slide) => slide.id === 'cat-a')?.breadcrumb).toEqual(['动物', '哺乳类'])
  })

  it('deep walks each category then its leaves in order', () => {
    const slides = buildTreeMapSlides(nodes, 'deep')
    expect(slides.map((slide) => slide.id)).toEqual([
      'overview',
      'cat-a',
      'leaf-a1',
      'leaf-a2',
      'cat-b',
      'leaf-b1',
    ])
    expect(slides.find((slide) => slide.id === 'leaf-a2')?.focusNodeIds).toEqual([
      'cat-a',
      'leaf-a2',
    ])
    expect(slides.find((slide) => slide.id === 'leaf-a2')?.breadcrumb).toEqual([
      '动物',
      '哺乳类',
      '狗',
    ])
  })
})
