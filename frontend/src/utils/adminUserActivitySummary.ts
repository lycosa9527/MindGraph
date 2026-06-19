/**
 * Format admin user activity row summary for the activity timeline tab.
 */

export interface AdminUserActivityRow {
  source: string
  action: string
  title?: string | null
  promptPreview?: string | null
  replyPreview?: string | null
  diagramType?: string | null
  success?: boolean
}

export interface ActivitySummaryLabels {
  ask: string
  answer: string
  generate: string
  save: string
  dingtalkGenerate: string
  sourceMindgraph: string
  sourceMindmate: string
  sourceDingtalk: string
  failedSuffix: string
}

const DIAGRAM_TYPE_LABELS_ZH: Record<string, string> = {
  mind_map: '思维导图',
  mindmap: '思维导图',
  bubble_map: '气泡图',
  double_bubble_map: '双气泡图',
  circle_map: '圆圈图',
  tree_map: '树形图',
  brace_map: '括号图',
  flow_map: '流程图',
  multi_flow_map: '复流程图',
  bridge_map: '桥形图',
  concept_map: '概念图',
}

const DIAGRAM_TYPE_LABELS_EN: Record<string, string> = {
  mind_map: 'Mind map',
  mindmap: 'Mind map',
  bubble_map: 'Bubble map',
  double_bubble_map: 'Double bubble map',
  circle_map: 'Circle map',
  tree_map: 'Tree map',
  brace_map: 'Brace map',
  flow_map: 'Flow map',
  multi_flow_map: 'Multi-flow map',
  bridge_map: 'Bridge map',
  concept_map: 'Concept map',
}

export function diagramTypeLabel(diagramType: string | null | undefined, locale: string): string {
  const key = (diagramType ?? '').trim()
  if (!key) {
    return ''
  }
  const labels = locale.startsWith('zh') ? DIAGRAM_TYPE_LABELS_ZH : DIAGRAM_TYPE_LABELS_EN
  return labels[key] ?? key.replace(/_/g, ' ')
}

export function activitySourceLabel(source: string, labels: ActivitySummaryLabels): string {
  if (source === 'mindmate') {
    return labels.sourceMindmate
  }
  if (source === 'dingtalk') {
    return labels.sourceDingtalk
  }
  return labels.sourceMindgraph
}

export function formatAdminUserActivitySummary(
  row: AdminUserActivityRow,
  labels: ActivitySummaryLabels,
  locale: string
): string {
  const action = row.action
  const isChat = action === 'chat_turn'
  const failed = row.success === false

  if (isChat) {
    const parts: string[] = []
    const prompt = (row.promptPreview ?? '').trim()
    const reply = (row.replyPreview ?? '').trim()
    if (prompt) {
      parts.push(`${labels.ask}${prompt}`)
    }
    if (reply) {
      parts.push(`${labels.answer}${reply}`)
    }
    let summary = parts.join(' → ')
    if (!summary) {
      summary = row.title?.trim() ?? '—'
    }
    if (failed) {
      summary += labels.failedSuffix
    }
    return summary
  }

  const verb =
    action === 'diagram_save'
      ? labels.save
      : action === 'dingtalk_diagram'
        ? labels.dingtalkGenerate
        : labels.generate
  const dtype = diagramTypeLabel(row.diagramType, locale)
  const title = (row.title ?? row.promptPreview ?? '').trim()
  const chunks = [verb]
  if (dtype) {
    chunks.push(dtype)
  }
  if (title) {
    chunks.push(`· ${title}`)
  }
  let summary = chunks.join(' ')
  if (failed) {
    summary += labels.failedSuffix
  }
  return summary || '—'
}
