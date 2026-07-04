<script setup lang="ts">
/**
 * SidebarOutline — flat hierarchy tree with default / hover / selected states.
 */
import { computed, nextTick, ref } from 'vue'

import { ElTooltip } from 'element-plus'

import { ChevronDown, FileText, GitCommit, GripVertical, Plus, Trash2 } from '@lucide/vue'

import MindMapSidePanelCloseButton from '@/components/canvas/MindMapSidePanelCloseButton.vue'

import { useLanguage } from '@/composables'
import { useMindMapOutlineMirror } from '@/composables/mindMap/useMindMapOutlineMirror'
import { useMindMapOutlineDrag } from '@/composables/mindMap/useMindMapOutlineDrag'
import { useMindMapMultiLinePaste } from '@/composables/mindMap/useMindMapMultiLinePaste'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores'
import type { MindMapOutlineNode } from '@/utils/mindMapOutlineTree'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const diagramStore = useDiagramStore()

const DEPTH_INDENT_PX = 22
const ROOT_PADDING_PX = 12

type OutlineRow = {
  node: MindMapOutlineNode
  depth: number
  hasChildren: boolean
  collapsed: boolean
}

const editingNodeId = ref<string | null>(null)
const editDraft = ref('')
const editInputRef = ref<HTMLInputElement | null>(null)
const rowRefs = ref(new Map<string, HTMLElement>())

const { handlePaste: handleMindMapMultiLinePaste } = useMindMapMultiLinePaste({
  isBlocked: () => editingNodeId.value !== null,
})

const {
  focusNodeFromOutline,
  toggleOutlineBranch,
  isOutlineBranchCollapsed,
  getOutlineTree,
} = useMindMapOutlineMirror({
  enabled: () => true,
  scrollToRow: (nodeId) => {
    rowRefs.value.get(nodeId)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  },
})

const {
  draggingNodeId,
  canDragNode,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDragLeave,
  onDrop,
  isDropBefore,
  isDropAfter,
  isDropChild,
} = useMindMapOutlineDrag()

function rowIndent(depth: number): string {
  return `${ROOT_PADDING_PX + depth * DEPTH_INDENT_PX}px`
}

function collectVisibleRows(nodes: MindMapOutlineNode[], depth = 0): OutlineRow[] {
  const rows: OutlineRow[] = []
  for (const node of nodes) {
    const hasChildren = node.children.length > 0
    const collapsed = hasChildren && isOutlineBranchCollapsed(node.id)
    rows.push({ node, depth, hasChildren, collapsed })
    if (hasChildren && !collapsed) {
      rows.push(...collectVisibleRows(node.children, depth + 1))
    }
  }
  return rows
}

const visibleRows = computed(() => {
  void diagramStore.data?.nodes?.length
  void diagramStore.data?.connections?.length
  void diagramStore.data?._collapsed_paths
  return collectVisibleRows(getOutlineTree())
})

function setRowRef(nodeId: string, el: Element | null): void {
  if (el instanceof HTMLElement) rowRefs.value.set(nodeId, el)
  else rowRefs.value.delete(nodeId)
}

function isSelected(nodeId: string): boolean {
  return diagramStore.selectedNodes.includes(nodeId)
}

function handleClose(): void {
  emit('close')
}

function handleRowClick(nodeId: string): void {
  if (editingNodeId.value) return
  focusNodeFromOutline(nodeId)
}

async function startEdit(nodeId: string, text: string): Promise<void> {
  editingNodeId.value = nodeId
  editDraft.value = text
  diagramStore.selectNodes(nodeId)
  await nextTick()
  editInputRef.value?.focus()
  editInputRef.value?.select()
}

function commitEdit(): void {
  const nodeId = editingNodeId.value
  if (!nodeId) return
  const text = editDraft.value.trim()
  if (text) {
    eventBus.emit('node:text_updated', { nodeId, text })
  }
  editingNodeId.value = null
  editDraft.value = ''
}

function cancelEdit(): void {
  editingNodeId.value = null
  editDraft.value = ''
}

function handleAddChild(nodeId: string): void {
  diagramStore.selectNodes(nodeId)
  if (nodeId === 'topic') {
    diagramStore.addMindMapBranch(
      'right',
      t('canvas.toolbar.newBranch'),
      t('canvas.toolbar.newChild')
    )
    return
  }
  diagramStore.addMindMapChild(nodeId, t('canvas.toolbar.newChild'))
}

function handleAddSibling(nodeId: string): void {
  if (nodeId === 'topic') return
  diagramStore.selectNodes(nodeId)
  diagramStore.addMindMapSibling(nodeId, t('canvas.toolbar.newBranch'))
}

function handleDelete(nodeId: string): void {
  if (nodeId === 'topic') return
  diagramStore.removeMindMapNodes([nodeId])
  diagramStore.clearSelection()
}

function rowClass(nodeId: string): string {
  if (isSelected(nodeId)) return 'sidebar-outline__row sidebar-outline__row--selected'
  return 'sidebar-outline__row sidebar-outline__row--idle'
}

function showActions(nodeId: string): boolean {
  return editingNodeId.value !== nodeId
}
</script>

<template>
  <aside
    class="sidebar-outline pointer-events-auto absolute inset-y-3 left-3 z-40 flex w-80 flex-col overflow-hidden rounded-2xl border border-slate-200/70 bg-white shadow-sm"
    :aria-label="t('canvas.mindMapSideToolbar.outline')"
  >
    <header class="shrink-0 border-b border-gray-100 bg-white px-4 pb-3 pt-3.5">
      <div class="flex items-center justify-between gap-3">
        <div class="flex min-w-0 flex-1 items-center justify-start gap-2">
          <FileText
            class="h-4 w-4 shrink-0 text-emerald-500"
            :stroke-width="1.75"
          />
          <span class="truncate text-[13px] font-semibold text-slate-800">
            {{ t('canvas.mindMapSideToolbar.outline') }}
          </span>
        </div>
        <MindMapSidePanelCloseButton @close="handleClose" />
      </div>

      <div class="mt-2.5 flex flex-col gap-1">
        <span class="text-[10px] leading-snug text-gray-400">
          {{ t('canvas.mindMapSideToolbar.outlineDragHint') }}
        </span>
        <span class="text-[10px] leading-snug text-gray-400">
          {{ t('canvas.mindMapSideToolbar.outlinePasteHint') }}
        </span>
      </div>
      <div class="mt-1 flex justify-end">
        <span class="shrink-0 text-[10px] font-semibold text-blue-600">
          {{ t('canvas.mindMapSideToolbar.realtimeSync') }}
        </span>
      </div>
    </header>

    <div
      class="sidebar-outline__scroll min-h-0 flex-1 overflow-y-auto bg-white py-2 pr-2"
      @paste.capture="handleMindMapMultiLinePaste"
    >
      <ul
        v-if="visibleRows.length"
        class="m-0 flex list-none flex-col p-0"
      >
        <li
          v-for="row in visibleRows"
          :key="row.node.id"
          :ref="(el) => setRowRef(row.node.id, el as Element | null)"
          class="group list-none outline-none"
          :class="{
            'sidebar-outline__row--dragging': draggingNodeId === row.node.id,
          }"
          :style="{ paddingLeft: rowIndent(row.depth) }"
          :draggable="canDragNode(row.node.id) && editingNodeId !== row.node.id"
          @dragstart="onDragStart($event, row.node.id)"
          @dragend="onDragEnd"
          @dragover="onDragOver($event, row.node.id)"
          @dragleave="onDragLeave"
          @drop="onDrop($event, row.node.id)"
        >
          <div
            v-if="isDropBefore(row.node.id)"
            class="sidebar-outline__drop-line sidebar-outline__drop-line--before"
          />
          <div
            :class="[
              rowClass(row.node.id),
              { 'sidebar-outline__row--drop-child': isDropChild(row.node.id) },
            ]"
          >
            <span
              v-if="canDragNode(row.node.id)"
              class="sidebar-outline__grip shrink-0"
              aria-hidden="true"
            >
              <GripVertical
                class="h-3.5 w-3.5"
                :stroke-width="2"
              />
            </span>
            <span
              v-else
              class="w-[14px] shrink-0"
              aria-hidden="true"
            />
            <!-- Chevron (branch nodes only) -->
            <button
              v-if="row.hasChildren"
              type="button"
              class="sidebar-outline__toggle shrink-0"
              :aria-label="
                row.collapsed
                  ? t('canvas.mindMapSideToolbar.expandBranch')
                  : t('canvas.mindMapSideToolbar.collapseBranch')
              "
              @click.stop="toggleOutlineBranch(row.node.id)"
            >
              <ChevronDown
                class="h-3.5 w-3.5 transition-transform duration-200"
                :class="row.collapsed ? '-rotate-90' : ''"
                :stroke-width="2"
              />
            </button>
            <span
              v-else
              class="w-[18px] shrink-0"
              aria-hidden="true"
            />

            <!-- Text -->
            <div class="min-w-0 flex-1 py-1">
              <button
                v-if="editingNodeId !== row.node.id && !isSelected(row.node.id)"
                type="button"
                class="sidebar-outline__text sidebar-outline__text--plain w-full truncate text-left"
                @click="handleRowClick(row.node.id)"
                @dblclick.stop="startEdit(row.node.id, row.node.text)"
              >
                {{ row.node.text }}
              </button>

              <button
                v-else-if="editingNodeId !== row.node.id && isSelected(row.node.id)"
                type="button"
                class="sidebar-outline__text sidebar-outline__text--pill w-full truncate text-left"
                @click="handleRowClick(row.node.id)"
                @dblclick.stop="startEdit(row.node.id, row.node.text)"
              >
                {{ row.node.text }}
              </button>

              <input
                v-else
                ref="editInputRef"
                v-model="editDraft"
                type="text"
                class="sidebar-outline__text sidebar-outline__text--pill sidebar-outline__input w-full"
                @keydown.enter="commitEdit"
                @keydown.esc="cancelEdit"
                @blur="commitEdit"
              />
            </div>

            <!-- Actions: hover (fig2) or always when selected (fig3) -->
            <div
              v-if="showActions(row.node.id)"
              class="sidebar-outline__actions shrink-0"
              :class="isSelected(row.node.id) ? 'is-visible' : ''"
            >
              <ElTooltip
                :content="t('canvas.mindMapSideToolbar.addChild')"
                placement="top"
                :show-after="200"
              >
                <button
                  type="button"
                  class="sidebar-outline__action-btn"
                  @click.stop="handleAddChild(row.node.id)"
                >
                  <Plus
                    class="h-3.5 w-3.5"
                    :stroke-width="1.75"
                  />
                </button>
              </ElTooltip>
              <ElTooltip
                v-if="row.node.id !== 'topic'"
                :content="t('canvas.mindMapSideToolbar.addSibling')"
                placement="top"
                :show-after="200"
              >
                <button
                  type="button"
                  class="sidebar-outline__action-btn"
                  @click.stop="handleAddSibling(row.node.id)"
                >
                  <GitCommit
                    class="h-3.5 w-3.5"
                    :stroke-width="1.75"
                  />
                </button>
              </ElTooltip>
              <ElTooltip
                v-if="row.node.id !== 'topic'"
                :content="t('canvas.mindMapSideToolbar.deleteBranch')"
                placement="top"
                :show-after="200"
              >
                <button
                  type="button"
                  class="sidebar-outline__action-btn sidebar-outline__action-btn--danger"
                  @click.stop="handleDelete(row.node.id)"
                >
                  <Trash2
                    class="h-3.5 w-3.5"
                    :stroke-width="1.75"
                  />
                </button>
              </ElTooltip>
            </div>
          </div>
          <div
            v-if="isDropAfter(row.node.id)"
            class="sidebar-outline__drop-line sidebar-outline__drop-line--after"
          />
        </li>
      </ul>

      <p
        v-else
        class="px-4 py-10 text-center text-[11px] text-gray-400"
      >
        {{ t('canvas.mindMapSideToolbar.outlineEmpty') }}
      </p>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-outline {
  max-height: calc(100% - 1.5rem);
}

.sidebar-outline__scroll {
  scrollbar-width: thin;
  scrollbar-color: rgb(209 213 219) transparent;
}

.sidebar-outline__scroll::-webkit-scrollbar {
  width: 4px;
}

.sidebar-outline__scroll::-webkit-scrollbar-thumb {
  border-radius: 9999px;
  background: rgb(209 213 219);
}

/* ── Row shell ── */
.sidebar-outline__row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 38px;
  margin-right: 4px;
  padding: 2px 6px 2px 4px;
  border-radius: 8px;
  transition: background-color 0.15s ease;
}

/* Fig 1 — idle: transparent */
.sidebar-outline__row--idle {
  background: transparent;
}

.sidebar-outline__row--idle:hover {
  background: rgb(243 244 246);
}

/* Fig 3 — selected: blue wash + left anchor */
.sidebar-outline__row--selected {
  background: rgb(239 246 255);
}

.sidebar-outline__row--selected::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: rgb(37 99 235);
}

/* Chevron toggle */
.sidebar-outline__toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  background: transparent;
  color: rgb(156 163 175);
  cursor: pointer;
}

.sidebar-outline__toggle:hover {
  color: rgb(107 114 128);
}

/* Text variants */
.sidebar-outline__text {
  font-size: 13px;
  line-height: 1.45;
  letter-spacing: 0.01em;
}

.sidebar-outline__text--plain {
  padding: 4px 6px;
  border: none;
  background: transparent;
  color: rgb(51 65 85);
  cursor: pointer;
}

/* Fig 3 — pill input look when selected */
.sidebar-outline__text--pill {
  padding: 4px 10px;
  border: 1px solid rgb(59 130 246);
  border-radius: 6px;
  background: rgb(255 255 255);
  color: rgb(37 99 235);
  font-weight: 500;
  cursor: pointer;
}

.sidebar-outline__input {
  cursor: text;
  outline: none;
}

.sidebar-outline__input:focus {
  box-shadow: 0 0 0 2px rgb(147 197 253 / 0.45);
}

/* Fig 2 hover — actions hidden until hover; fig 3 — always visible when selected */
.sidebar-outline__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.group:hover .sidebar-outline__actions,
.sidebar-outline__actions.is-visible {
  opacity: 1;
}

.sidebar-outline__action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: rgb(156 163 175);
  cursor: pointer;
  transition: color 0.12s ease;
}

.sidebar-outline__action-btn:hover {
  color: rgb(75 85 99);
}

.sidebar-outline__row--drop-child {
  outline: 2px dashed rgb(37 99 235 / 0.55);
  outline-offset: 1px;
  background: rgb(239 246 255 / 0.85);
}

.sidebar-outline__row--dragging {
  opacity: 0.45;
}

.sidebar-outline__grip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  color: rgb(148 163 184);
  cursor: grab;
}

.group:hover .sidebar-outline__grip {
  color: rgb(100 116 139);
}

.sidebar-outline__drop-line {
  height: 3px;
  margin: 1px 8px 1px 24px;
  border-radius: 2px;
  background: rgb(37 99 235);
  box-shadow: 0 0 0 2px rgb(37 99 235 / 0.2);
}

.sidebar-outline__action-btn--danger:hover {
  color: rgb(220 38 38);
}
</style>
