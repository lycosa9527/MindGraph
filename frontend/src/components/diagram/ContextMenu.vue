<script setup lang="ts">
/**
 * ContextMenu - Custom right-click context menu for diagram canvas
 * Replaces browser's default context menu with custom actions
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  BRANCH_NODE_HEIGHT,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore, useUIStore } from '@/stores'
import type { DiagramNode, MindGraphNode } from '@/types'

interface MenuItem {
  label?: string
  icon?: string
  action?: () => void
  disabled?: boolean
  divider?: boolean
  checked?: boolean
  swatch?: string
  stroke?: string
  sectionHeader?: boolean
}

interface Props {
  visible: boolean
  x: number
  y: number
  node?: MindGraphNode | null
  target?: 'node' | 'pane'
}

const props = withDefaults(defineProps<Props>(), {})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'paste', position: { x: number; y: number }): void
  (e: 'addConcept', position: { x: number; y: number }): void
}>()

const diagramStore = useDiagramStore()
const uiStore = useUIStore()
const { t } = useLanguage()
const notify = useNotifications()
const menuRef = ref<HTMLElement | null>(null)

/** Resolve double bubble group from node id: similarity-*, left-diff-*, right-diff-* */
function getDoubleBubbleGroupFromNodeId(
  nodeId: string
): 'similarity' | 'leftDiff' | 'rightDiff' | null {
  if (/^similarity-\d+$/.test(nodeId)) return 'similarity'
  if (/^left-diff-\d+$/.test(nodeId)) return 'leftDiff'
  if (/^right-diff-\d+$/.test(nodeId)) return 'rightDiff'
  return null
}

// Build menu items based on context (reactive to UI locale via uiStore.language)
const menuItems = computed<MenuItem[]>(() => {
  void uiStore.language
  const items: MenuItem[] = []

  if (props.target === 'node' && props.node) {
    const node = props.node
    const nodeData = node.data
    const isTopicNode = nodeData?.nodeType === 'topic'
    const isBoundaryNode = nodeData?.nodeType === 'boundary'

    items.push({
      label: t('diagram.contextMenu.edit'),
      action: () => {
        emit('close')
        eventBus.emit('node:edit_requested', { nodeId: node.id })
      },
    })

    items.push({ divider: true })

    items.push({
      label: t('diagram.contextMenu.delete'),
      action: () => {
        const diagramType = diagramStore.type
        let deleted = false
        if (diagramType === 'mindmap' || diagramType === 'mind_map') {
          deleted = diagramStore.removeMindMapNodes([node.id]) > 0
        } else if (diagramType === 'brace_map') {
          deleted = diagramStore.removeBraceMapNodes([node.id]) > 0
        } else if (diagramType === 'double_bubble_map') {
          deleted = diagramStore.removeDoubleBubbleMapNodes([node.id]) > 0
        } else if (diagramType === 'tree_map') {
          deleted = diagramStore.removeTreeMapNodes([node.id]) > 0
        } else {
          deleted = diagramStore.removeNode(node.id)
        }
        if (deleted) {
          diagramStore.pushHistory(t('diagram.history.deleteNode'))
          emit('close')
        }
      },
      disabled: isTopicNode || isBoundaryNode,
    })

    items.push({ divider: true })

    if (diagramStore.type === 'multi_flow_map') {
      if (node.id.startsWith('cause-')) {
        items.push({
          label: t('diagram.contextMenu.addCause'),
          action: () => {
            diagramStore.addNode({
              id: 'cause-temp',
              text: t('diagram.flow.newCause'),
              type: 'flow',
              position: { x: 0, y: 0 },
              category: 'causes',
            } as DiagramNode & { category?: string })
            diagramStore.pushHistory(t('diagram.history.addCause'))
            emit('close')
          },
        })
      } else if (node.id.startsWith('effect-')) {
        items.push({
          label: t('diagram.contextMenu.addEffect'),
          action: () => {
            diagramStore.addNode({
              id: 'effect-temp',
              text: t('diagram.flow.newEffect'),
              type: 'flow',
              position: { x: 0, y: 0 },
              category: 'effects',
            } as DiagramNode & { category?: string })
            diagramStore.pushHistory(t('diagram.history.addEffect'))
            emit('close')
          },
        })
      }

      items.push({ divider: true })
    }

    if (diagramStore.type === 'double_bubble_map') {
      const group = getDoubleBubbleGroupFromNodeId(node.id)
      if (group) {
        const spec = diagramStore.getDoubleBubbleSpecFromData()
        if (spec) {
          const similarities = (spec.similarities as string[]) || []
          const leftDifferences = (spec.leftDifferences as string[]) || []
          const rightDifferences = (spec.rightDifferences as string[]) || []
          const newSimText = t('diagram.doubleBubble.similarityN', {
            n: similarities.length + 1,
          })
          const pairIndex = Math.max(leftDifferences.length, rightDifferences.length) + 1
          const newLeftText = t('diagram.doubleBubble.differenceAn', { n: pairIndex })
          const newRightText = t('diagram.doubleBubble.differenceBn', { n: pairIndex })
          const text = group === 'similarity' ? newSimText : newLeftText
          const pairText = group === 'similarity' ? undefined : newRightText
          items.push({
            label: t('diagram.contextMenu.addToGroup'),
            action: () => {
              if (diagramStore.addDoubleBubbleMapNode(group, text, pairText)) {
                diagramStore.pushHistory(t('diagram.history.addNode'))
              }
              emit('close')
            },
          })
        }
        items.push({ divider: true })
      }
    }

    if (diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map') {
      if (node.id !== 'topic') {
        items.push({
          label: t('diagram.contextMenu.addChild'),
          action: () => {
            if (diagramStore.addMindMapChild(node.id, t('diagram.newChild'))) {
              diagramStore.pushHistory(t('diagram.history.addChild'))
            }
            emit('close')
          },
        })
      }
      items.push({
        label: t('diagram.contextMenu.addBranch'),
        action: () => {
          const side = node.id.startsWith('branch-l-') ? 'left' : 'right'
          const childText = t('diagram.newChild')
          if (diagramStore.addMindMapBranch(side, t('diagram.newBranch'), childText)) {
            diagramStore.pushHistory(t('diagram.history.addBranch'))
          }
          emit('close')
        },
      })
      items.push({ divider: true })
    }

    items.push({
      label: t('diagram.contextMenu.copy'),
      action: () => {
        diagramStore.copySelectedNodes()
        emit('close')
      },
      disabled: !diagramStore.hasSelection,
    })

    items.push({
      label: t('diagram.contextMenu.paste'),
      action: () => {
        emit('paste', { x: props.x, y: props.y })
        emit('close')
      },
      disabled: !diagramStore.canPaste,
    })
  } else if (props.target === 'pane') {
    const diagramType = diagramStore.type
    if (diagramType === 'multi_flow_map') {
      items.push({
        label: t('diagram.contextMenu.addCause'),
        action: () => {
          diagramStore.addNode({
            id: 'cause-temp',
            text: t('diagram.flow.newCause'),
            type: 'flow',
            position: { x: 0, y: 0 },
            category: 'causes',
          } as DiagramNode & { category?: string })
          diagramStore.pushHistory(t('diagram.history.addCause'))
          emit('close')
        },
      })

      items.push({
        label: t('diagram.contextMenu.addEffect'),
        action: () => {
          diagramStore.addNode({
            id: 'effect-temp',
            text: t('diagram.flow.newEffect'),
            type: 'flow',
            position: { x: 0, y: 0 },
            category: 'effects',
          } as DiagramNode & { category?: string })
          diagramStore.pushHistory(t('diagram.history.addEffect'))
          emit('close')
        },
      })
    } else if (diagramType === 'bubble_map') {
      items.push({
        label: t('diagram.contextMenu.addAttribute'),
        action: () => {
          if (!diagramStore.data?.nodes) {
            notify.warning(t('diagram.contextMenu.warningCreateDiagramFirst'))
            emit('close')
            return
          }
          const bubbleNodes = diagramStore.data.nodes.filter(
            (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
          )
          const newIndex = bubbleNodes.length
          diagramStore.addNode({
            id: `bubble-${newIndex}`,
            text: t('diagram.newAttribute'),
            type: 'bubble',
            position: { x: 0, y: 0 },
          })
          diagramStore.pushHistory(t('diagram.history.addAttribute'))
          emit('close')
        },
      })
    } else if (diagramType === 'circle_map') {
      items.push({
        label: t('diagram.contextMenu.addNode'),
        action: () => {
          if (!diagramStore.data?.nodes) {
            notify.warning(t('diagram.contextMenu.warningCreateDiagramFirst'))
            emit('close')
            return
          }
          const contextNodes = diagramStore.data.nodes.filter(
            (n) => n.type === 'bubble' && n.id.startsWith('context-')
          )
          const newIndex = contextNodes.length
          diagramStore.addNode({
            id: `context-${newIndex}`,
            text: t('diagram.contextMenu.circleNewIdea'),
            type: 'bubble',
            position: { x: 0, y: 0 },
          })
          diagramStore.pushHistory(t('diagram.history.addNode'))
          emit('close')
        },
      })
    } else if (diagramType === 'concept_map') {
      items.push({
        label: t('diagram.contextMenu.addConcept'),
        action: () => {
          emit('addConcept', { x: props.x, y: props.y })
          emit('close')
        },
      })
    } else if (diagramType === 'bridge_map') {
      items.push({
        label: t('diagram.contextMenu.addNode'),
        action: () => {
          if (!diagramStore.data?.nodes) {
            notify.warning(t('diagram.contextMenu.warningCreateDiagramFirst'))
            emit('close')
            return
          }
          const pairNodes = diagramStore.data.nodes.filter(
            (n) =>
              n.data?.diagramType === 'bridge_map' &&
              n.data?.pairIndex !== undefined &&
              !n.data?.isDimensionLabel
          )
          let maxPairIndex = -1
          pairNodes.forEach((node) => {
            const pairIndex = node.data?.pairIndex
            if (typeof pairIndex === 'number' && pairIndex > maxPairIndex) {
              maxPairIndex = pairIndex
            }
          })
          const newPairIndex = maxPairIndex + 1
          const centerY = DEFAULT_CENTER_Y
          const gapBetweenPairs = 50
          const verticalGap = 5
          const nodeWidth = DEFAULT_NODE_WIDTH
          const nodeHeight = BRANCH_NODE_HEIGHT
          const gapFromLabelRight = 10
          const estimatedLabelWidth = 100
          const startX = DEFAULT_PADDING + estimatedLabelWidth + gapFromLabelRight
          let nextX = startX
          if (pairNodes.length > 0) {
            const rightmostNode = pairNodes.reduce((rightmost, node) => {
              if (!rightmost) return node
              const rightmostX = rightmost.position?.x || 0
              const nodeX = node.position?.x || 0
              return nodeX > rightmostX ? node : rightmost
            })
            const rightmostX = rightmostNode.position?.x || startX
            nextX = rightmostX + nodeWidth + gapBetweenPairs
          }
          const leftNodeY = centerY - verticalGap - nodeHeight
          const rightNodeY = centerY + verticalGap
          const leftNode: DiagramNode = {
            id: `pair-${newPairIndex}-left`,
            text: t('diagram.contextMenu.bridgeItemA'),
            type: 'branch',
            position: { x: nextX, y: leftNodeY },
            data: {
              pairIndex: newPairIndex,
              position: 'left',
              diagramType: 'bridge_map',
            },
          }
          const rightNode: DiagramNode = {
            id: `pair-${newPairIndex}-right`,
            text: t('diagram.contextMenu.bridgeItemB'),
            type: 'branch',
            position: { x: nextX, y: rightNodeY },
            data: {
              pairIndex: newPairIndex,
              position: 'right',
              diagramType: 'bridge_map',
            },
          }
          diagramStore.addNode(leftNode)
          diagramStore.addNode(rightNode)
          diagramStore.pushHistory(t('diagram.history.addAnalogyPair'))
          emit('close')
        },
      })
    } else if (diagramType === 'double_bubble_map') {
      const selectedId = diagramStore.selectedNodes[0]
      const group = getDoubleBubbleGroupFromNodeId(selectedId)
      items.push({
        label: t('diagram.contextMenu.addNode'),
        action: () => {
          if (!group) {
            notify.warning(t('diagram.contextMenu.warningSelectSimilarityOrDiff'))
            emit('close')
            return
          }
          const spec = diagramStore.getDoubleBubbleSpecFromData()
          if (!spec) {
            emit('close')
            return
          }
          const similarities = (spec.similarities as string[]) || []
          const leftDifferences = (spec.leftDifferences as string[]) || []
          const rightDifferences = (spec.rightDifferences as string[]) || []
          const newSimText = t('diagram.doubleBubble.similarityN', {
            n: similarities.length + 1,
          })
          const pairIndex = Math.max(leftDifferences.length, rightDifferences.length) + 1
          const newLeftText = t('diagram.doubleBubble.differenceAn', { n: pairIndex })
          const newRightText = t('diagram.doubleBubble.differenceBn', { n: pairIndex })
          const text = group === 'similarity' ? newSimText : newLeftText
          const pairText = group === 'similarity' ? undefined : newRightText
          if (diagramStore.addDoubleBubbleMapNode(group, text, pairText)) {
            diagramStore.pushHistory(t('diagram.history.addNode'))
          }
          emit('close')
        },
        disabled: !group,
      })
    } else {
      items.push({
        label: t('diagram.contextMenu.addNode'),
        action: () => {
          notify.info(t('diagram.contextMenu.infoAddNodeSoon'))
          emit('close')
        },
      })
    }

    items.push({ divider: true })

    items.push({
      label: t('diagram.contextMenu.paste'),
      action: () => {
        emit('paste', { x: props.x, y: props.y })
        emit('close')
      },
      disabled: !diagramStore.canPaste,
    })
  }

  return items.filter((item) => !item.divider || items.indexOf(item) < items.length - 1)
})

// Close menu when clicking outside
function handleClickOutside(event: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) {
    emit('close')
  }
}

// Close menu on Escape key
function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    emit('close')
  }
}

// Position menu to stay within viewport
const menuStyle = computed(() => {
  if (!menuRef.value) {
    return {
      left: `${props.x}px`,
      top: `${props.y}px`,
    }
  }

  const rect = menuRef.value.getBoundingClientRect()
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  let left = props.x
  let top = props.y

  // Adjust if menu would overflow right edge
  if (left + rect.width > viewportWidth) {
    left = viewportWidth - rect.width - 10
  }

  // Adjust if menu would overflow bottom edge
  if (top + rect.height > viewportHeight) {
    top = viewportHeight - rect.height - 10
  }

  // Ensure menu doesn't go off left or top edges
  left = Math.max(10, left)
  top = Math.max(10, top)

  return {
    left: `${left}px`,
    top: `${top}px`,
  }
})

function addOutsideListeners(): void {
  document.addEventListener('mousedown', handleClickOutside, true)
  document.addEventListener('keydown', handleKeyDown)
  document.addEventListener('contextmenu', preventDefault)
}

function removeOutsideListeners(): void {
  document.removeEventListener('mousedown', handleClickOutside, true)
  document.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('contextmenu', preventDefault)
}

// Add/remove listeners when menu visibility changes (not just on mount)
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      addOutsideListeners()
    } else {
      removeOutsideListeners()
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  removeOutsideListeners()
})

function preventDefault(event: Event) {
  event.preventDefault()
}

function handleItemClick(item: MenuItem) {
  if (!item.disabled && !item.divider && item.action) {
    item.action()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="context-menu">
      <div
        v-if="visible"
        ref="menuRef"
        class="context-menu"
        :style="menuStyle"
        @contextmenu.prevent
      >
        <div
          v-for="(item, index) in menuItems"
          :key="index"
          class="context-menu-item"
          :class="{
            disabled: item.disabled,
            divider: item.divider,
            'swatch-pick': !!item.swatch,
            'section-title-row': item.sectionHeader && !item.action,
          }"
          @click="handleItemClick(item)"
        >
          <template v-if="item.divider" />
          <template v-else-if="item.swatch">
            <span class="context-menu-check">{{ item.checked ? '✓' : '' }}</span>
            <span
              class="context-menu-swatch"
              :style="{ backgroundColor: item.swatch }"
            />
          </template>
          <template v-else>
            <span
              v-if="item.checked !== undefined"
              class="context-menu-check"
              >{{ item.checked ? '✓' : '' }}</span
            >
            <span
              v-if="item.label"
              class="context-menu-label"
              :class="{ 'is-section-title': item.sectionHeader }"
              >{{ item.label }}</span
            >
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.context-menu {
  position: fixed;
  z-index: 10000;
  min-width: 160px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 4px 0;
  font-size: 14px;
  user-select: none;
}

.dark .context-menu {
  background: #1f2937;
  border-color: #374151;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.context-menu-check {
  width: 1.25rem;
  flex-shrink: 0;
  text-align: center;
  font-size: 12px;
  color: #059669;
}

.dark .context-menu-check {
  color: #34d399;
}

.context-menu-swatch {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid #e5e7eb;
  flex-shrink: 0;
  box-sizing: border-box;
}

.dark .context-menu-swatch {
  border-color: #4b5563;
}

.context-menu-label.is-section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #9ca3af;
}

.dark .context-menu-label.is-section-title {
  color: #6b7280;
}

.context-menu-item.section-title-row {
  cursor: default;
  padding-top: 10px;
  padding-bottom: 4px;
}

.context-menu-item.section-title-row:hover {
  background-color: transparent !important;
}

.context-menu-item.swatch-pick {
  padding-top: 4px;
  padding-bottom: 4px;
}

.context-menu-item:hover:not(.disabled):not(.divider) {
  background-color: #f3f4f6;
}

.dark .context-menu-item:hover:not(.disabled):not(.divider) {
  background-color: #374151;
}

.context-menu-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.context-menu-item.divider {
  display: block;
  height: 1px;
  padding: 0;
  margin: 4px 0;
  background-color: #e5e7eb;
  cursor: default;
}

.dark .context-menu-item.divider {
  background-color: #374151;
}

.context-menu-label {
  display: block;
  color: #374151;
}

.dark .context-menu-label {
  color: #d1d5db;
}

/* Transition animations */
.context-menu-enter-active,
.context-menu-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
}

.context-menu-enter-from {
  opacity: 0;
  transform: scale(0.95);
}

.context-menu-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
