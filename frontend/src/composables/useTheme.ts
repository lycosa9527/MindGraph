/**
 * useTheme - Composable for diagram theme management
 * Migrated from archive/static/js/style-manager.js
 * Provides centralized theme handling matching the old JavaScript implementation
 */
import { type Ref, computed } from 'vue'

import type { DiagramType, NodeStyle } from '@/types'

// Default themes matching the old StyleManager
const DEFAULT_THEMES: Partial<Record<DiagramType, DiagramTheme>> = {
  bubble_map: {
    background: '#f5f5f5',
    topicFill: '#1976d2',
    topicText: '#ffffff',
    topicStroke: '#000000',
    topicStrokeWidth: 2,
    attributeFill: '#e3f2fd',
    attributeText: '#333333',
    attributeStroke: '#000000',
    attributeStrokeWidth: 2,
    fontTopic: 20,
    fontAttribute: 14,
  },
  double_bubble_map: {
    background: '#f5f5f5',
    centralTopicFill: '#1976d2',
    centralTopicText: '#ffffff',
    centralTopicStroke: '#000000',
    centralTopicStrokeWidth: 3,
    leftTopicFill: '#1976d2',
    leftTopicText: '#ffffff',
    leftTopicStroke: '#000000',
    leftTopicStrokeWidth: 2,
    rightTopicFill: '#1976d2',
    rightTopicText: '#ffffff',
    rightTopicStroke: '#000000',
    rightTopicStrokeWidth: 2,
    attributeFill: '#e3f2fd',
    attributeText: '#333333',
    attributeStroke: '#000000',
    attributeStrokeWidth: 2,
    fontCentralTopic: 18,
    fontTopic: 16,
    fontAttribute: 12,
  },
  mindmap: {
    background: '#f5f5f5',
    centralTopicFill: '#1976d2',
    centralTopicText: '#ffffff',
    centralTopicStroke: '#0d47a1',
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
  },
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
    topicFill: '#1976d2',
    topicText: '#ffffff',
    topicStroke: '#0d47a1',
    topicStrokeWidth: 3,
    partFill: '#e3f2fd',
    partText: '#333333',
    partStroke: '#4e79a7',
    partStrokeWidth: 2,
    subpartFill: '#bbdefb',
    subpartText: '#333333',
    subpartStroke: '#90caf9',
    subpartStrokeWidth: 1,
    braceColor: '#666666',
    dimensionLabelColor: '#1976d2',
    fontTopic: 18,
    fontPart: 16,
    fontSubpart: 12,
  },
  tree_map: {
    background: '#f5f5f5',
    rootFill: '#1976d2',
    rootText: '#ffffff',
    rootStroke: '#0d47a1',
    rootStrokeWidth: 2,
    branchFill: '#e3f2fd',
    branchText: '#333333',
    branchStroke: '#1976d2',
    branchStrokeWidth: 1.5,
    leafFill: '#ffffff',
    leafText: '#333333',
    leafStroke: '#c8d6e5',
    leafStrokeWidth: 1,
    dimensionLabelColor: '#1976d2',
    fontRoot: 20,
    fontBranch: 16,
    fontLeaf: 14,
  },
  flow_map: {
    background: '#f5f5f5',
    stepFill: '#ffffff',
    stepText: '#303133',
    stepStroke: '#409eff',
    stepStrokeWidth: 2,
    fontStep: 13,
  },
  bridge_map: {
    background: '#f5f5f5',
    bridgeLineColor: '#666666',
    analogyTextColor: '#333333',
    analogyFontSize: 14,
    dimensionLabelColor: '#1976d2',
    firstPairFill: '#1976d2',
    firstPairText: '#ffffff',
    firstPairStroke: '#0d47a1',
    firstPairStrokeWidth: 2,
  },
  multi_flow_map: {
    background: '#f5f5f5',
    stepFill: '#ffffff',
    stepText: '#303133',
    stepStroke: '#409eff',
    stepStrokeWidth: 2,
    fontStep: 13,
  },
  // Circle Map colors matching old JS bubble-map-renderer.js THEME
  circle_map: {
    background: '#f5f5f5',
    topicFill: '#1976d2', // Blue
    topicText: '#ffffff', // White
    topicStroke: '#0d47a1', // Dark blue
    topicStrokeWidth: 3,
    contextFill: '#e3f2fd', // Light blue
    contextText: '#333333', // Dark gray
    contextStroke: '#1976d2', // Blue
    contextStrokeWidth: 2,
    boundaryStroke: '#666666', // Gray
    boundaryStrokeWidth: 2,
    fontTopic: 20,
    fontContext: 14,
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
  const diagramType = computed(() => {
    const type = options.diagramType
    return type && typeof type === 'object' && 'value' in type ? type.value : type
  })

  const theme = computed<DiagramTheme>(() => {
    const type = diagramType.value
    if (!type) return {}

    // Start with default theme
    const defaultTheme = DEFAULT_THEMES[type] || {}

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
