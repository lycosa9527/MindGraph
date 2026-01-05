/**
 * useDiagramOperations - Composable for diagram-specific operations
 *
 * Dynamically provides add/delete/update operations based on diagram type.
 * Each diagram type has specific rules for node manipulation.
 *
 * Migrated from archive/static/js/managers/editor/diagram-operations-loader.js
 */
import { computed, onUnmounted, ref, shallowRef, watch } from 'vue'

import type { DiagramSpec, DiagramType } from '@/types'

import { eventBus } from './useEventBus'

// ============================================================================
// Types
// ============================================================================

export interface NodePosition {
  x: number
  y: number
}

export interface NodeStyles {
  fill?: string
  stroke?: string
  strokeWidth?: number
  fontSize?: number
  textColor?: string
  fontFamily?: string
  fontWeight?: string
}

export interface NodeUpdate {
  text?: string
  label?: string
  styles?: NodeStyles
}

export interface AddNodeResult {
  nodeId: string
  nodeType: string
  index?: number
}

export interface DeleteNodeResult {
  deletedIds: string[]
  deletedIndices: number[]
  warnings: string[]
}

export interface DiagramOperations {
  addNode: (spec: DiagramSpec, nodeType?: string) => AddNodeResult | null
  deleteNodes: (spec: DiagramSpec, nodeIds: string[]) => DeleteNodeResult | null
  updateNode: (spec: DiagramSpec, nodeId: string, updates: NodeUpdate) => boolean
  savePosition: (spec: DiagramSpec, nodeId: string, position: NodePosition) => boolean
  saveStyles: (spec: DiagramSpec, nodeId: string, styles: NodeStyles) => boolean
  clearPositions: (spec: DiagramSpec) => boolean
  validateSpec: (spec: DiagramSpec) => boolean
  getNodeTypes: () => string[]
  canAddNode: (nodeType?: string) => boolean
  canDeleteNode: (nodeId: string, nodeType: string) => boolean
}

export interface UseDiagramOperationsOptions {
  ownerId?: string
  language?: string
}

// ============================================================================
// Diagram Type Configuration
// ============================================================================

interface DiagramConfig {
  nodeTypes: string[]
  arrayFields: Record<string, string>
  protectedNodes: string[]
  maxNodes?: Record<string, number>
  defaultTexts: Record<string, { en: string | string[]; zh: string | string[] }>
}

const DIAGRAM_CONFIGS: Record<string, DiagramConfig> = {
  circle_map: {
    nodeTypes: ['topic', 'context'],
    arrayFields: { context: 'context' },
    protectedNodes: ['topic'],
    defaultTexts: {
      context: { en: 'New Context', zh: '新联想' },
    },
  },
  bubble_map: {
    nodeTypes: ['topic', 'attribute'],
    arrayFields: { attribute: 'attributes' },
    protectedNodes: ['topic'],
    defaultTexts: {
      attribute: { en: 'New Attribute', zh: '新属性' },
    },
  },
  double_bubble_map: {
    nodeTypes: ['topic1', 'topic2', 'shared', 'unique1', 'unique2'],
    arrayFields: {
      shared: 'shared',
      unique1: 'unique1',
      unique2: 'unique2',
    },
    protectedNodes: ['topic1', 'topic2'],
    defaultTexts: {
      shared: { en: 'New Shared', zh: '新共同点' },
      unique1: { en: 'New Unique', zh: '新独特点' },
      unique2: { en: 'New Unique', zh: '新独特点' },
    },
  },
  brace_map: {
    nodeTypes: ['whole', 'part', 'subpart'],
    arrayFields: { part: 'parts' },
    protectedNodes: ['whole'],
    defaultTexts: {
      part: { en: 'New Part', zh: '新部分' },
      subpart: { en: 'New Subpart', zh: '新子部分' },
    },
  },
  bridge_map: {
    nodeTypes: ['relation', 'pair'],
    arrayFields: { pair: 'pairs' },
    protectedNodes: [],
    defaultTexts: {
      pair: { en: ['Top', 'Bottom'], zh: ['上方', '下方'] },
    },
  },
  tree_map: {
    nodeTypes: ['main', 'category', 'item'],
    arrayFields: { category: 'categories' },
    protectedNodes: ['main'],
    defaultTexts: {
      category: { en: 'New Category', zh: '新类别' },
      item: { en: 'New Item', zh: '新项目' },
    },
  },
  flow_map: {
    nodeTypes: ['title', 'step'],
    arrayFields: { step: 'steps' },
    protectedNodes: [],
    defaultTexts: {
      step: { en: 'New Step', zh: '新步骤' },
    },
  },
  multi_flow_map: {
    nodeTypes: ['event', 'cause', 'effect'],
    arrayFields: { cause: 'causes', effect: 'effects' },
    protectedNodes: ['event'],
    defaultTexts: {
      cause: { en: 'New Cause', zh: '新原因' },
      effect: { en: 'New Effect', zh: '新结果' },
    },
  },
  concept_map: {
    nodeTypes: ['concept', 'link'],
    arrayFields: { concept: 'nodes' },
    protectedNodes: [],
    defaultTexts: {
      concept: { en: 'New Concept', zh: '新概念' },
    },
  },
  mindmap: {
    nodeTypes: ['topic', 'branch', 'child'],
    arrayFields: { branch: 'branches' },
    protectedNodes: ['topic'],
    defaultTexts: {
      branch: { en: 'New Branch', zh: '新分支' },
      child: { en: 'New Child', zh: '新子节点' },
    },
  },
}

// Aliases for shared operation logic
const DIAGRAM_ALIASES: Record<string, string> = {
  factor_analysis: 'mindmap',
  four_quadrant: 'mindmap',
}

// ============================================================================
// Composable
// ============================================================================

export function useDiagramOperations(options: UseDiagramOperationsOptions = {}) {
  const { ownerId = `DiagramOps_${Date.now()}`, language = 'en' } = options

  // Current diagram type
  const diagramType = ref<DiagramType | null>(null)
  const currentLang = ref(language)

  // Current operations (computed based on diagram type)
  const operations = shallowRef<DiagramOperations | null>(null)

  // Get effective diagram type (resolve aliases)
  const effectiveType = computed(() => {
    if (!diagramType.value) return null
    return DIAGRAM_ALIASES[diagramType.value] || diagramType.value
  })

  // Get config for current diagram type
  const config = computed<DiagramConfig | null>(() => {
    if (!effectiveType.value) return null
    return DIAGRAM_CONFIGS[effectiveType.value] || null
  })

  // =========================================================================
  // Helper Functions
  // =========================================================================

  function getDefaultText(nodeType: string): string {
    if (!config.value) return 'New Node'
    const texts = config.value.defaultTexts[nodeType]
    if (!texts) return 'New Node'

    const textValue = currentLang.value === 'zh' ? texts.zh : texts.en
    return Array.isArray(textValue) ? textValue[0] : textValue
  }

  function findNodeInSpec(
    spec: DiagramSpec,
    nodeId: string
  ): { type: string; index?: number; field?: string } | null {
    if (!config.value || !spec) return null

    // Check main/protected nodes first
    for (const protectedType of config.value.protectedNodes) {
      if (nodeId === protectedType || nodeId.startsWith(`${protectedType}_`)) {
        return { type: protectedType }
      }
    }

    // Check array fields
    for (const [nodeType, field] of Object.entries(config.value.arrayFields)) {
      const arr = (spec as Record<string, unknown>)[field]
      if (Array.isArray(arr)) {
        // Match by pattern: nodeType_index (e.g., context_0, branch_1)
        const match = nodeId.match(new RegExp(`^${nodeType}_(\\d+)$`))
        if (match) {
          const index = parseInt(match[1], 10)
          if (index < arr.length) {
            return { type: nodeType, index, field }
          }
        }
      }
    }

    return null
  }

  // =========================================================================
  // Operations Factory
  // =========================================================================

  function createOperations(): DiagramOperations | null {
    if (!config.value || !effectiveType.value) return null

    const cfg = config.value
    const type = effectiveType.value

    return {
      addNode(spec: DiagramSpec, nodeType?: string): AddNodeResult | null {
        if (!spec) return null

        // Determine which node type to add
        const addType = nodeType || cfg.nodeTypes.find((t) => !cfg.protectedNodes.includes(t))
        if (!addType) return null

        const field = cfg.arrayFields[addType]
        if (!field) {
          console.warn(`[DiagramOperations] No array field for node type: ${addType}`)
          return null
        }

        const arr = (spec as Record<string, unknown>)[field]
        if (!Array.isArray(arr)) {
          console.warn(`[DiagramOperations] Field ${field} is not an array`)
          return null
        }

        // Add new node
        const newText = getDefaultText(addType)
        arr.push(newText)

        const index = arr.length - 1
        const newNodeId = `${addType}_${index}`

        // Emit events
        eventBus.emit('diagram:node_added', {
          diagramType: type,
          nodeType: addType,
          nodeIndex: index,
        })

        eventBus.emit('diagram:operation_completed', {
          operation: 'add_node',
          details: { nodeId: newNodeId, nodeType: addType },
        })

        return { nodeId: newNodeId, nodeType: addType, index }
      },

      deleteNodes(spec: DiagramSpec, nodeIds: string[]): DeleteNodeResult | null {
        if (!spec || !nodeIds.length) return null

        const warnings: string[] = []
        const toDelete: Map<string, number[]> = new Map()

        // Categorize nodes by their array field
        for (const nodeId of nodeIds) {
          const nodeInfo = findNodeInSpec(spec, nodeId)
          if (!nodeInfo) continue

          if (cfg.protectedNodes.includes(nodeInfo.type)) {
            warnings.push(`Cannot delete ${nodeInfo.type} node`)
            continue
          }

          if (nodeInfo.field && nodeInfo.index !== undefined) {
            if (!toDelete.has(nodeInfo.field)) {
              toDelete.set(nodeInfo.field, [])
            }
            toDelete.get(nodeInfo.field)!.push(nodeInfo.index)
          }
        }

        const deletedIds: string[] = []
        const deletedIndices: number[] = []

        // Delete from each array (in reverse order to preserve indices)
        for (const [field, indices] of toDelete) {
          const arr = (spec as Record<string, unknown[]>)[field]
          if (!Array.isArray(arr)) continue

          // Sort descending
          indices.sort((a, b) => b - a)

          for (const index of indices) {
            if (index < arr.length) {
              arr.splice(index, 1)
              deletedIndices.push(index)

              // Find the node type for this field
              const nodeType = Object.entries(cfg.arrayFields).find(([, f]) => f === field)?.[0]
              if (nodeType) {
                deletedIds.push(`${nodeType}_${index}`)
              }
            }
          }
        }

        if (deletedIds.length > 0) {
          eventBus.emit('diagram:nodes_deleted', {
            diagramType: type,
            deletedIds,
            deletedIndices,
          })

          eventBus.emit('diagram:operation_completed', {
            operation: 'delete_nodes',
            details: { deletedIds },
          })
        }

        return { deletedIds, deletedIndices, warnings }
      },

      updateNode(spec: DiagramSpec, nodeId: string, updates: NodeUpdate): boolean {
        if (!spec) return false

        const nodeInfo = findNodeInSpec(spec, nodeId)
        if (!nodeInfo) return false

        // Handle protected nodes (topic, main, etc.)
        if (cfg.protectedNodes.includes(nodeInfo.type) && updates.text !== undefined) {
          // Update the main field directly (use index access since DiagramSpec has index signature)
          if (nodeInfo.type === 'topic' && 'topic' in spec) {
            spec['topic'] = updates.text
          } else if (nodeInfo.type === 'whole' && 'whole' in spec) {
            spec['whole'] = updates.text
          } else if (nodeInfo.type === 'main' && 'main' in spec) {
            spec['main'] = updates.text
          } else if (nodeInfo.type === 'event' && 'event' in spec) {
            spec['event'] = updates.text
          }
        }

        // Handle array nodes
        if (nodeInfo.field && nodeInfo.index !== undefined && updates.text !== undefined) {
          const arr = (spec as Record<string, unknown[]>)[nodeInfo.field]
          if (Array.isArray(arr) && nodeInfo.index < arr.length) {
            arr[nodeInfo.index] = updates.text
          }
        }

        eventBus.emit('diagram:node_updated', {
          diagramType: type,
          nodeId,
          nodeType: nodeInfo.type,
          updates,
        })

        eventBus.emit('diagram:operation_completed', {
          operation: 'update_node',
          details: { nodeId, updates },
        })

        return true
      },

      savePosition(spec: DiagramSpec, nodeId: string, position: NodePosition): boolean {
        if (!spec) return false

        // Initialize custom positions if needed
        if (!(spec as Record<string, unknown>)._customPositions) {
          ;(spec as Record<string, unknown>)._customPositions = {}
        }

        const positions = (spec as { _customPositions: Record<string, NodePosition> })
          ._customPositions
        positions[nodeId] = position

        eventBus.emit('diagram:position_saved', {
          diagramType: type,
          nodeId,
          position,
        })

        return true
      },

      saveStyles(spec: DiagramSpec, nodeId: string, styles: NodeStyles): boolean {
        if (!spec) return false

        // Initialize node styles if needed
        if (!(spec as Record<string, unknown>)._node_styles) {
          ;(spec as Record<string, unknown>)._node_styles = {}
        }

        const nodeStyles = (spec as { _node_styles: Record<string, NodeStyles> })._node_styles
        nodeStyles[nodeId] = { ...(nodeStyles[nodeId] || {}), ...styles }

        return true
      },

      clearPositions(spec: DiagramSpec): boolean {
        if (!spec) return false

        delete (spec as Record<string, unknown>)._customPositions

        eventBus.emit('diagram:positions_cleared', { diagramType: type })
        eventBus.emit('diagram:operation_completed', {
          operation: 'clear_positions',
          details: {},
        })

        return true
      },

      validateSpec(spec: DiagramSpec): boolean {
        if (!spec) return false

        // Check required fields based on diagram type
        switch (type) {
          case 'circle_map':
            return 'topic' in spec && Array.isArray((spec as { context?: unknown }).context)
          case 'bubble_map':
            return 'topic' in spec && Array.isArray((spec as { attributes?: unknown }).attributes)
          case 'mindmap':
            return 'topic' in spec && Array.isArray((spec as { branches?: unknown }).branches)
          case 'flow_map':
            return Array.isArray((spec as { steps?: unknown }).steps)
          case 'concept_map':
            return Array.isArray((spec as { nodes?: unknown }).nodes)
          default:
            return true
        }
      },

      getNodeTypes(): string[] {
        return cfg.nodeTypes
      },

      canAddNode(nodeType?: string): boolean {
        const addType = nodeType || cfg.nodeTypes.find((t) => !cfg.protectedNodes.includes(t))
        if (!addType) return false

        // Check if we have an array field for this type
        return !!cfg.arrayFields[addType]
      },

      canDeleteNode(nodeId: string, nodeType: string): boolean {
        return !cfg.protectedNodes.includes(nodeType)
      },
    }
  }

  // =========================================================================
  // Watch for diagram type changes
  // =========================================================================

  watch(
    effectiveType,
    (newType) => {
      if (newType) {
        operations.value = createOperations()

        eventBus.emit('diagram:operations_loaded', {
          diagramType: newType,
          available: !!operations.value,
        })
      } else {
        operations.value = null
      }
    },
    { immediate: true }
  )

  // =========================================================================
  // EventBus Subscriptions
  // =========================================================================

  const unsubTypeChanged = eventBus.onWithOwner(
    'diagram:type_changed',
    (data) => {
      if (data.diagramType) {
        diagramType.value = data.diagramType as DiagramType
      }
    },
    ownerId
  )

  const unsubLoaded = eventBus.onWithOwner(
    'diagram:loaded',
    (data) => {
      if (data.diagramType) {
        diagramType.value = data.diagramType as DiagramType
      }
    },
    ownerId
  )

  // =========================================================================
  // Voice Agent Event Subscriptions (Bridge voice commands to diagram)
  // =========================================================================

  // Handle diagram:add_nodes from voice agent
  const unsubAddNodes = eventBus.onWithOwner(
    'diagram:add_nodes',
    (data) => {
      if (!operations.value) return

      const nodes = data.nodes as unknown[]
      if (!Array.isArray(nodes)) return

      // Import store dynamically to avoid circular dependency
      import('@/stores/diagram').then(({ useDiagramStore }) => {
        const store = useDiagramStore()
        const spec = store.data as DiagramSpec | null

        if (!spec) return

        let addedCount = 0
        nodes.forEach((node) => {
          const nodeType =
            typeof node === 'object' && node !== null
              ? ((node as Record<string, unknown>).type as string)
              : undefined
          const result = operations.value?.addNode(spec, nodeType)
          if (result) addedCount++
        })

        // Save to history after all nodes added
        if (addedCount > 0) {
          store.pushHistory(`Add ${addedCount} node(s) via voice`)
        }
      })
    },
    ownerId
  )

  // Handle diagram:update_nodes from voice agent
  const unsubUpdateNodes = eventBus.onWithOwner(
    'diagram:update_nodes',
    (data) => {
      if (!operations.value) return

      const nodes = data.nodes as unknown[]
      if (!Array.isArray(nodes)) return

      import('@/stores/diagram').then(({ useDiagramStore }) => {
        const store = useDiagramStore()
        const spec = store.data as DiagramSpec | null

        if (!spec) return

        let updatedCount = 0
        nodes.forEach((nodeData) => {
          if (typeof nodeData !== 'object' || nodeData === null) return

          const obj = nodeData as Record<string, unknown>
          const nodeId = (obj.node_id as string) || (obj.id as string)
          const text = (obj.text as string) || (obj.new_text as string)

          if (nodeId && text !== undefined) {
            const result = operations.value?.updateNode(spec, nodeId, { text })
            if (result) updatedCount++
          }
        })

        // Save to history after all nodes updated
        if (updatedCount > 0) {
          store.pushHistory(`Update ${updatedCount} node(s) via voice`)
        }
      })
    },
    ownerId
  )

  // Handle diagram:remove_nodes from voice agent
  const unsubRemoveNodes = eventBus.onWithOwner(
    'diagram:remove_nodes',
    (data) => {
      if (!operations.value) return

      const nodeIds = data.nodeIds as unknown[]
      if (!Array.isArray(nodeIds)) return

      import('@/stores/diagram').then(({ useDiagramStore }) => {
        const store = useDiagramStore()
        const spec = store.data as DiagramSpec | null

        if (!spec) return

        // Extract node IDs from various formats
        const ids = nodeIds
          .map((item) => {
            if (typeof item === 'string') return item
            if (typeof item === 'object' && item !== null) {
              return (
                ((item as Record<string, unknown>).node_id as string) ||
                ((item as Record<string, unknown>).id as string)
              )
            }
            return null
          })
          .filter((id): id is string => id !== null)

        if (ids.length > 0) {
          const result = operations.value?.deleteNodes(spec, ids)
          if (result && result.deletedIds.length > 0) {
            store.pushHistory(`Delete ${result.deletedIds.length} node(s) via voice`)
          }
        }
      })
    },
    ownerId
  )

  // Handle diagram:update_center from voice agent
  const unsubUpdateCenter = eventBus.onWithOwner(
    'diagram:update_center',
    (data) => {
      if (!operations.value) return

      import('@/stores/diagram').then(({ useDiagramStore }) => {
        const store = useDiagramStore()
        const spec = store.data as DiagramSpec | null

        if (!spec) return

        // Update center/topic text based on diagram type
        const newText = (data.new_text as string) || (data.text as string)
        if (newText !== undefined) {
          // Determine the center node ID based on diagram type
          const centerNodeId = 'topic' // Most diagram types use 'topic' for center
          const result = operations.value?.updateNode(spec, centerNodeId, { text: newText })
          if (result) {
            store.pushHistory('Update center via voice')
          }
        }
      })
    },
    ownerId
  )

  // =========================================================================
  // Public API
  // =========================================================================

  function setDiagramType(type: DiagramType): void {
    diagramType.value = type
  }

  function setLanguage(lang: string): void {
    currentLang.value = lang
  }

  function hasOperations(): boolean {
    return !!operations.value
  }

  function getAvailableDiagramTypes(): string[] {
    return Object.keys(DIAGRAM_CONFIGS)
  }

  // =========================================================================
  // Cleanup
  // =========================================================================

  function destroy(): void {
    unsubTypeChanged()
    unsubLoaded()
    unsubAddNodes()
    unsubUpdateNodes()
    unsubRemoveNodes()
    unsubUpdateCenter()
    eventBus.removeAllListenersForOwner(ownerId)
  }

  onUnmounted(() => {
    destroy()
  })

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    diagramType,
    effectiveType,
    operations,
    config,

    // Actions
    setDiagramType,
    setLanguage,

    // Queries
    hasOperations,
    getAvailableDiagramTypes,

    // Cleanup
    destroy,
  }
}

// ============================================================================
// Singleton instance for global access
// ============================================================================

let _globalOps: ReturnType<typeof useDiagramOperations> | null = null

export function getDiagramOperations(): ReturnType<typeof useDiagramOperations> {
  if (!_globalOps) {
    _globalOps = useDiagramOperations({ ownerId: 'GlobalDiagramOps' })
  }
  return _globalOps
}
