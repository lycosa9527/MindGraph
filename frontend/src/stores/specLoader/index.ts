/**
 * Spec Loader - Main entry point
 * Converts API spec format to DiagramData
 * Each diagram type has its own converter function
 *
 * This separates the spec-to-data conversion logic from the store,
 * making it easier to maintain and test each diagram type independently.
 */
import type { DiagramType } from '@/types'

import { loadBraceMapSpec } from './braceMap'
import { loadBridgeMapSpec } from './bridgeMap'
import { loadBubbleMapSpec, recalculateBubbleMapLayout } from './bubbleMap'
import { loadCircleMapSpec } from './circleMap'
import { loadDoubleBubbleMapSpec } from './doubleBubbleMap'
import { loadFlowMapSpec } from './flowMap'
import { loadGenericSpec } from './generic'
import { loadMindMapSpec } from './mindMap'
import { loadMultiFlowMapSpec, recalculateMultiFlowMapLayout } from './multiFlowMap'
import { loadTreeMapSpec } from './treeMap'
import type { SpecLoaderResult } from './types'

// Re-export public APIs
export { recalculateCircleMapLayout } from './circleMap'
export { recalculateBubbleMapLayout } from './bubbleMap'
export { recalculateMultiFlowMapLayout } from './multiFlowMap'
export type { SpecLoaderResult } from './types'

/**
 * Load diagram data from API spec
 * @param spec - The API spec object
 * @param diagramType - The type of diagram
 * @returns SpecLoaderResult with nodes, connections, and optional metadata
 *
 * Note: Saved diagrams use a generic format with { nodes, connections },
 * while LLM-generated specs use type-specific formats (e.g., { topic, attributes }).
 * We detect saved diagrams by checking for the 'nodes' array and use loadGenericSpec.
 */
export function loadSpecForDiagramType(
  spec: Record<string, unknown>,
  diagramType: DiagramType
): SpecLoaderResult {
  // Check if this is a saved diagram (has nodes array)
  // Saved diagrams use generic format: { nodes: [...], connections: [...] }
  // LLM-generated specs use type-specific format: { topic, attributes, ... }
  if (Array.isArray(spec.nodes) && spec.nodes.length > 0) {
    return loadGenericSpec(spec)
  }

  // Use type-specific loader for LLM-generated specs
  const loader = SPEC_LOADERS[diagramType]
  if (loader) {
    return loader(spec)
  }
  return loadGenericSpec(spec)
}

// ============================================================================
// Loader Registry
// ============================================================================
const SPEC_LOADERS: Partial<
  Record<DiagramType, (spec: Record<string, unknown>) => SpecLoaderResult>
> = {
  circle_map: loadCircleMapSpec,
  bubble_map: loadBubbleMapSpec,
  double_bubble_map: loadDoubleBubbleMapSpec,
  tree_map: loadTreeMapSpec,
  flow_map: loadFlowMapSpec,
  multi_flow_map: loadMultiFlowMapSpec,
  brace_map: loadBraceMapSpec,
  bridge_map: loadBridgeMapSpec,
  // concept_map: handled by teammate
  mindmap: loadMindMapSpec,
  mind_map: loadMindMapSpec,
}

// ============================================================================
// Default Templates
// Static templates with placeholder text for each diagram type
// Used when user clicks "新建" to create a blank canvas
// ============================================================================

// Default templates matching the old JS diagram-selector.js templates
const DEFAULT_TEMPLATES: Record<string, Record<string, unknown>> = {
  circle_map: {
    topic: '主题',
    context: ['联想1', '联想2', '联想3', '联想4', '联想5', '联想6', '联想7', '联想8'],
  },
  bubble_map: {
    topic: '主题',
    attributes: ['属性1', '属性2', '属性3', '属性4', '属性5'],
  },
  double_bubble_map: {
    left: '主题A',
    right: '主题B',
    similarities: ['相似点1', '相似点2'],
    left_differences: ['不同点A1', '不同点A2', '不同点A3'],
    right_differences: ['不同点B1', '不同点B2', '不同点B3'],
  },
  tree_map: {
    topic: '根主题',
    dimension: '',
    alternative_dimensions: [],
    children: [
      {
        text: '类别1',
        children: [
          { text: '项目1.1', children: [] },
          { text: '项目1.2', children: [] },
          { text: '项目1.3', children: [] },
        ],
      },
      {
        text: '类别2',
        children: [
          { text: '项目2.1', children: [] },
          { text: '项目2.2', children: [] },
          { text: '项目2.3', children: [] },
        ],
      },
      {
        text: '类别3',
        children: [
          { text: '项目3.1', children: [] },
          { text: '项目3.2', children: [] },
          { text: '项目3.3', children: [] },
        ],
      },
      {
        text: '类别4',
        children: [
          { text: '项目4.1', children: [] },
          { text: '项目4.2', children: [] },
          { text: '项目4.3', children: [] },
        ],
      },
    ],
  },
  brace_map: {
    whole: '主题',
    dimension: '',
    parts: [
      { name: '部分1', subparts: [{ name: '子部分1.1' }, { name: '子部分1.2' }] },
      { name: '部分2', subparts: [{ name: '子部分2.1' }, { name: '子部分2.2' }] },
      { name: '部分3', subparts: [{ name: '子部分3.1' }, { name: '子部分3.2' }] },
    ],
  },
  flow_map: {
    title: '事件流程',
    steps: ['步骤1', '步骤2', '步骤3', '步骤4'],
    substeps: [
      { step: '步骤1', substeps: ['子步骤1.1', '子步骤1.2'] },
      { step: '步骤2', substeps: ['子步骤2.1', '子步骤2.2'] },
      { step: '步骤3', substeps: ['子步骤3.1', '子步骤3.2'] },
      { step: '步骤4', substeps: ['子步骤4.1', '子步骤4.2'] },
    ],
  },
  multi_flow_map: {
    event: '事件',
    causes: ['原因1', '原因2', '原因3', '原因4'],
    effects: ['结果1', '结果2', '结果3', '结果4'],
  },
  bridge_map: {
    relating_factor: '[点击设置]',
    dimension: '',
    analogies: [
      { left: '事物A1', right: '事物B1' },
      { left: '事物A2', right: '事物B2' },
      { left: '事物A3', right: '事物B3' },
      { left: '事物A4', right: '事物B4' },
      { left: '事物A5', right: '事物B5' },
    ],
    alternative_dimensions: [],
  },
  mindmap: {
    topic: '中心主题',
    children: [
      {
        id: 'branch_0',
        label: '分支1',
        text: '分支1',
        children: [
          { id: 'sub_0_0', label: '子项1.1', text: '子项1.1', children: [] },
          { id: 'sub_0_1', label: '子项1.2', text: '子项1.2', children: [] },
        ],
      },
      {
        id: 'branch_1',
        label: '分支2',
        text: '分支2',
        children: [
          { id: 'sub_1_0', label: '子项2.1', text: '子项2.1', children: [] },
          { id: 'sub_1_1', label: '子项2.2', text: '子项2.2', children: [] },
        ],
      },
      {
        id: 'branch_2',
        label: '分支3',
        text: '分支3',
        children: [
          { id: 'sub_2_0', label: '子项3.1', text: '子项3.1', children: [] },
          { id: 'sub_2_1', label: '子项3.2', text: '子项3.2', children: [] },
        ],
      },
      {
        id: 'branch_3',
        label: '分支4',
        text: '分支4',
        children: [
          { id: 'sub_3_0', label: '子项4.1', text: '子项4.1', children: [] },
          { id: 'sub_3_1', label: '子项4.2', text: '子项4.2', children: [] },
        ],
      },
    ],
  },
  concept_map: {
    topic: '主要概念',
    concepts: ['概念1', '概念2', '概念3'],
    relationships: [
      { from: '主要概念', to: '概念1', label: '关联' },
      { from: '主要概念', to: '概念2', label: '包含' },
      { from: '概念1', to: '概念3', label: '导致' },
    ],
  },
}

/**
 * Get default template spec for a diagram type
 * Returns a static template with placeholder text
 *
 * @param diagramType - The type of diagram
 * @returns Template spec or null if not found
 */
export function getDefaultTemplate(diagramType: DiagramType): Record<string, unknown> | null {
  return DEFAULT_TEMPLATES[diagramType] || null
}
