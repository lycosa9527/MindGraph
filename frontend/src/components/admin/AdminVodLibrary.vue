<script setup lang="ts">
import { ElTable, ElTableColumn } from 'element-plus'

import { useLanguage } from '@/composables'
import { formatVodDuration } from '@/composables/admin/vodMediaFormat'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import type { VodFolderItem, VodMediaItem } from '@/utils/vodApi'

defineProps<{
  items: VodMediaItem[]
  folders: VodFolderItem[]
  view: 'grid' | 'table'
  canEdit: boolean
}>()

const emit = defineEmits<{
  preview: [item: VodMediaItem]
  refresh: [item: VodMediaItem]
  delete: [item: VodMediaItem]
  move: [item: VodMediaItem, folderId: string | null]
}>()

const { t } = useLanguage()

function statusLabelKey(status: string): string {
  if (status === 'ready') return 'admin.vod.statusReady'
  if (status === 'failed') return 'admin.vod.statusFailed'
  if (status === 'pending') return 'admin.vod.statusPending'
  return 'admin.vod.statusProcessing'
}

function isVodMediaItem(row: unknown): row is VodMediaItem {
  if (typeof row !== 'object' || row === null) {
    return false
  }
  const rec = row as Record<string, unknown>
  return typeof rec.id === 'string' && typeof rec.file_id === 'string'
}

async function confirmDelete(item: VodMediaItem): Promise<void> {
  try {
    await swissGlassConfirm(String(t('admin.vod.deleteConfirm')), String(t('admin.vod.delete')), {
      type: 'warning',
    })
    emit('delete', item)
  } catch {
    return
  }
}

function refreshRow(row: unknown): void {
  if (isVodMediaItem(row)) {
    emit('refresh', row)
  }
}

function deleteRow(row: unknown): void {
  if (isVodMediaItem(row)) {
    void confirmDelete(row)
  }
}

function onMove(item: VodMediaItem, event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  emit('move', item, value || null)
}

function moveRow(row: unknown, event: Event): void {
  if (isVodMediaItem(row)) {
    onMove(row, event)
  }
}

function folderValue(row: unknown): string {
  if (!isVodMediaItem(row) || !row.folder_id) return ''
  return row.folder_id
}
</script>

<template>
  <div
    v-if="view === 'grid'"
    class="vod-grid"
  >
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="vod-card"
      @click="emit('preview', item)"
    >
      <div class="vod-card-cover">{{ formatVodDuration(item.duration_ms) }}</div>
      <div class="vod-card-body">
        <div class="vod-card-title">{{ item.title }}</div>
        <div class="vod-card-meta">
          <I18nText :k="statusLabelKey(item.status)" />
          <span v-if="item.owner_name"> · {{ item.owner_name }}</span>
        </div>
        <div
          v-if="canEdit"
          class="vod-card-actions"
          @click.stop
        >
          <button
            type="button"
            @click="emit('refresh', item)"
          >
            <I18nText k="admin.vod.refresh" />
          </button>
          <button
            type="button"
            @click="confirmDelete(item)"
          >
            <I18nText k="admin.vod.delete" />
          </button>
          <select
            class="vod-move"
            :aria-label="t('admin.vod.moveFolder')"
            :value="item.folder_id || ''"
            @change="onMove(item, $event)"
          >
            <option value=""><I18nText k="admin.vod.folderNone" /></option>
            <option
              v-for="folder in folders"
              :key="folder.id"
              :value="folder.id"
            >
              {{ folder.name }}
            </option>
          </select>
        </div>
      </div>
    </button>
  </div>
  <ElTable
    v-else
    :data="items"
    stripe
    @row-click="(row: VodMediaItem) => emit('preview', row)"
  >
    <ElTableColumn
      prop="title"
      min-width="180"
    >
      <template #header>
        <I18nText k="admin.vod.titleColumn" />
      </template>
    </ElTableColumn>
    <ElTableColumn min-width="110">
      <template #header>
        <I18nText k="admin.vod.status" />
      </template>
      <template #default="{ row }">
        <I18nText :k="statusLabelKey(row.status)" />
      </template>
    </ElTableColumn>
    <ElTableColumn min-width="90">
      <template #header>
        <I18nText k="admin.vod.duration" />
      </template>
      <template #default="{ row }">{{ formatVodDuration(row.duration_ms) }}</template>
    </ElTableColumn>
    <ElTableColumn
      prop="owner_name"
      min-width="120"
    >
      <template #header>
        <I18nText k="admin.vod.owner" />
      </template>
    </ElTableColumn>
    <ElTableColumn
      v-if="canEdit"
      width="160"
    >
      <template #header>
        <I18nText k="admin.vod.refresh" />
      </template>
      <template #default="{ row }">
        <button
          type="button"
          class="vod-link"
          @click.stop="refreshRow(row)"
        >
          <I18nText k="admin.vod.refresh" />
        </button>
        <button
          type="button"
          class="vod-link"
          @click.stop="deleteRow(row)"
        >
          <I18nText k="admin.vod.delete" />
        </button>
        <select
          class="vod-move"
          :aria-label="t('admin.vod.moveFolder')"
          :value="folderValue(row)"
          @click.stop
          @change="moveRow(row, $event)"
        >
          <option value=""><I18nText k="admin.vod.folderNone" /></option>
          <option
            v-for="folder in folders"
            :key="folder.id"
            :value="folder.id"
          >
            {{ folder.name }}
          </option>
        </select>
      </template>
    </ElTableColumn>
  </ElTable>
</template>

<style scoped>
.vod-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 1rem;
}
.vod-card {
  text-align: left;
  border: 1px solid #e7e5e4;
  border-radius: 0.75rem;
  overflow: hidden;
  background: #fff;
}
.vod-card-cover {
  height: 7.5rem;
  background: #1c1917;
  color: #e7e5e4;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  padding: 0.5rem 0.75rem;
  font-size: 0.75rem;
}
.vod-card-body {
  padding: 0.75rem;
}
.vod-card-title {
  font-weight: 600;
  color: #1c1917;
}
.vod-card-meta {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: #78716c;
}
.vod-card-actions {
  margin-top: 0.6rem;
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
}
.vod-link {
  color: #57534e;
  background: none;
  border: none;
  padding: 0;
  margin-right: 0.75rem;
}
.vod-move {
  margin-left: auto;
  max-width: 8rem;
  font-size: 0.75rem;
}
</style>
