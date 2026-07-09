import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import type { Connection, DiagramNode } from '@/types'

export interface MindMapSubgraphContext {
  topic: string
  expandBranch: string
  referenceBranches: string[]
  existingChildren: string[]
  parentBranch?: string
  /** True when the anchor is a top-level branch (child of the central topic). */
  isMainBranch: boolean
}

/** Whether the floating-toolbar AI subgraph action applies to this node. */
export function isMindMapSubgraphExpandable(nodeId: string | null | undefined): boolean {
  return Boolean(nodeId && nodeId !== 'topic')
}

function directChildrenInstruction(language: string, isMainBranch: boolean): string {
  const isZh = language === 'zh' || language.startsWith('zh-')
  if (isZh) {
    return isMainBranch
      ? '请为该主分支生成 4–6 个直接子节点（仅一层，不要嵌套更深层级）。'
      : '请为该子节点生成 4–6 个直接下级节点（仅一层，不要嵌套更深层级）。'
  }
  return isMainBranch
    ? 'Generate 4–6 direct child nodes for this main branch only (one level; no deeper nesting).'
    : 'Generate 4–6 direct child nodes for this sub-node only (one level; no deeper nesting).'
}

function formatBranchListZh(labels: string[]): string {
  return labels.join('、')
}

function formatBranchListEn(labels: string[]): string {
  return labels.join(', ')
}

/** Build the LLM prompt sent for mind map branch sub-graph expansion. */
export function formatMindMapSubgraphPrompt(
  context: MindMapSubgraphContext,
  language: string
): string {
  const isZh = language === 'zh' || language.startsWith('zh-')
  if (isZh) {
    const lines = [
      `中心主题：${context.topic || '（未设置）'}`,
      `要扩展的分支：${context.expandBranch}`,
    ]
    if (context.parentBranch) {
      lines.push(`上级分支：${context.parentBranch}`)
    }
    if (context.referenceBranches.length > 0) {
      lines.push(`图中其他分支（参考）：${formatBranchListZh(context.referenceBranches)}`)
    }
    if (context.existingChildren.length > 0) {
      lines.push(`该分支已有子节点（勿重复）：${formatBranchListZh(context.existingChildren)}`)
    }
    lines.push(directChildrenInstruction(language, context.isMainBranch))
    return lines.join('\n')
  }

  const lines = [
    `Central topic: ${context.topic || '(not set)'}`,
    `Branch to expand: ${context.expandBranch}`,
  ]
  if (context.parentBranch) {
    lines.push(`Parent branch: ${context.parentBranch}`)
  }
  if (context.referenceBranches.length > 0) {
    lines.push(`Other branches in the map (reference): ${formatBranchListEn(context.referenceBranches)}`)
  }
  if (context.existingChildren.length > 0) {
    lines.push(
      `Existing children under this branch (do not duplicate): ${formatBranchListEn(context.existingChildren)}`
    )
  }
  lines.push(directChildrenInstruction(language, context.isMainBranch))
  return lines.join('\n')
}

function childIds(parentId: string, connections: Connection[]): string[] {
  return connections.filter((c) => c.source === parentId).map((c) => c.target)
}

function parentIdOf(nodeId: string, connections: Connection[]): string | null {
  const link = connections.find((c) => c.target === nodeId)
  return link?.source ?? null
}

function uniqueNonEmptyLabels(labels: string[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const raw of labels) {
    const text = raw.trim()
    if (!text || seen.has(text)) continue
    seen.add(text)
    result.push(text)
  }
  return result
}

const MAX_REFERENCE_BRANCHES = 24

function usableLabel(text: string): string {
  const trimmed = text.trim()
  if (!trimmed || isPlaceholderText(trimmed)) return ''
  return trimmed
}

export function collectMindMapSubgraphContext(
  nodes: DiagramNode[],
  connections: Connection[],
  anchorNodeId: string
): MindMapSubgraphContext | null {
  if (anchorNodeId === 'topic') return null

  const anchor = nodes.find((n) => n.id === anchorNodeId)
  if (!anchor) return null

  const expandBranch = usableLabel(anchor.text ?? '')
  if (!expandBranch) return null

  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const topic = usableLabel(nodeMap.get('topic')?.text ?? '')

  const topLevelIds = childIds('topic', connections)
  const topLevelBranches = topLevelIds
    .map((id) => usableLabel(nodeMap.get(id)?.text ?? ''))
    .filter(Boolean)
    .filter((text) => text !== expandBranch)

  const parentId = parentIdOf(anchorNodeId, connections)
  const isMainBranch = parentId === 'topic'
  let siblingBranches: string[] = []
  let parentBranch: string | undefined

  if (parentId) {
    if (!isMainBranch) {
      const parentText = usableLabel(nodeMap.get(parentId)?.text ?? '')
      if (parentText) {
        parentBranch = parentText
      }
    }
    siblingBranches = childIds(parentId, connections)
      .filter((id) => id !== anchorNodeId)
      .map((id) => usableLabel(nodeMap.get(id)?.text ?? ''))
      .filter(Boolean)
  }

  const referenceBranches = uniqueNonEmptyLabels([...siblingBranches, ...topLevelBranches])
    .filter((label) => label !== expandBranch)
    .slice(0, MAX_REFERENCE_BRANCHES)

  const existingChildren = childIds(anchorNodeId, connections)
    .map((id) => usableLabel(nodeMap.get(id)?.text ?? ''))
    .filter(Boolean)
    .slice(0, MAX_REFERENCE_BRANCHES)

  return {
    topic,
    expandBranch,
    referenceBranches,
    existingChildren,
    parentBranch,
    isMainBranch,
  }
}
