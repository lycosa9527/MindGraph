/**
 * Locale-aware placeholder strings for new diagrams and concept map edge/topic logic.
 */
import { i18n } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'
import { UI_LOCALE_CODES } from '@/i18n/locales'
import type { DiagramType } from '@/types'

function defaultsT(key: string, locale: LocaleCode, params?: Record<string, unknown>): string {
  return String(i18n.global.t(key, params ?? {}, { locale }))
}

/**
 * True when label text is still the blank diagram template for circle map (any UI locale).
 * Used so Insert equation replaces the template instead of appending after "Topic" / "Context n".
 */
export function isCircleMapDefaultNodeLabel(nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  for (const loc of UI_LOCALE_CODES) {
    if (nodeId === 'topic') {
      if (trimmed === defaultsT('diagram.defaults.topic', loc)) return true
      continue
    }
    const m = /^context-(\d+)$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.contextN', loc, { n: idx + 1 })) return true
      }
    }
  }
  return false
}

export function isBubbleMapDefaultNodeLabel(nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  for (const loc of UI_LOCALE_CODES) {
    if (nodeId === 'topic') {
      if (trimmed === defaultsT('diagram.defaults.topic', loc)) return true
      continue
    }
    const m = /^bubble-(\d+)$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.attributeN', loc, { n: idx + 1 })) return true
      }
    }
  }
  return false
}

export function isDoubleBubbleDefaultNodeLabel(nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  for (const loc of UI_LOCALE_CODES) {
    if (nodeId === 'left-topic') {
      if (trimmed === defaultsT('diagram.defaults.topicA', loc)) return true
    } else if (nodeId === 'right-topic') {
      if (trimmed === defaultsT('diagram.defaults.topicB', loc)) return true
    } else {
      const sim = /^similarity-(\d+)$/.exec(nodeId)
      if (sim) {
        const idx = parseInt(sim[1], 10)
        if (Number.isFinite(idx) && idx >= 0) {
          if (trimmed === defaultsT('diagram.doubleBubble.similarityN', loc, { n: idx + 1 })) {
            return true
          }
        }
      }
      const ld = /^left-diff-(\d+)$/.exec(nodeId)
      if (ld) {
        const idx = parseInt(ld[1], 10)
        if (Number.isFinite(idx) && idx >= 0) {
          if (trimmed === defaultsT('diagram.doubleBubble.differenceAn', loc, { n: idx + 1 })) {
            return true
          }
        }
      }
      const rd = /^right-diff-(\d+)$/.exec(nodeId)
      if (rd) {
        const idx = parseInt(rd[1], 10)
        if (Number.isFinite(idx) && idx >= 0) {
          if (trimmed === defaultsT('diagram.doubleBubble.differenceBn', loc, { n: idx + 1 })) {
            return true
          }
        }
      }
    }
  }
  return false
}

export function isMultiFlowDefaultNodeLabel(nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  for (const loc of UI_LOCALE_CODES) {
    if (nodeId === 'event') {
      if (trimmed === defaultsT('diagram.defaults.mainEvent', loc)) return true
      continue
    }
    let m = /^cause-(\d+)$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.causeN', loc, { n: idx + 1 })) return true
      }
      continue
    }
    m = /^effect-(\d+)$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.effectN', loc, { n: idx + 1 })) return true
      }
    }
  }
  return false
}

export function isFlowMapDefaultNodeLabel(nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  for (const loc of UI_LOCALE_CODES) {
    if (nodeId === 'flow-topic') {
      if (trimmed === defaultsT('diagram.defaults.process', loc)) return true
      continue
    }
    let m = /^flow-step-(\d+)$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.stepN', loc, { n: idx + 1 })) return true
      }
      continue
    }
    m = /^flow-substep-(\d+)-(\d+)$/.exec(nodeId)
    if (m) {
      const stepIdx = parseInt(m[1], 10)
      const subIdx = parseInt(m[2], 10)
      if (Number.isFinite(stepIdx) && Number.isFinite(subIdx) && stepIdx >= 0 && subIdx >= 0) {
        if (
          trimmed ===
          defaultsT('diagram.defaults.substepNM', loc, { n: stepIdx + 1, m: subIdx + 1 })
        ) {
          return true
        }
      }
    }
  }
  return false
}

export function isTreeMapDefaultNodeLabel(nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  for (const loc of UI_LOCALE_CODES) {
    if (nodeId === 'tree-topic') {
      if (trimmed === defaultsT('diagram.defaults.rootTopic', loc)) return true
      continue
    }
    if (nodeId === 'dimension-label') {
      continue
    }
    let m = /^tree-cat-(\d+)$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.categoryN', loc, { n: idx + 1 })) return true
      }
      continue
    }
    m = /^tree-leaf-(\d+)-(\d+)$/.exec(nodeId)
    if (m) {
      const catIdx = parseInt(m[1], 10)
      const leafIdx = parseInt(m[2], 10)
      if (Number.isFinite(catIdx) && Number.isFinite(leafIdx) && catIdx >= 0 && leafIdx >= 0) {
        if (
          trimmed ===
          defaultsT('diagram.defaults.itemNM', loc, { n: catIdx + 1, m: leafIdx + 1 })
        ) {
          return true
        }
      }
    }
  }
  return false
}

export function isBraceMapDefaultNodeLabel(nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  for (const loc of UI_LOCALE_CODES) {
    if (nodeId === 'brace-whole') {
      if (trimmed === defaultsT('diagram.defaults.topic', loc)) return true
      continue
    }
    if (nodeId === 'dimension-label') {
      continue
    }
    let m = /^brace-part-(\d+)$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.partN', loc, { n: idx + 1 })) return true
      }
      continue
    }
    m = /^brace-subpart-(\d+)-(\d+)$/.exec(nodeId)
    if (m) {
      const pi = parseInt(m[1], 10)
      const si = parseInt(m[2], 10)
      if (Number.isFinite(pi) && Number.isFinite(si) && pi >= 0 && si >= 0) {
        if (
          trimmed === defaultsT('diagram.defaults.subpartNM', loc, { n: pi + 1, m: si + 1 })
        ) {
          return true
        }
      }
    }
  }
  return false
}

export function isBridgeMapDefaultNodeLabel(nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  for (const loc of UI_LOCALE_CODES) {
    if (nodeId === 'dimension-label') {
      if (trimmed === defaultsT('diagram.labelNode.clickToSet', loc)) return true
      continue
    }
    let m = /^pair-(\d+)-left$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.bridgeItemAN', loc, { n: idx + 1 })) return true
      }
      continue
    }
    m = /^pair-(\d+)-right$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.bridgeItemBN', loc, { n: idx + 1 })) return true
      }
    }
  }
  return false
}

export function isMindmapDefaultNodeLabel(nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  for (const loc of UI_LOCALE_CODES) {
    if (nodeId === 'topic') {
      if (trimmed === defaultsT('diagram.defaults.centralTopic', loc)) return true
      continue
    }
    // Legacy IDs from old default templates: branch_N and sub_N_M
    let m = /^branch_(\d+)$/.exec(nodeId)
    if (m) {
      const idx = parseInt(m[1], 10)
      if (Number.isFinite(idx) && idx >= 0) {
        if (trimmed === defaultsT('diagram.defaults.branchN', loc, { n: idx + 1 })) return true
      }
      continue
    }
    m = /^sub_(\d+)_(\d+)$/.exec(nodeId)
    if (m) {
      const bi = parseInt(m[1], 10)
      const ci = parseInt(m[2], 10)
      if (Number.isFinite(bi) && Number.isFinite(ci) && bi >= 0 && ci >= 0) {
        if (
          trimmed === defaultsT('diagram.defaults.childNM', loc, { n: bi + 1, m: ci + 1 })
        ) {
          return true
        }
      }
      continue
    }
    // Current spec-loader IDs: branch-r-DEPTH-IDX or branch-l-DEPTH-IDX
    // The counter-based IDX does not encode the branch position directly, so we
    // check the text against all reasonable branchN / childNM combinations.
    if (/^branch-[rl]-\d+-\d+$/.test(nodeId)) {
      for (let n = 1; n <= 30; n++) {
        if (trimmed === defaultsT('diagram.defaults.branchN', loc, { n })) return true
      }
      for (let n = 1; n <= 20; n++) {
        for (let cm = 1; cm <= 20; cm++) {
          if (trimmed === defaultsT('diagram.defaults.childNM', loc, { n, m: cm })) return true
        }
      }
    }
  }
  return false
}

function conceptT(key: string, lang: LocaleCode): string {
  return String(i18n.global.t(key, {}, { locale: lang }))
}

export function getConceptMapFocusQuestionPrefix(lang: LocaleCode): string {
  return conceptT('diagram.conceptMap.focusQuestionPrefix', lang)
}

export function getConceptMapFocusQuestionSuffix(lang: LocaleCode): string {
  return conceptT('diagram.conceptMap.focusQuestionSuffix', lang)
}

export function getConceptMapFocusQuestionDefault(lang: LocaleCode): string {
  return getConceptMapFocusQuestionPrefix(lang) + getConceptMapFocusQuestionSuffix(lang)
}

export function getConceptMapRootConceptText(lang: LocaleCode): string {
  return conceptT('diagram.conceptMap.rootConcept', lang)
}

/** Edge label for topic → default root concept (mirrors 的根概念). */
export function getConceptMapTopicRootRelationshipLabel(lang: LocaleCode): string {
  return conceptT('diagram.conceptMap.topicRootRelationship', lang)
}

/** Known labels for the topic → root edge (saved diagrams may use any UI locale). */
export const ALL_TOPIC_ROOT_RELATIONSHIP_LABELS: readonly string[] = UI_LOCALE_CODES.map((l) =>
  getConceptMapTopicRootRelationshipLabel(l)
)

/** Known default root concept node texts. */
export const ALL_ROOT_CONCEPT_NODE_TEXTS: readonly string[] = UI_LOCALE_CODES.map((l) =>
  getConceptMapRootConceptText(l)
)

/** Default focus question topic strings (for muted styling). */
export const ALL_FOCUS_QUESTION_DEFAULTS: readonly string[] = UI_LOCALE_CODES.map((l) =>
  getConceptMapFocusQuestionDefault(l)
)

export function stripConceptMapFocusQuestionPrefix(raw: string): string {
  const trimmed = raw.trim()
  for (const loc of UI_LOCALE_CODES) {
    const prefix = getConceptMapFocusQuestionPrefix(loc)
    if (trimmed.startsWith(prefix)) {
      return trimmed.slice(prefix.length).trim()
    }
  }
  return trimmed
}

export function isDefaultFocusQuestionLabel(label: string): boolean {
  return ALL_FOCUS_QUESTION_DEFAULTS.includes(label.trim())
}

export function focusQuestionMutedParts(label: string): { prefix: string; suffix: string } | null {
  const t = label.trim()
  for (const loc of UI_LOCALE_CODES) {
    const def = getConceptMapFocusQuestionDefault(loc)
    if (t === def) {
      return {
        prefix: getConceptMapFocusQuestionPrefix(loc),
        suffix: getConceptMapFocusQuestionSuffix(loc),
      }
    }
  }
  return null
}

/**
 * When Insert equation runs on a node that still shows the blank-template label (any locale),
 * replace the whole label with the math snippet instead of appending after "Topic" / step name, etc.
 */
export function shouldReplaceLabelWithMathInsert(
  diagramType: DiagramType | null | undefined,
  nodeId: string,
  text: string
): boolean {
  if (!diagramType) return false
  const trimmed = text.trim()
  if (!trimmed) return true
  const normalized: DiagramType = diagramType === 'mind_map' ? 'mindmap' : diagramType
  switch (normalized) {
    case 'circle_map':
      return isCircleMapDefaultNodeLabel(nodeId, text)
    case 'bubble_map':
      return isBubbleMapDefaultNodeLabel(nodeId, text)
    case 'double_bubble_map':
      return isDoubleBubbleDefaultNodeLabel(nodeId, text)
    case 'multi_flow_map':
      return isMultiFlowDefaultNodeLabel(nodeId, text)
    case 'flow_map':
      return isFlowMapDefaultNodeLabel(nodeId, text)
    case 'tree_map':
      return isTreeMapDefaultNodeLabel(nodeId, text)
    case 'brace_map':
      return isBraceMapDefaultNodeLabel(nodeId, text)
    case 'bridge_map':
      return isBridgeMapDefaultNodeLabel(nodeId, text)
    case 'mindmap':
      return isMindmapDefaultNodeLabel(nodeId, text)
    case 'concept_map':
      if (nodeId === 'topic') return isDefaultFocusQuestionLabel(text)
      if (nodeId.startsWith('concept-')) {
        return ALL_ROOT_CONCEPT_NODE_TEXTS.includes(trimmed)
      }
      return false
    default:
      return false
  }
}
