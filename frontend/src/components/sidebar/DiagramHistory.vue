<script setup lang="ts">
/**
 * DiagramHistory - Grouped list of saved diagrams
 * Design: Clean minimalist grouped by time periods
 * Shows max 20 items with "More" option
 */
import { computed, onMounted, ref, watch } from 'vue'

import {
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
  ElMessageBox,
  ElScrollbar,
} from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import { Edit3, FileImage, Lock, MoreHorizontal, Pin, Power, Trash2, Users } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'

import { useAuthStore } from '@/stores'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'

const props = defineProps<{
  isBlurred?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', diagram: SavedDiagram): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()

// Show all or just 10
const showAll = ref(false)
const INITIAL_LIMIT = 10

// Computed
const diagrams = computed(() => savedDiagramsStore.diagrams)
const isLoading = computed(() => savedDiagramsStore.isLoading)
const currentDiagramId = computed(() => savedDiagramsStore.currentDiagramId)
const maxDiagrams = computed(() => savedDiagramsStore.maxDiagrams)
const _remainingSlots = computed(() => savedDiagramsStore.remainingSlots)

// Group diagrams by time period with pinned at top
interface GroupedDiagrams {
  pinned: SavedDiagram[]
  today: SavedDiagram[]
  yesterday: SavedDiagram[]
  week: SavedDiagram[]
  month: SavedDiagram[]
}

const groupedDiagrams = computed((): GroupedDiagrams => {
  const groups: GroupedDiagrams = {
    pinned: [],
    today: [],
    yesterday: [],
    week: [],
    month: [],
  }

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000

  // Limit unless showAll
  const items = showAll.value ? diagrams.value : diagrams.value.slice(0, INITIAL_LIMIT)

  items.forEach((diagram) => {
    // Pinned items go to the top group
    if (diagram.is_pinned) {
      groups.pinned.push(diagram)
      return
    }

    const diagramTime = new Date(diagram.updated_at).getTime()

    if (diagramTime >= todayStart) {
      groups.today.push(diagram)
    } else if (diagramTime >= yesterdayStart) {
      groups.yesterday.push(diagram)
    } else if (diagramTime >= weekStart) {
      groups.week.push(diagram)
    } else {
      // Everything older goes to Past Month
      groups.month.push(diagram)
    }
  })

  return groups
})

// Check if there are more diagrams to show
const hasMore = computed(() => diagrams.value.length > INITIAL_LIMIT && !showAll.value)
const remainingCount = computed(() => diagrams.value.length - INITIAL_LIMIT)

// Group labels
const groupLabels = computed(() => ({
  pinned: t('sidebar.history.pinned'),
  today: t('common.date.today'),
  yesterday: t('common.date.yesterday'),
  week: t('common.date.pastWeek'),
  month: t('common.date.pastMonth'),
}))

function getDiagramTypeLabel(type: string): string {
  const key = `sidebar.diagramType.${type}`
  const translated = t(key)
  if (translated !== key) {
    return translated
  }
  return type
}

/** Popper width: compact for pin/rename/delete only; wider when collab stop is shown. */
function diagramMoreMenuPopperClass(diagram: SavedDiagram): string {
  return diagram.workshop_active
    ? 'diagram-history-more-popper diagram-history-more-popper--wide'
    : 'diagram-history-more-popper diagram-history-more-popper--narrow'
}

// Fetch diagrams on mount if authenticated
onMounted(() => {
  if (authStore.isAuthenticated && !props.isBlurred) {
    savedDiagramsStore.fetchDiagrams()
  }
})

// Re-fetch when authentication changes
watch(
  () => authStore.isAuthenticated,
  (isAuth) => {
    if (isAuth) {
      savedDiagramsStore.fetchDiagrams()
    } else {
      savedDiagramsStore.reset()
    }
  }
)

// Handle diagram click
function handleDiagramClick(diagram: SavedDiagram): void {
  savedDiagramsStore.setCurrentDiagram(diagram.id)
  emit('select', diagram)
}

// Handle rename diagram
async function handleRenameDiagram(diagramId: string): Promise<void> {
  const diagram = diagrams.value.find((d) => d.id === diagramId)
  const currentName = diagram?.title || ''

  try {
    const result = await ElMessageBox.prompt(
      t('sidebar.diagramHistory.renamePrompt'),
      t('sidebar.diagramHistory.renameTitle'),
      {
        confirmButtonText: t('common.ok'),
        cancelButtonText: t('common.cancel'),
        inputValue: currentName,
        inputPattern: /\S+/,
        inputErrorMessage: t('sidebar.diagramHistory.nameRequired'),
      }
    )

    const value =
      typeof result === 'object' && result !== null && 'value' in result
        ? (result as { value: string }).value
        : undefined
    if (value && value.trim() !== currentName) {
      await savedDiagramsStore.updateDiagram(diagramId, { title: value.trim() })
    }
  } catch {
    // User cancelled
  }
}

// Handle delete diagram - delete immediately
async function handleDeleteDiagram(diagramId: string): Promise<void> {
  try {
    const success = await savedDiagramsStore.deleteDiagram(diagramId)
    if (success) {
      notify.success(t('sidebar.diagramHistory.deleted'))
    } else {
      notify.error(t('sidebar.diagramHistory.deleteFailed'))
    }
  } catch (error) {
    console.error('[DiagramHistory] Delete error:', error)
    notify.error(t('sidebar.diagramHistory.deleteFailed'))
  }
}

// Handle pin/unpin diagram
async function handlePinDiagram(diagramId: string): Promise<void> {
  const diagram = diagrams.value.find((d) => d.id === diagramId)
  if (!diagram) return

  const newPinned = !diagram.is_pinned
  await savedDiagramsStore.pinDiagram(diagramId, newPinned)
}

// Toggle show all
function toggleShowAll(): void {
  showAll.value = !showAll.value
}

/** End workshop for this diagram (host only; clears canvas session if this diagram is open). */
async function handleTurnOffOnlineCollab(diagramId: string): Promise<void> {
  const ok = await savedDiagramsStore.stopDiagramOnlineCollab(diagramId)
  if (ok) {
    if (diagramId === savedDiagramsStore.activeDiagramId) {
      eventBus.emit('workshop:code-changed', { code: null, visibility: null })
    }
    notify.success(t('collab.ended'))
  } else {
    notify.error(t('collab.endFailed'))
  }
}
</script>

<template>
  <div
    class="diagram-history flex flex-1 min-h-0 flex-col border-t border-stone-200 relative overflow-hidden"
  >
    <!-- Header -->
    <div class="px-4 py-3 flex items-center justify-between">
      <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
        {{ t('sidebar.diagramHistory.title') }}
      </div>
      <div
        v-if="!isBlurred && diagrams.length > 0"
        class="text-xs text-stone-400"
      >
        {{ diagrams.length }}/{{ maxDiagrams }}
      </div>
    </div>

    <!-- Scrollable diagram list -->
    <ElScrollbar class="flex-1 px-4 pb-4">
      <div :class="isBlurred ? 'blur-sm pointer-events-none select-none' : ''">
        <!-- Loading State -->
        <div
          v-if="isLoading"
          class="flex items-center justify-center py-8"
        >
          <ElIcon class="animate-spin text-stone-400">
            <Loading />
          </ElIcon>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="diagrams.length === 0"
          class="text-center py-8"
        >
          <FileImage class="w-8 h-8 mx-auto mb-2 text-stone-300" />
          <p class="text-xs text-stone-400">
            {{ t('sidebar.diagramHistory.empty') }}
          </p>
          <p class="text-xs text-stone-300 mt-1">
            {{ t('sidebar.diagramHistory.capacity', { n: maxDiagrams }) }}
          </p>
        </div>

        <!-- Grouped Diagram List -->
        <template v-else>
          <!-- Top (Pinned) -->
          <div
            v-if="groupedDiagrams.pinned.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.pinned }}</div>
            <div
              v-for="diagram in groupedDiagrams.pinned"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  <Pin class="w-3 h-3 inline-block mr-1 text-amber-500" />
                  {{ diagram.title || t('mindmate.untitled') }}
                  <span
                    v-if="diagram.workshop_active"
                    class="collab-live-badge"
                    :title="t('sidebar.diagramHistory.collabLive')"
                  >
                    <Users class="w-2.5 h-2.5" />
                  </span>
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <button
                class="delete-btn"
                :title="t('sidebar.actions.delete')"
                @click.stop="handleDeleteDiagram(diagram.id)"
              >
                <Trash2 class="w-4 h-4" />
              </button>
              <ElDropdown
                trigger="click"
                placement="bottom-end"
                :popper-class="diagramMoreMenuPopperClass(diagram)"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu class="diagram-history-more__menu">
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Pin class="w-4 h-4 shrink-0 text-amber-500 rotate-45" />
                        {{ t('sidebar.actions.unpin') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Edit3 class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.rename') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      v-if="diagram.workshop_active"
                      @click="handleTurnOffOnlineCollab(diagram.id)"
                    >
                      <span class="diagram-history-more__row">
                        <Power class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.turnOffOnlineCollab') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="diagram-history-more__row diagram-history-more__row--danger">
                        <Trash2 class="w-4 h-4 shrink-0" />
                        {{ t('sidebar.actions.delete') }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Today -->
          <div
            v-if="groupedDiagrams.today.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.today }}</div>
            <div
              v-for="diagram in groupedDiagrams.today"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  {{ diagram.title || t('mindmate.untitled') }}
                  <span
                    v-if="diagram.workshop_active"
                    class="collab-live-badge"
                    :title="t('sidebar.diagramHistory.collabLive')"
                  >
                    <Users class="w-2.5 h-2.5" />
                  </span>
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <button
                class="delete-btn"
                :title="t('sidebar.actions.delete')"
                @click.stop="handleDeleteDiagram(diagram.id)"
              >
                <Trash2 class="w-4 h-4" />
              </button>
              <ElDropdown
                trigger="click"
                placement="bottom-end"
                :popper-class="diagramMoreMenuPopperClass(diagram)"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu class="diagram-history-more__menu">
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Pin class="w-4 h-4 shrink-0 text-amber-500" />
                        {{ t('sidebar.actions.pinToTop') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Edit3 class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.rename') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      v-if="diagram.workshop_active"
                      @click="handleTurnOffOnlineCollab(diagram.id)"
                    >
                      <span class="diagram-history-more__row">
                        <Power class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.turnOffOnlineCollab') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="diagram-history-more__row diagram-history-more__row--danger">
                        <Trash2 class="w-4 h-4 shrink-0" />
                        {{ t('sidebar.actions.delete') }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Yesterday -->
          <div
            v-if="groupedDiagrams.yesterday.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.yesterday }}</div>
            <div
              v-for="diagram in groupedDiagrams.yesterday"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  {{ diagram.title || t('mindmate.untitled') }}
                  <span
                    v-if="diagram.workshop_active"
                    class="collab-live-badge"
                    :title="t('sidebar.diagramHistory.collabLive')"
                  >
                    <Users class="w-2.5 h-2.5" />
                  </span>
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <button
                class="delete-btn"
                :title="t('sidebar.actions.delete')"
                @click.stop="handleDeleteDiagram(diagram.id)"
              >
                <Trash2 class="w-4 h-4" />
              </button>
              <ElDropdown
                trigger="click"
                placement="bottom-end"
                :popper-class="diagramMoreMenuPopperClass(diagram)"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu class="diagram-history-more__menu">
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Pin class="w-4 h-4 shrink-0 text-amber-500" />
                        {{ t('sidebar.actions.pinToTop') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Edit3 class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.rename') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      v-if="diagram.workshop_active"
                      @click="handleTurnOffOnlineCollab(diagram.id)"
                    >
                      <span class="diagram-history-more__row">
                        <Power class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.turnOffOnlineCollab') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="diagram-history-more__row diagram-history-more__row--danger">
                        <Trash2 class="w-4 h-4 shrink-0" />
                        {{ t('sidebar.actions.delete') }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Past Week -->
          <div
            v-if="groupedDiagrams.week.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.week }}</div>
            <div
              v-for="diagram in groupedDiagrams.week"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  {{ diagram.title || t('mindmate.untitled') }}
                  <span
                    v-if="diagram.workshop_active"
                    class="collab-live-badge"
                    :title="t('sidebar.diagramHistory.collabLive')"
                  >
                    <Users class="w-2.5 h-2.5" />
                  </span>
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <button
                class="delete-btn"
                :title="t('sidebar.actions.delete')"
                @click.stop="handleDeleteDiagram(diagram.id)"
              >
                <Trash2 class="w-4 h-4" />
              </button>
              <ElDropdown
                trigger="click"
                placement="bottom-end"
                :popper-class="diagramMoreMenuPopperClass(diagram)"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu class="diagram-history-more__menu">
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Pin class="w-4 h-4 shrink-0 text-amber-500" />
                        {{ t('sidebar.actions.pinToTop') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Edit3 class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.rename') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      v-if="diagram.workshop_active"
                      @click="handleTurnOffOnlineCollab(diagram.id)"
                    >
                      <span class="diagram-history-more__row">
                        <Power class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.turnOffOnlineCollab') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="diagram-history-more__row diagram-history-more__row--danger">
                        <Trash2 class="w-4 h-4 shrink-0" />
                        {{ t('sidebar.actions.delete') }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Past Month -->
          <div
            v-if="groupedDiagrams.month.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.month }}</div>
            <div
              v-for="diagram in groupedDiagrams.month"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  {{ diagram.title || t('mindmate.untitled') }}
                  <span
                    v-if="diagram.workshop_active"
                    class="collab-live-badge"
                    :title="t('sidebar.diagramHistory.collabLive')"
                  >
                    <Users class="w-2.5 h-2.5" />
                  </span>
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <button
                class="delete-btn"
                :title="t('sidebar.actions.delete')"
                @click.stop="handleDeleteDiagram(diagram.id)"
              >
                <Trash2 class="w-4 h-4" />
              </button>
              <ElDropdown
                trigger="click"
                placement="bottom-end"
                :popper-class="diagramMoreMenuPopperClass(diagram)"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu class="diagram-history-more__menu">
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Pin class="w-4 h-4 shrink-0 text-amber-500" />
                        {{ t('sidebar.actions.pinToTop') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <span class="diagram-history-more__row">
                        <Edit3 class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.rename') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      v-if="diagram.workshop_active"
                      @click="handleTurnOffOnlineCollab(diagram.id)"
                    >
                      <span class="diagram-history-more__row">
                        <Power class="w-4 h-4 shrink-0 text-stone-600" />
                        {{ t('sidebar.actions.turnOffOnlineCollab') }}
                      </span>
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="diagram-history-more__row diagram-history-more__row--danger">
                        <Trash2 class="w-4 h-4 shrink-0" />
                        {{ t('sidebar.actions.delete') }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Show More button -->
          <button
            v-if="hasMore"
            class="show-more-btn"
            @click="toggleShowAll"
          >
            {{ t('sidebar.actions.showMore', { n: remainingCount }) }}
          </button>

          <!-- Show Less button -->
          <button
            v-if="showAll && diagrams.length > INITIAL_LIMIT"
            class="show-more-btn"
            @click="toggleShowAll"
          >
            {{ t('sidebar.actions.showLess') }}
          </button>
        </template>
      </div>
    </ElScrollbar>

    <!-- Login overlay when blurred -->
    <div
      v-if="isBlurred"
      class="absolute inset-0 flex items-center justify-center bg-stone-50/60 backdrop-blur-[2px]"
    >
      <div class="text-center px-4">
        <div
          class="w-10 h-10 rounded-full bg-stone-100 flex items-center justify-center mx-auto mb-2"
        >
          <Lock class="w-5 h-5 text-stone-400" />
        </div>
        <p class="text-xs text-stone-500">
          {{ t('sidebar.diagramHistory.loginPrompt') }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diagram-history {
  min-height: 120px;
}

.group-section {
  margin-bottom: 12px;
}

.group-section:last-child {
  margin-bottom: 0;
}

.group-label {
  font-size: 11px;
  font-weight: 500;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  margin-bottom: 4px;
  padding-left: 2px;
}

.diagram-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  color: #57534e;
  font-size: 13px;
  text-align: left;
  transition: background-color 0.15s ease;
  cursor: pointer;
  border: none;
  background: transparent;
}

.diagram-item:hover {
  background-color: #f5f5f4;
}

.diagram-item.active {
  background-color: #e7e5e4;
  color: #1c1917;
}

.diagram-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.diagram-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.diagram-type {
  font-size: 10px;
  color: #a8a29e;
}

.delete-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  opacity: 0;
  color: #78716c;
  transition: all 0.15s ease;
  background: transparent;
  border: none;
  cursor: pointer;
  margin-right: 2px;
}

.diagram-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background-color: #fee2e2;
  color: #dc2626;
}

.more-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  opacity: 0;
  color: #78716c;
  transition: all 0.15s ease;
  background: transparent;
  border: none;
  cursor: pointer;
}

.diagram-item:hover .more-btn {
  opacity: 1;
}

.more-btn:hover {
  background-color: #e7e5e4;
  color: #1c1917;
}

.show-more-btn {
  display: block;
  width: 100%;
  padding: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: #78716c;
  text-align: center;
  background: transparent;
  border: 1px dashed #d6d3d1;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.show-more-btn:hover {
  background-color: #fafaf9;
  border-color: #a8a29e;
  color: #57534e;
}

/* Live collab indicator */
.collab-live-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background-color: #22c55e;
  color: #fff;
  margin-left: 4px;
  vertical-align: middle;
  flex-shrink: 0;
  animation: collab-pulse 2s ease-in-out infinite;
}

@keyframes collab-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.55);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(34, 197, 94, 0);
  }
}
</style>

<!-- Teleported dropdown — Swiss popper; width via --narrow / --wide (collab extras) -->
<style>
.diagram-history-more-popper.el-popper {
  min-width: 0 !important;
  box-sizing: border-box !important;
  padding: 3px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden !important;
}

/* Pin / rename / delete only — hugs content; cap for long translations */
.diagram-history-more-popper.diagram-history-more-popper--narrow.el-popper {
  width: max-content !important;
  max-width: min(calc(100vw - 24px), 260px) !important;
}

.diagram-history-more-popper.diagram-history-more-popper--narrow .diagram-history-more__row {
  white-space: nowrap;
  word-break: normal;
  align-items: center;
}

/* Includes long collab line — hug content up to max (no fixed empty rail) */
.diagram-history-more-popper.diagram-history-more-popper--wide.el-popper {
  width: max-content !important;
  max-width: min(calc(100vw - 24px), 172px) !important;
}

.diagram-history-more-popper.diagram-history-more-popper--wide .diagram-history-more__row {
  align-items: flex-start;
}

.diagram-history-more-popper .diagram-history-more__menu.el-dropdown-menu {
  min-width: 0 !important;
  width: max-content !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow-x: hidden !important;
  scrollbar-gutter: auto;
}

.diagram-history-more-popper .el-dropdown-menu__item {
  display: flex !important;
  min-width: 0 !important;
  box-sizing: border-box;
  width: auto !important;
  max-width: 100%;
  padding: 0 !important;
  margin: 0 !important;
  border-radius: 6px;
  justify-content: flex-start !important;
  transition:
    background 0.12s,
    color 0.12s;
}

.diagram-history-more-popper .el-dropdown-menu__item:hover,
.diagram-history-more-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4 !important;
  color: #1c1917;
}

.diagram-history-more-popper .el-dropdown-menu__item:active {
  background: #e7e5e4 !important;
}

.diagram-history-more-popper .el-dropdown-menu__item.is-divided {
  margin-top: 4px !important;
  border-top: 1px solid #e7e5e4 !important;
  padding-top: 0 !important;
}

.diagram-history-more-popper .diagram-history-more__row {
  display: inline-flex;
  align-items: flex-start;
  gap: 6px;
  box-sizing: border-box;
  width: auto;
  max-width: 100%;
  min-width: 0;
  padding: 6px 5px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  color: #44403c;
  letter-spacing: 0.01em;
  white-space: normal;
  word-break: break-word;
}

.diagram-history-more-popper.diagram-history-more-popper--wide .diagram-history-more__row svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.diagram-history-more-popper .el-dropdown-menu__item:hover .diagram-history-more__row,
.diagram-history-more-popper .el-dropdown-menu__item:focus .diagram-history-more__row {
  color: #1c1917;
}

.diagram-history-more-popper .diagram-history-more__row--danger,
.diagram-history-more-popper .el-dropdown-menu__item:hover .diagram-history-more__row--danger,
.diagram-history-more-popper .el-dropdown-menu__item:focus .diagram-history-more__row--danger {
  color: #dc2626;
}
</style>
