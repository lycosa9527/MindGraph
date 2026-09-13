/**
 * Assemble the generate_graph body for 智能生成子图.
 * Structural prompt stays in formatMindMapSubgraphPrompt; 专业内容 is a
 * first-class generation_instructions field (same helper as full generate).
 */
import { withMindMapAudienceContext } from '@/composables/mindMap/audience/withMindMapAudienceContext'
import {
  formatMindMapSubgraphPrompt,
  type MindMapSubgraphContext,
} from '@/utils/mindMapSubgraphContext'

export function buildMindMapSubgraphGenerateBody(options: {
  context: MindMapSubgraphContext
  language: string
  llm: string
  diagramId?: string | null
}): Record<string, unknown> {
  const { context, language, llm, diagramId } = options
  const body: Record<string, unknown> = {
    prompt: formatMindMapSubgraphPrompt(context, language),
    diagram_type: 'mindmap',
    language,
    request_type: 'autocomplete',
    llm,
    expand_branch: context.expandBranch,
  }
  if (context.topic) {
    body.mind_map_topic = context.topic
  }
  if (context.referenceBranches.length > 0) {
    body.reference_branches = context.referenceBranches
  }
  if (context.existingChildren.length > 0) {
    body.existing_branch_children = context.existingChildren
  }
  if (context.parentBranch) {
    body.parent_branch = context.parentBranch
  }
  if (diagramId) {
    body.diagram_id = diagramId
  }
  return withMindMapAudienceContext(body, language)
}
