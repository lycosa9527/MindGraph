/**
 * Node-carousel slides for tree maps.
 * - firstLevel: overview → each category (category + its leaves focused)
 * - deep: overview → each category, then each leaf under that category
 */
import type { DiagramNode } from '@/types'
import type { MindMapSlide, MindMapSlideTraversalMode } from '@/utils/mindMapSlides'
import { TREE_TOPIC_NODE_ID, treeMapColumnsOf } from '@/utils/treeMapIdentity'

function nodeText(node: DiagramNode | undefined): string {
  if (!node) return ''
  return String(node.text ?? (node.data as { label?: string } | undefined)?.label ?? '').trim()
}

function branchSlide(
  id: string,
  title: string,
  breadcrumb: string[],
  focusNodeIds: string[],
  branchNodeId: string
): MindMapSlide {
  return {
    id,
    kind: 'branch',
    title,
    branchNodeId,
    breadcrumb,
    focusNodeIds,
  }
}

export function buildTreeMapSlides(
  nodes: DiagramNode[],
  mode: MindMapSlideTraversalMode = 'firstLevel'
): MindMapSlide[] {
  if (!nodes.length) return []

  const topic = nodes.find((node) => node.id === TREE_TOPIC_NODE_ID)
  const columns = treeMapColumnsOf(nodes)
  const rootTitle = nodeText(topic) || 'overview'
  const allIds = nodes.map((node) => node.id)
  const deep = mode === 'deep'

  const slides: MindMapSlide[] = [
    {
      id: 'overview',
      kind: 'overview',
      title: rootTitle,
      branchNodeId: topic?.id ?? columns[0]?.category.id,
      breadcrumb: [rootTitle],
      focusNodeIds: allIds,
    },
  ]

  for (const column of columns) {
    const category = column.category
    if (!category.id) continue
    const categoryTitle = nodeText(category) || category.id
    const leafIds = column.leaves.map((leaf) => leaf.id).filter((id): id is string => Boolean(id))
    const categoryFocus = [category.id, ...leafIds]
    slides.push(
      branchSlide(
        category.id,
        categoryTitle,
        [rootTitle, categoryTitle],
        categoryFocus,
        category.id
      )
    )
    if (!deep) continue
    for (const leaf of column.leaves) {
      if (!leaf.id) continue
      const leafTitle = nodeText(leaf) || leaf.id
      slides.push(
        branchSlide(
          leaf.id,
          leafTitle,
          [rootTitle, categoryTitle, leafTitle],
          [category.id, leaf.id],
          leaf.id
        )
      )
    }
  }

  return slides
}
