<script setup lang="ts">
/**
 * MindMate export — Dify raw dump upload, import, and snapshot management.
 */
import { computed, onMounted, ref } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  deleteMindMateExportDumpIncoming,
  deleteMindMateExportDumpSnapshot,
  fetchMindMateExportDumpInventory,
  importMindMateExportDumps,
  uploadMindMateExportDumpZip,
  type MindMateExportDumpInventory,
  type MindMateExportDumpSnapshotRow,
  type MindMateExportIncomingDumpRow,
} from '@/composables/queries'

const { t } = useLanguage()
const notify = useNotifications()

const loading = ref(false)
const uploading = ref(false)
const importing = ref(false)
const inventory = ref<MindMateExportDumpInventory | null>(null)

const incomingRows = computed(() => inventory.value?.incoming ?? [])
const difySnapshots = computed(() => inventory.value?.labels.dify?.snapshots ?? [])
const neodifySnapshots = computed(() => inventory.value?.labels.neodify?.snapshots ?? [])

const libraryBlocks = computed(() => [
  {
    label: 'dify' as const,
    library: inventory.value?.labels.dify?.library ?? null,
    titleKey: 'admin.mindmateExport.dumps.libraryDify',
  },
  {
    label: 'neodify' as const,
    library: inventory.value?.labels.neodify?.library ?? null,
    titleKey: 'admin.mindmateExport.dumps.libraryNeodify',
  },
])

const dataSourceLine = computed(() => {
  const summary = inventory.value?.data_source_summary?.per_label
  if (!summary) {
    return null
  }
  return Object.entries(summary)
    .map(([label, mode]) => {
      const modeLabel =
        mode === 'library'
          ? t('admin.mindmateExport.dumps.sourceLibrary')
          : mode === 'missing'
            ? t('admin.mindmateExport.dumps.sourceMissing')
            : mode
      return `${label}: ${modeLabel}`
    })
    .join(' · ')
})

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
  }
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${bytes} B`
}

function serverLabelText(label: string | null | undefined): string {
  if (label === 'dify') {
    return t('admin.mindmateExport.dumps.labelDify')
  }
  if (label === 'neodify') {
    return t('admin.mindmateExport.dumps.labelNeodify')
  }
  return label ?? '—'
}

function statusTagType(row: MindMateExportDumpSnapshotRow): 'success' | 'warning' | 'danger' {
  if (!row.usable) {
    return 'danger'
  }
  if (row.stale) {
    return 'warning'
  }
  return 'success'
}

async function refreshInventory(): Promise<void> {
  loading.value = true
  try {
    inventory.value = await fetchMindMateExportDumpInventory()
  } catch {
    notify.error(t('admin.mindmateExport.dumps.loadError'))
  } finally {
    loading.value = false
  }
}

async function handleUpload(options: { file: File }): Promise<void> {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', options.file)
    inventory.value = (await uploadMindMateExportDumpZip(formData)).inventory
    notify.success(t('admin.mindmateExport.dumps.uploadSuccess'))
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.mindmateExport.dumps.uploadError')
    notify.error(message)
  } finally {
    uploading.value = false
  }
}

function beforeUpload(file: File): boolean {
  const maxBytes = inventory.value?.max_upload_bytes
  if (maxBytes != null && file.size > maxBytes) {
    notify.error(
      t('admin.mindmateExport.dumps.uploadTooLarge', { limit: formatBytes(maxBytes) })
    )
    return false
  }
  return true
}

async function importAllPending(): Promise<void> {
  importing.value = true
  try {
    const result = await importMindMateExportDumps()
    inventory.value = result.inventory
    if (result.errors?.length) {
      notify.warning(t('admin.mindmateExport.dumps.importPartial'))
    } else {
      notify.success(t('admin.mindmateExport.dumps.importSuccess'))
    }
  } catch {
    notify.error(t('admin.mindmateExport.dumps.importError'))
  } finally {
    importing.value = false
  }
}

async function importOne(row: MindMateExportIncomingDumpRow): Promise<void> {
  importing.value = true
  try {
    const result = await importMindMateExportDumps([row.name])
    inventory.value = result.inventory
    if (result.errors?.length) {
      notify.warning(result.errors.join('; '))
    } else {
      notify.success(t('admin.mindmateExport.dumps.importSuccess'))
    }
  } catch {
    notify.error(t('admin.mindmateExport.dumps.importError'))
  } finally {
    importing.value = false
  }
}

async function removeIncoming(row: MindMateExportIncomingDumpRow): Promise<void> {
  try {
    const result = await deleteMindMateExportDumpIncoming(row.name)
    inventory.value = result.inventory
    notify.success(t('admin.mindmateExport.dumps.deleteSuccess'))
  } catch {
    notify.error(t('admin.mindmateExport.dumps.deleteError'))
  }
}

async function removeSnapshot(label: string, row: MindMateExportDumpSnapshotRow): Promise<void> {
  try {
    const result = await deleteMindMateExportDumpSnapshot(label, row.timestamp)
    inventory.value = result.inventory
    notify.success(t('admin.mindmateExport.dumps.deleteSuccess'))
  } catch {
    notify.error(t('admin.mindmateExport.dumps.deleteError'))
  }
}

onMounted(() => {
  void refreshInventory()
})
</script>

<template>
  <div
    v-loading="loading"
    class="mindmate-export-dumps"
  >
    <p class="mindmate-export-dumps-intro">
      {{ t('admin.mindmateExport.dumps.intro') }}
    </p>
    <p
      v-if="dataSourceLine"
      class="mindmate-export-meta-line"
    >
      {{ t('admin.mindmateExport.dataSource', { summary: dataSourceLine }) }}
    </p>
    <p class="mindmate-export-dumps-root">
      {{ t('admin.mindmateExport.dumps.rootPath', { path: inventory?.dump_root ?? '…' }) }}
    </p>

    <section
      v-for="block in libraryBlocks"
      :key="block.label"
      class="mindmate-export-card mindmate-export-dumps-library"
    >
      <h3 class="mindmate-export-subtitle">
        {{ t(block.titleKey) }}
      </h3>
      <p
        v-if="!block.library"
        class="mindmate-export-dumps-empty"
      >
        {{ t('admin.mindmateExport.dumps.libraryEmpty') }}
      </p>
      <dl
        v-else
        class="mindmate-export-library-stats"
      >
        <div>
          <dt>{{ t('admin.mindmateExport.dumps.libraryMergedSnapshots') }}</dt>
          <dd>{{ block.library.merged_snapshot_count }}</dd>
        </div>
        <div>
          <dt>{{ t('admin.mindmateExport.dumps.colMessages') }}</dt>
          <dd>{{ block.library.message_rows }}</dd>
        </div>
        <div>
          <dt>{{ t('admin.mindmateExport.dumps.libraryConversations') }}</dt>
          <dd>{{ block.library.conversation_rows }}</dd>
        </div>
        <div>
          <dt>{{ t('admin.mindmateExport.dumps.libraryLastMerged') }}</dt>
          <dd>{{ block.library.last_merged_at ?? '—' }}</dd>
        </div>
      </dl>
      <p
        v-if="block.library"
        class="mindmate-export-dumps-library-note"
      >
        {{ t('admin.mindmateExport.dumps.librarySearchNote') }}
      </p>
    </section>

    <section class="mindmate-export-card mindmate-export-dumps-upload">
      <h3 class="mindmate-export-subtitle">
        {{ t('admin.mindmateExport.dumps.uploadTitle') }}
      </h3>
      <el-upload
        drag
        multiple
        accept=".zip"
        :show-file-list="false"
        :disabled="uploading || importing"
        :before-upload="beforeUpload"
        :http-request="handleUpload"
      >
        <div class="mindmate-export-dumps-drop">
          <p>{{ t('admin.mindmateExport.dumps.uploadHint') }}</p>
          <p class="mindmate-export-dumps-drop-sub">
            {{ t('admin.mindmateExport.dumps.uploadFormats') }}
          </p>
        </div>
      </el-upload>
    </section>

    <section class="mindmate-export-card">
      <div class="mindmate-export-dumps-section-head">
        <h3 class="mindmate-export-subtitle">
          {{ t('admin.mindmateExport.dumps.incomingTitle') }}
        </h3>
        <div class="mindmate-export-dumps-actions">
          <el-button
            class="admin-swiss-btn"
            :loading="loading"
            @click="refreshInventory"
          >
            {{ t('admin.mindmateExport.dumps.refresh') }}
          </el-button>
          <el-button
            type="primary"
            class="admin-swiss-btn admin-swiss-btn--primary"
            :disabled="incomingRows.length === 0"
            :loading="importing"
            @click="importAllPending"
          >
            {{ t('admin.mindmateExport.dumps.importAll') }}
          </el-button>
        </div>
      </div>
      <p
        v-if="incomingRows.length === 0"
        class="mindmate-export-dumps-empty"
      >
        {{ t('admin.mindmateExport.dumps.incomingEmpty') }}
      </p>
      <el-table
        v-else
        :data="incomingRows"
        size="small"
        class="mindmate-export-dumps-table"
      >
        <el-table-column
          prop="name"
          :label="t('admin.mindmateExport.dumps.colFile')"
          min-width="200"
        />
        <el-table-column
          :label="t('admin.mindmateExport.dumps.colServer')"
          width="120"
        >
          <template #default="{ row }">
            {{ serverLabelText(row.server_label) }}
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.mindmateExport.dumps.colSize')"
          width="100"
        >
          <template #default="{ row }">
            {{ formatBytes(row.bytes) }}
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.mindmateExport.dumps.colActions')"
          width="180"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="importing || !!row.peek_error"
              @click="importOne(row)"
            >
              {{ t('admin.mindmateExport.dumps.importOne') }}
            </el-button>
            <el-button
              link
              type="danger"
              @click="removeIncoming(row)"
            >
              {{ t('admin.mindmateExport.dumps.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section
      v-for="block in [
        { label: 'dify', rows: difySnapshots, titleKey: 'admin.mindmateExport.dumps.archiveDify' },
        { label: 'neodify', rows: neodifySnapshots, titleKey: 'admin.mindmateExport.dumps.archiveNeodify' },
      ]"
      :key="block.label"
      class="mindmate-export-card"
    >
      <h3 class="mindmate-export-subtitle">
        {{ t(block.titleKey) }}
      </h3>
      <p
        v-if="block.rows.length === 0"
        class="mindmate-export-dumps-empty"
      >
        {{ t('admin.mindmateExport.dumps.snapshotsEmpty') }}
      </p>
      <el-table
        v-else
        :data="block.rows"
        size="small"
        class="mindmate-export-dumps-table"
      >
        <el-table-column
          prop="timestamp"
          :label="t('admin.mindmateExport.dumps.colSnapshot')"
          min-width="180"
        />
        <el-table-column
          :label="t('admin.mindmateExport.dumps.colStatus')"
          width="120"
        >
          <template #default="{ row }">
            <el-tag
              :type="statusTagType(row)"
              size="small"
            >
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="message_rows"
          :label="t('admin.mindmateExport.dumps.colMessages')"
          width="100"
        />
        <el-table-column
          :label="t('admin.mindmateExport.dumps.colActions')"
          width="100"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              link
              type="danger"
              @click="removeSnapshot(block.label, row)"
            >
              {{ t('admin.mindmateExport.dumps.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.mindmate-export-dumps-intro {
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1.5;
}

.mindmate-export-dumps-root {
  margin: 0 0 16px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  word-break: break-all;
}

.mindmate-export-dumps-upload {
  margin-bottom: 16px;
}

.mindmate-export-dumps-drop {
  padding: 24px 12px;
}

.mindmate-export-dumps-drop-sub {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.mindmate-export-dumps-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.mindmate-export-dumps-section-head .mindmate-export-subtitle {
  margin: 0;
}

.mindmate-export-dumps-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.mindmate-export-library-stats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr));
  gap: 0.75rem 1.25rem;
  margin: 0;
}

.mindmate-export-library-stats div {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.mindmate-export-library-stats dt {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--swiss-muted, #78716c);
}

.mindmate-export-library-stats dd {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--swiss-ink, #1c1917);
}

.mindmate-export-dumps-library-note {
  margin: 0.75rem 0 0;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: var(--swiss-muted, #78716c);
}

.mindmate-export-dumps-empty {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.mindmate-export-dumps-table {
  width: 100%;
}
</style>
