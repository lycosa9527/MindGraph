/**
 * Screen-space + handle layouts for tree-map contextual add.
 * Categories run left↔right under the topic; leaves stack top↔bottom in a column.
 */
import {
  TREE_TOPIC_NODE_ID,
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
} from '@/utils/treeMapIdentity'

export type TreeMapAddAction =
  'category-before' | 'category-after' | 'leaf-append' | 'leaf-before' | 'leaf-after'

export type TreeMapAddSelectionKind = 'topic' | 'category' | 'leaf'

export type TreeMapAddHandleLayout = {
  action: TreeMapAddAction
  left: number
  top: number
}

export type TreeMapAddRect = {
  left: number
  top: number
  right: number
  bottom: number
  width: number
  height: number
}

export function resolveTreeMapAddSelectionKind(node: {
  id?: string
  type?: string
  data?: Record<string, unknown>
}): TreeMapAddSelectionKind | null {
  if (node.id === TREE_TOPIC_NODE_ID || node.type === 'topic') return 'topic'
  if (isTreeMapCategoryNode(node)) return 'category'
  if (isTreeMapLeafNode(node)) return 'leaf'
  return null
}

/**
 * Place + handles around the selected tree node.
 * - Topic: + below inserts the next category.
 * - Category: left/right insert predecessor/successor; bottom appends a leaf.
 * - Leaf: top/bottom insert predecessor/successor under the same category.
 */
export function layoutTreeMapAddHandles(
  kind: TreeMapAddSelectionKind,
  rect: TreeMapAddRect
): TreeMapAddHandleLayout[] {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  switch (kind) {
    case 'topic':
      return [{ action: 'category-after', left: cx, top: rect.bottom }]
    case 'category':
      return [
        { action: 'category-before', left: rect.left, top: cy },
        { action: 'leaf-append', left: cx, top: rect.bottom },
        { action: 'category-after', left: rect.right, top: cy },
      ]
    case 'leaf':
      return [
        { action: 'leaf-before', left: cx, top: rect.top },
        { action: 'leaf-after', left: cx, top: rect.bottom },
      ]
  }
}
