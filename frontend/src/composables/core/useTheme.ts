/**
 * useTheme - Composable for diagram theme management
 * Migrated from archive/static/js/style-manager.js
 * Provides centralized theme handling matching the old JavaScript implementation
 */
import { type Ref, computed } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { MIND_MAP_RAINBOW_TOPIC_COLORS } from '@/config/mindMapVibrantThemes'
import type { DiagramType, NodeStyle } from '@/types'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import { THINKING_MAP_LEAF_TEXT } from '@/utils/thinkingMapChrome'

// Default themes matching the old StyleManager
const LEGACY_MINDMAP_THEME = {
  background: '#f5f5f5',
  centralTopicFill: '#1976d2',
  centralTopicText: '#ffffff',
  centralTopicStroke: '#000000',
  centralTopicStrokeWidth: 3,
  branchFill: '#e3f2fd',
  branchText: '#333333',
  branchStroke: '#4e79a7',
  branchStrokeWidth: 2,
  childFill: '#bbdefb',
  childText: '#333333',
  childStroke: '#90caf9',
  childStrokeWidth: 1,
  fontTopic: 18,
  fontBranch: 16,
  fontChild: 12,
  linkStroke: '#4e79a7',
  linkStrokeWidth: 2,
}

const V2_MINDMAP_THEME = {
  background: '#f5f5f5',
  centralTopicFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
  centralTopicText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
  centralTopicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
  centralTopicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
  branchFill: '#eff6ff',
  branchText: '#1e40af',
  branchStroke: '#93c5fd',
  branchStrokeWidth: 1.5,
  childFill: '#ffffff',
  childText: '#334155',
  childStroke: '#CBD5E1',
  childStrokeWidth: 1.5,
  fontTopic: 18,
  fontBranch: 16,
  fontChild: 14,
  linkStroke: '#64748b',
  linkStrokeWidth: 2,
}

const DEFAULT_THEMES: Partial<Record<DiagramType, DiagramTheme>> = {
  bubble_map: {
    background: '#f5f5f5',
    topicFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    topicText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    topicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    topicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    attributeFill: '#EBF3FE',
    attributeText: '#175CD3',
    attributeStroke: '#2E90FA',
    attributeStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    fontTopic: MIND_MAP_GEOMETRY.topicFontSize,
    fontAttribute: MIND_MAP_GEOMETRY.branchFontSize,
  },
  double_bubble_map: {
    background: '#f5f5f5',
    centralTopicFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    centralTopicText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    centralTopicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    centralTopicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    leftTopicFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    leftTopicText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    leftTopicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    leftTopicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    rightTopicFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    rightTopicText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    rightTopicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    rightTopicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    attributeFill: '#FFFFFF',
    attributeText: THINKING_MAP_LEAF_TEXT,
    attributeStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    attributeStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    fontCentralTopic: MIND_MAP_GEOMETRY.topicFontSize,
    fontTopic: MIND_MAP_GEOMETRY.branchFontSize,
    fontAttribute: MIND_MAP_GEOMETRY.branchFontSize,
  },
  mindmap: LEGACY_MINDMAP_THEME,
  mind_map: LEGACY_MINDMAP_THEME,
  concept_map: {
    background: '#f5f5f5',
    topicFill: '#e3f2fd',
    topicText: '#000000',
    topicStroke: '#35506b',
    topicStrokeWidth: 3,
    conceptFill: '#e3f2fd',
    conceptText: '#333333',
    conceptStroke: '#4e79a7',
    conceptStrokeWidth: 2,
    relationshipColor: '#666666',
    relationshipStrokeWidth: 2,
    fontTopic: 18,
    fontConcept: 14,
  },
  brace_map: {
    background: '#f5f5f5',
    topicFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    topicText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    topicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    topicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    partFill: '#EBF3FE',
    partText: '#175CD3',
    partStroke: '#2E90FA',
    partStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    subpartFill: '#FFFFFF',
    subpartText: '#175CD3',
    subpartStroke: '#2E90FA',
    subpartStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    braceColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    dimensionLabelColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    fontTopic: MIND_MAP_GEOMETRY.topicFontSize,
    fontPart: MIND_MAP_GEOMETRY.branchFontSize,
    fontSubpart: MIND_MAP_GEOMETRY.fontSize,
  },
  tree_map: {
    background: '#f5f5f5',
    rootFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    rootText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    rootStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    rootStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    topicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    topicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    branchFill: '#EBF3FE',
    branchText: '#175CD3',
    branchStroke: '#2E90FA',
    branchStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    leafFill: '#FFFFFF',
    leafText: '#175CD3',
    leafStroke: '#2E90FA',
    leafStrokeWidth: 0,
    dimensionLabelColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    fontRoot: MIND_MAP_GEOMETRY.topicFontSize,
    fontBranch: MIND_MAP_GEOMETRY.branchFontSize,
    fontLeaf: MIND_MAP_GEOMETRY.fontSize,
  },
  flow_map: {
    background: '#f5f5f5',
    topicFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    topicText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    topicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    topicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    stepFill: '#EBF3FE',
    stepText: '#175CD3',
    stepStroke: '#2E90FA',
    stepStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    fontTopic: MIND_MAP_GEOMETRY.topicFontSize,
    fontStep: MIND_MAP_GEOMETRY.branchFontSize,
  },
  bridge_map: {
    background: '#f5f5f5',
    bridgeLineColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    analogyTextColor: THINKING_MAP_LEAF_TEXT,
    analogyFontSize: MIND_MAP_GEOMETRY.fontSize,
    dimensionLabelColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    firstPairFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    firstPairText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    firstPairStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    firstPairStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
  },
  multi_flow_map: {
    background: '#f5f5f5',
    topicFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    topicText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    topicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    topicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    stepFill: '#EBF3FE',
    stepText: '#175CD3',
    stepStroke: '#2E90FA',
    stepStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    fontTopic: MIND_MAP_GEOMETRY.topicFontSize,
    fontStep: MIND_MAP_GEOMETRY.branchFontSize,
  },
  circle_map: {
    background: '#f5f5f5',
    topicFill: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    topicText: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    topicStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    topicStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    contextFill: '#EBF3FE',
    contextText: '#175CD3',
    contextStroke: '#2E90FA',
    contextStrokeWidth: MIND_MAP_GEOMETRY.borderWidth,
    boundaryStroke: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    boundaryStrokeWidth: MIND_MAP_GEOMETRY.edgeStrokeWidth,
    fontTopic: MIND_MAP_GEOMETRY.topicFontSize,
    fontContext: MIND_MAP_GEOMETRY.branchFontSize,
  },
}

export interface DiagramTheme {
  background?: string
  // Topic/Central node styles
  topicFill?: string
  topicText?: string
  topicStroke?: string
  topicStrokeWidth?: number
  centralTopicFill?: string
  centralTopicText?: string
  centralTopicStroke?: string
  centralTopicStrokeWidth?: number
  // Branch/Child node styles
  branchFill?: string
  branchText?: string
  branchStroke?: string
  branchStrokeWidth?: number
  childFill?: string
  childText?: string
  childStroke?: string
  childStrokeWidth?: number
  // Attribute/Bubble node styles
  attributeFill?: string
  attributeText?: string
  attributeStroke?: string
  attributeStrokeWidth?: number
  // Part/Subpart styles (brace maps)
  partFill?: string
  partText?: string
  partStroke?: string
  partStrokeWidth?: number
  subpartFill?: string
  subpartText?: string
  subpartStroke?: string
  subpartStrokeWidth?: number
  // Root/Leaf styles (tree maps)
  rootFill?: string
  rootText?: string
  rootStroke?: string
  rootStrokeWidth?: number
  leafFill?: string
  leafText?: string
  leafStroke?: string
  leafStrokeWidth?: number
  // Flow map styles
  stepFill?: string
  stepText?: string
  stepStroke?: string
  stepStrokeWidth?: number
  // Bridge map styles
  firstPairFill?: string
  firstPairText?: string
  firstPairStroke?: string
  firstPairStrokeWidth?: number
  bridgeLineColor?: string
  analogyTextColor?: string
  analogyFontSize?: number
  // Context styles (circle maps)
  contextFill?: string
  contextText?: string
  contextStroke?: string
  contextStrokeWidth?: number
  // Boundary styles (circle map outer ring)
  boundaryStroke?: string
  boundaryStrokeWidth?: number
  // Left/Right topic styles (double bubble maps)
  leftTopicFill?: string
  leftTopicText?: string
  leftTopicStroke?: string
  leftTopicStrokeWidth?: number
  rightTopicFill?: string
  rightTopicText?: string
  rightTopicStroke?: string
  rightTopicStrokeWidth?: number
  // Concept map styles
  conceptFill?: string
  conceptText?: string
  conceptStroke?: string
  conceptStrokeWidth?: number
  // Font sizes
  fontTopic?: number
  fontAttribute?: number
  fontBranch?: number
  fontChild?: number
  fontPart?: number
  fontSubpart?: number
  fontRoot?: number
  fontLeaf?: number
  fontStep?: number
  fontCentralTopic?: number
  fontConcept?: number
  fontContext?: number
  // Link/Edge styles
  linkStroke?: string
  linkStrokeWidth?: number
  relationshipColor?: string
  relationshipStrokeWidth?: number
  braceColor?: string
  dimensionLabelColor?: string
}

export interface UseThemeOptions {
  diagramType?: DiagramType | Ref<DiagramType | null>
  userTheme?: Partial<DiagramTheme>
  backendTheme?: Partial<DiagramTheme>
}

/**
 * Get theme for a diagram type
 */
export function useTheme(options: UseThemeOptions = {}) {
  const diagramStore = useDiagramSession()

  const diagramType = computed(() => {
    const type = options.diagramType
    return type && typeof type === 'object' && 'value' in type ? type.value : type
  })

  const theme = computed<DiagramTheme>(() => {
    const type = diagramType.value
    if (!type) return {}

    // Start with default theme
    let defaultTheme = DEFAULT_THEMES[type] || {}
    if (
      (type === 'mindmap' || type === 'mind_map') &&
      isSessionMindMapV2VisualDesignActive(diagramStore.mindMapCanvasMode)
    ) {
      defaultTheme = V2_MINDMAP_THEME
    }

    // Merge backend theme if provided
    let merged = { ...defaultTheme }
    if (options.backendTheme) {
      merged = { ...merged, ...options.backendTheme }
    }

    // Merge user theme if provided
    if (options.userTheme) {
      merged = { ...merged, ...options.userTheme }
    }

    return merged
  })

  /**
   * Get NodeStyle for a specific node type
   */
  function getNodeStyle(
    nodeType:
      | 'topic'
      | 'branch'
      | 'child'
      | 'bubble'
      | 'attribute'
      | 'part'
      | 'subpart'
      | 'root'
      | 'leaf'
      | 'step'
      | 'context'
      | 'boundary'
  ): NodeStyle {
    const t = theme.value

    switch (nodeType) {
      case 'topic':
        return {
          backgroundColor: t.topicFill || t.centralTopicFill || '#1976d2',
          textColor: t.topicText || t.centralTopicText || '#ffffff',
          borderColor: t.topicStroke || t.centralTopicStroke || '#0d47a1',
          borderWidth: t.topicStrokeWidth || t.centralTopicStrokeWidth || 3,
          fontSize: t.fontTopic || t.fontCentralTopic || 18,
          fontWeight: 'bold',
        }

      case 'branch':
        return {
          backgroundColor: t.branchFill || '#e3f2fd',
          textColor: t.branchText || '#333333',
          borderColor: t.branchStroke || '#4e79a7',
          borderWidth: t.branchStrokeWidth || 2,
          fontSize: t.fontBranch || 16,
          fontWeight: 'normal',
        }

      case 'child':
        return {
          backgroundColor: t.childFill || '#bbdefb',
          textColor: t.childText || '#333333',
          borderColor: t.childStroke || '#90caf9',
          borderWidth: t.childStrokeWidth || 1,
          fontSize: t.fontChild || 12,
          fontWeight: 'normal',
        }

      case 'bubble':
      case 'attribute':
        return {
          backgroundColor: t.attributeFill || '#e3f2fd',
          textColor: t.attributeText || '#333333',
          borderColor: t.attributeStroke || '#000000',
          borderWidth: t.attributeStrokeWidth || 2,
          fontSize: t.fontAttribute || 14,
          fontWeight: 'normal',
        }

      case 'part':
        return {
          backgroundColor: t.partFill || '#e3f2fd',
          textColor: t.partText || '#333333',
          borderColor: t.partStroke || '#4e79a7',
          borderWidth: t.partStrokeWidth || 2,
          fontSize: t.fontPart || 16,
          fontWeight: 'normal',
        }

      case 'subpart':
        return {
          backgroundColor: t.subpartFill || '#bbdefb',
          textColor: t.subpartText || '#333333',
          borderColor: t.subpartStroke || '#90caf9',
          borderWidth: t.subpartStrokeWidth || 1,
          fontSize: t.fontSubpart || 12,
          fontWeight: 'normal',
        }

      case 'root':
        return {
          backgroundColor: t.rootFill || '#1976d2',
          textColor: t.rootText || '#ffffff',
          borderColor: t.rootStroke || '#0d47a1',
          borderWidth: t.rootStrokeWidth || 2,
          fontSize: t.fontRoot || 20,
          fontWeight: 'bold',
        }

      case 'leaf':
        return {
          backgroundColor: t.leafFill || '#ffffff',
          textColor: t.leafText || '#333333',
          borderColor: t.leafStroke || '#c8d6e5',
          borderWidth: t.leafStrokeWidth || 1,
          fontSize: t.fontLeaf || 14,
          fontWeight: 'normal',
        }

      case 'step':
        return {
          backgroundColor: t.stepFill || '#ffffff',
          textColor: t.stepText || '#303133',
          borderColor: t.stepStroke || '#409eff',
          borderWidth: t.stepStrokeWidth || 2,
          fontSize: t.fontStep || 13,
          fontWeight: 'normal',
        }

      case 'context':
        return {
          backgroundColor: t.contextFill || '#e3f2fd',
          textColor: t.contextText || '#333333',
          borderColor: t.contextStroke || '#1976d2', // Blue, matching old JS
          borderWidth: t.contextStrokeWidth || 2,
          fontSize: t.fontContext || 14,
          fontWeight: 'normal',
        }

      case 'boundary':
        return {
          backgroundColor: 'transparent',
          textColor: 'transparent',
          borderColor: t.boundaryStroke || '#666666',
          borderWidth: t.boundaryStrokeWidth || 2,
          fontSize: 0,
          fontWeight: 'normal',
        }

      default:
        return {
          backgroundColor: '#ffffff',
          textColor: '#333333',
          borderColor: '#000000',
          borderWidth: 2,
          fontSize: 14,
          fontWeight: 'normal',
        }
    }
  }

  /**
   * Get background color for the diagram
   */
  const backgroundColor = computed(() => theme.value.background || '#f5f5f5')

  return {
    theme,
    backgroundColor,
    getNodeStyle,
  }
}
