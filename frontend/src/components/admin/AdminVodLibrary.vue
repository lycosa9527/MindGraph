<script setup lang="ts">
import { ElTable, ElTableColumn } from 'element-plus'

import { useLanguage } from '@/composables'
import { formatVodDuration } from '@/composables/admin/vodMediaFormat'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import type { VodMediaItem } from '@/utils/vodApi'

defineProps<{
  items: VodMediaItem[]
  view: 'grid' | 'table'
  canEdit: boolean
}>()

const emit = defineEmits<{
  preview: [item: VodMediaItem]
  refresh: [item: VodMediaItem]
  delete: [item: VodMediaItem]
}>()

const { t } = useLanguage()

function statusLabel(status: string): string {
  if (status === 'ready') return String(t('admin.vod.statusReady'))
  if (status === 'failed') return String(t('admin.vod.statusFailed'))
  if (status === 'pending') return String(t('admin.vod.statusPending'))
  return String(t('admin.vod.statusProcessing'))
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
          {{ statusLabel(item.status) }}
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
            {{ t('admin.vod.refresh') }}
          </button>
          <button
            type="button"
            @click="confirmDelete(item)"
          >
            {{ t('admin.vod.delete') }}
          </button>
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
      :label="t('admin.vod.titleColumn')"
      prop="title"
      min-width="180"
    />
    <ElTableColumn
      :label="t('admin.vod.status')"
      min-width="110"
    >
      <template #default="{ row }">{{ statusLabel(row.status) }}</template>
    </ElTableColumn>
    <ElTableColumn
      :label="t('admin.vod.duration')"
      min-width="90"
    >
      <template #default="{ row }">{{ formatVodDuration(row.duration_ms) }}</template>
    </ElTableColumn>
    <ElTableColumn
      :label="t('admin.vod.owner')"
      prop="owner_name"
      min-width="120"
    />
    <ElTableColumn
      v-if="canEdit"
      :label="t('admin.vod.refresh')"
      width="160"
    >
      <template #default="{ row }">
        <button
          type="button"
          class="vod-link"
          @click.stop="refreshRow(row)"
        >
          {{ t('admin.vod.refresh') }}
        </button>
        <button
          type="button"
          class="vod-link"
          @click.stop="deleteRow(row)"
        >
          {{ t('admin.vod.delete') }}
        </button>
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
</style>
