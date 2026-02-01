<script setup lang="ts">
/**
 * ContextMenu - Custom right-click context menu for diagram canvas
 * Replaces browser's default context menu with custom actions
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { eventBus } from '@/composables/useEventBus'
import { useDiagramStore } from '@/stores'
import type { DiagramNode, MindGraphNode } from '@/types'

interface MenuItem {
  label?: string
  icon?: string
  action?: () => void
  disabled?: boolean
  divider?: boolean
}

interface Props {
  visible: boolean
  x: number
  y: number
  node?: MindGraphNode | null
  target?: 'node' | 'pane'
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const diagramStore = useDiagramStore()
const menuRef = ref<HTMLElement | null>(null)

// Build menu items based on context
const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = []

  if (props.target === 'node' && props.node) {
    const node = props.node
    const nodeData = node.data
    const isTopicNode = nodeData?.nodeType === 'topic'
    const isBoundaryNode = nodeData?.nodeType === 'boundary'

    // Edit action
    items.push({
      label: '编辑',
      action: () => {
        emit('close')
        // Emit event to trigger edit mode
        eventBus.emit('node:edit_requested', { nodeId: node.id })
      },
    })

    items.push({ divider: true })

    // Delete action (disabled for topic/center/boundary nodes)
    items.push({
      label: '删除',
      action: () => {
        if (diagramStore.removeNode(node.id)) {
          diagramStore.pushHistory('删除节点')
          emit('close')
        }
      },
      disabled: isTopicNode || isBoundaryNode,
    })

    items.push({ divider: true })

    // For multi-flow map, add "Add Cause" or "Add Effect" based on node type
    if (diagramStore.type === 'multi_flow_map') {
      if (node.id.startsWith('cause-')) {
        items.push({
          label: '添加原因',
          action: () => {
            diagramStore.addNode({
              id: 'cause-temp',
              text: '新原因',
              type: 'flow',
              position: { x: 0, y: 0 },
              category: 'causes',
            } as DiagramNode & { category?: string })
            diagramStore.pushHistory('添加原因')
            emit('close')
          },
        })
      } else if (node.id.startsWith('effect-')) {
        items.push({
          label: '添加结果',
          action: () => {
            diagramStore.addNode({
              id: 'effect-temp',
              text: '新结果',
              type: 'flow',
              position: { x: 0, y: 0 },
              category: 'effects',
            } as DiagramNode & { category?: string })
            diagramStore.pushHistory('添加结果')
            emit('close')
          },
        })
      }
      
      items.push({ divider: true })
    }

    // Copy action
    items.push({
      label: '复制',
      action: () => {
        // TODO: Implement copy functionality
        emit('close')
      },
    })

    // Paste action
    items.push({
      label: '粘贴',
      action: () => {
        // TODO: Implement paste functionality
        emit('close')
      },
      disabled: true, // Disabled until copy is implemented
    })
  } else if (props.target === 'pane') {
    // Pane context menu
    const diagramType = diagramStore.type
    if (diagramType === 'multi_flow_map') {
      // Add cause option
      items.push({
        label: '添加原因',
        action: () => {
          diagramStore.addNode({
            id: 'cause-temp',
            text: '新原因',
            type: 'flow',
            position: { x: 0, y: 0 },
            category: 'causes',
          } as DiagramNode & { category?: string })
          diagramStore.pushHistory('添加原因')
          emit('close')
        },
      })
      
      // Add effect option
      items.push({
        label: '添加结果',
        action: () => {
          diagramStore.addNode({
            id: 'effect-temp',
            text: '新结果',
            type: 'flow',
            position: { x: 0, y: 0 },
            category: 'effects',
          } as DiagramNode & { category?: string })
          diagramStore.pushHistory('添加结果')
          emit('close')
        },
      })
    } else {
      items.push({
        label: '添加节点',
        action: () => {
          // TODO: Implement add node at position for other diagram types
          emit('close')
        },
      })
    }

    items.push({ divider: true })

    items.push({
      label: '粘贴',
      action: () => {
        // TODO: Implement paste functionality
        emit('close')
      },
      disabled: true, // Disabled until copy is implemented
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

onMounted(() => {
  if (props.visible) {
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    // Prevent default context menu
    document.addEventListener('contextmenu', preventDefault)
  }
})

onUnmounted(() => {
  document.removeEventListener('mousedown', handleClickOutside)
  document.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('contextmenu', preventDefault)
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
          :class="{ disabled: item.disabled, divider: item.divider }"
          @click="handleItemClick(item)"
        >
          <span v-if="!item.divider && item.label" class="context-menu-label">{{ item.label }}</span>
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
  padding: 8px 16px;
  cursor: pointer;
  transition: background-color 0.15s ease;
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
  transition: opacity 0.15s ease, transform 0.15s ease;
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
