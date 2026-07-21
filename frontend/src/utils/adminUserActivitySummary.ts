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

const ACTION_VERBS_ZH: Record<string, string> = {
  diagram_generate: '生成',
  diagram_save: '保存',
  dingtalk_diagram: '钉钉导图',
  autocomplete: '自动补全',
  export_diagram: '导出',
  voice_session: '语音会话',
  one_sentence_generate: '一句话生成',
  one_sentence_edit: '一句话编辑',
  knowledge_query: '知识检索',
  knowledge_ingest: '知识入库',
  doc_summary_session: '文档摘要',
  workshop_collab: '协作画布',
  workshop_chat: '工作坊聊天',
  askonce_turn: 'AskOnce',
  debate_turn: '辩论',
  market_order: '市场订单',
  library_engage: '图书馆',
  showcase_engage: '展示墙',
  canvas_translate: '画布翻译',
  relationship_labels: '关系标签',
}

const ACTION_VERBS_EN: Record<string, string> = {
  diagram_generate: 'Generated',
  diagram_save: 'Saved',
  dingtalk_diagram: 'DingTalk diagram',
  autocomplete: 'Autocomplete',
  export_diagram: 'Exported',
  voice_session: 'Voice session',
  one_sentence_generate: 'One-sentence generate',
  one_sentence_edit: 'One-sentence edit',
  knowledge_query: 'Knowledge query',
  knowledge_ingest: 'Knowledge ingest',
  doc_summary_session: 'Doc summary',
  workshop_collab: 'Workshop collab',
  workshop_chat: 'Workshop chat',
  askonce_turn: 'AskOnce',
  debate_turn: 'Debate',
  market_order: 'Market order',
  library_engage: 'Library',
  showcase_engage: 'Showcase',
  canvas_translate: 'Canvas translate',
  relationship_labels: 'Relationship labels',
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

function actionVerb(
  action: string,
  labels: ActivitySummaryLabels,
  locale: string
): string {
  if (action === 'diagram_save') {
    return labels.save
  }
  if (action === 'dingtalk_diagram') {
    return labels.dingtalkGenerate
  }
  if (action === 'diagram_generate') {
    return labels.generate
  }
  const verbs = locale.startsWith('zh') ? ACTION_VERBS_ZH : ACTION_VERBS_EN
  return verbs[action] ?? labels.generate
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

  const verb = actionVerb(action, labels, locale)
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
