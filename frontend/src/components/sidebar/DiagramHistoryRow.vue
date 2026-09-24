<script setup lang="ts">
import { computed, ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import {
  Edit3,
  FolderInput,
  FolderMinus,
  FolderPlus,
  MoreHorizontal,
  Pin,
  Power,
  Share2,
  Trash2,
  Users,
} from '@lucide/vue'

import DiagramShareDialog from '@/components/sidebar/DiagramShareDialog.vue'
import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { promptSwissGlassName } from '@/composables/sidebar/promptSwissGlassName'
import { useAuthStore } from '@/stores'
import {
  type DiagramFolder,
  type SavedDiagram,
  useSavedDiagramsStore,
} from '@/stores/savedDiagrams'

const props = defineProps<{
  diagram: SavedDiagram
  isActive: boolean
  showPinnedIcon?: boolean
  folders: DiagramFolder[]
  createFolder?: () => Promise<string | null>
}>()

const emit = defineEmits<{
  (e: 'select', diagram: SavedDiagram): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const shareOpen = ref(false)
const isRecipient = computed(() => props.diagram.share_role === 'recipient')
const canShare = computed(() => Boolean(authStore.user?.schoolId) && !isRecipient.value)

function getDiagramTypeLabel(type: string): string {
  const key = `sidebar.diagramType.${type}`
  const translated = t(key)
  if (translated !== key) {
    return translated
  }
  return type
}

function diagramMoreMenuPopperClass(diagram: SavedDiagram): string {
  return diagram.workshop_active
    ? 'diagram-history-more-popper diagram-history-more-popper--wide'
    : 'diagram-history-more-popper diagram-history-more-popper--narrow'
}

function handleClick(): void {
  emit('select', props.diagram)
}

async function handleDelete(): Promise<void> {
  if (isRecipient.value) {
    const removed = await savedDiagramsStore.removeSharedDiagram(props.diagram.id)
    if (removed) {
      notify.success(t('sidebar.share.removed'))
    } else {
      notify.error(t('sidebar.share.removeFailed'))
    }
    return
  }
  const success = await savedDiagramsStore.deleteDiagram(props.diagram.id)
  if (success) {
    notify.success(t('sidebar.diagramHistory.deleted'))
  } else {
    notify.error(t('sidebar.diagramHistory.deleteFailed'))
  }
}

async function handlePin(): Promise<void> {
  await savedDiagramsStore.pinDiagram(props.diagram.id, !props.diagram.is_pinned)
}

async function handleRename(): Promise<void> {
  const currentName = props.diagram.title || ''
  const name = await promptSwissGlassName(
    t,
    'sidebar.diagramHistory.renameTitle',
    'sidebar.diagramHistory.renamePrompt',
    'sidebar.diagramHistory.title',
    currentName
  )
  if (!name || name === currentName) return
  await savedDiagramsStore.updateDiagram(props.diagram.id, { title: name })
}

async function handleTurnOffCollab(): Promise<void> {
  const ok = await savedDiagramsStore.stopDiagramOnlineCollab(props.diagram.id)
  if (ok) {
    if (props.diagram.id === savedDiagramsStore.activeDiagramId) {
      eventBus.emit('workshop:code-changed', { code: null, visibility: null })
    }
    notify.success(t('collab.ended'))
  } else {
    notify.error(t('collab.endFailed'))
  }
}

async function handleMoveToFolder(folderId: string | null): Promise<void> {
  const ok = await savedDiagramsStore.moveDiagramToFolder(props.diagram.id, folderId)
  if (ok) {
    notify.success(
      folderId
        ? t('sidebar.diagramHistory.movedToFolder')
        : t('sidebar.diagramHistory.removedFromFolder')
    )
  } else {
    const detail = savedDiagramsStore.error
    notify.error(detail || t('sidebar.diagramHistory.moveFailed'))
  }
}

async function handleCreateFolderAndMove(): Promise<void> {
  if (!props.createFolder) return
  const folderId = await props.createFolder()
  if (folderId) {
    await handleMoveToFolder(folderId)
  }
}
</script>

<template>
  <div
    class="diagram-item"
    :class="{ active: isActive }"
    @click="handleClick"
  >
    <div class="diagram-info">
      <span class="diagram-name">
        <Pin
          v-if="showPinnedIcon && diagram.is_pinned"
          class="w-3 h-3 inline-block mr-1 text-amber-500"
          :class="{ 'rotate-45': showPinnedIcon }"
        />
        {{ diagram.title || t('mindmate.untitled') }}
        <span
          v-if="diagram.shared"
          class="inline-flex items-center ml-1 text-sky-600"
          :title="t('sidebar.share.icon')"
        >
          <Share2 class="w-2.5 h-2.5" />
        </span>
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
    <ElDropdown
      trigger="click"
      placement="bottom-end"
      popper-class="diagram-history-folder-submenu diagram-history-folder-popper"
      class="folder-dropdown"
      @click.stop
    >
      <button
        class="folder-btn"
        :title="t('sidebar.actions.moveToFolder')"
        @click.stop
      >
        <FolderInput class="w-4 h-4" />
      </button>
      <template #dropdown>
        <ElDropdownMenu>
          <ElDropdownItem
            v-if="diagram.folder_id"
            @click.stop="handleMoveToFolder(null)"
          >
            <span class="diagram-history-more__row">
              <FolderMinus class="w-4 h-4 shrink-0 text-stone-600" />
              {{ t('sidebar.actions.removeFromFolder') }}
            </span>
          </ElDropdownItem>
          <ElDropdownItem
            v-for="folder in folders"
            :key="folder.id"
            :disabled="diagram.folder_id === folder.id"
            @click.stop="handleMoveToFolder(folder.id)"
          >
            {{ folder.name }}
          </ElDropdownItem>
          <ElDropdownItem
            divided
            @click.stop="handleCreateFolderAndMove"
          >
            <span class="diagram-history-more__row">
              <FolderPlus class="w-4 h-4 shrink-0 text-stone-600" />
              {{ t('sidebar.diagramHistory.createFolderAndMove') }}
            </span>
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>
    <button
      class="delete-btn"
      :title="isRecipient ? t('sidebar.actions.removeFromLibrary') : t('sidebar.actions.delete')"
      @click.stop="handleDelete"
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
          <ElDropdownItem @click="handlePin">
            <span class="diagram-history-more__row">
              <Pin
                class="w-4 h-4 shrink-0 text-amber-500"
                :class="{ 'rotate-45': diagram.is_pinned }"
              />
              {{ diagram.is_pinned ? t('sidebar.actions.unpin') : t('sidebar.actions.pinToTop') }}
            </span>
          </ElDropdownItem>
          <ElDropdownItem @click="handleRename">
            <span class="diagram-history-more__row">
              <Edit3 class="w-4 h-4 shrink-0 text-stone-600" />
              {{ t('sidebar.actions.rename') }}
            </span>
          </ElDropdownItem>
          <ElDropdownItem
            v-if="canShare"
            @click="shareOpen = true"
          >
            <span class="diagram-history-more__row">
              <Share2 class="w-4 h-4 shrink-0 text-sky-600" />
              {{ t('sidebar.actions.share') }}
            </span>
          </ElDropdownItem>
          <ElDropdownItem
            v-if="diagram.workshop_active"
            @click="handleTurnOffCollab"
          >
            <span class="diagram-history-more__row">
              <Power class="w-4 h-4 shrink-0 text-stone-600" />
              {{ t('sidebar.actions.turnOffOnlineCollab') }}
            </span>
          </ElDropdownItem>
          <ElDropdownItem
            divided
            @click="handleDelete"
          >
            <span class="diagram-history-more__row diagram-history-more__row--danger">
              <Trash2 class="w-4 h-4 shrink-0" />
              {{
                isRecipient ? t('sidebar.actions.removeFromLibrary') : t('sidebar.actions.delete')
              }}
            </span>
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>
    <DiagramShareDialog
      v-model="shareOpen"
      :diagram-id="diagram.id"
    />
  </div>
</template>

<style scoped>
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

.folder-btn {
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

.diagram-item:hover .delete-btn,
.diagram-item:hover .folder-btn {
  opacity: 1;
}

.folder-btn:hover {
  background-color: #fef3c7;
  color: #b45309;
}

.folder-dropdown {
  flex-shrink: 0;
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
