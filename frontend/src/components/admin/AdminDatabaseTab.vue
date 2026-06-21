<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ElMessageBox } from 'element-plus'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  useAdminDatabaseOrphans,
  useAdminDatabaseStats,
  useAnalyzeAdminDatabaseDump,
  useCleanupAdminDatabaseOrphans,
  useExportAdminDatabase,
  useImportAdminDatabaseDump,
  useMergeAdminDatabaseDump,
  useScanAdminDatabase,
} from '@/composables/queries'

interface BackupFile {
  name: string
  size_bytes: number
  modified_at: string
  manifest?: Record<string, unknown>
}

interface ScanResult {
  pg_dumps: BackupFile[]
}

interface PgStats {
  table_count: number
  column_count: number
  total_rows: number
  tables: Record<string, number>
}

interface PgDumpAnalysis {
  success: boolean
  matched_users: number
  new_users: number
  matched_orgs: number
  new_orgs: number
  staging_tables: Record<string, number>
  merge_tables: string[]
  skipped_tables: string[]
  per_table: Record<
    string,
    {
      staging_rows: number
      live_rows: number
      new_rows: number
      duplicate_rows: number
      orphaned_rows: number
    }
  >
}

interface PgDumpMergeResult {
  success: boolean
  tables: Record<string, { inserted: number; skipped: number; orphaned: number }>
  elapsed_seconds: number
  stats_recomputed_users?: number
  file_warning?: string
}

const { t } = useLanguage()
const notify = useNotifications()

const statsQuery = useAdminDatabaseStats()
const orphansQuery = useAdminDatabaseOrphans({ enabled: false })
const scanDatabase = useScanAdminDatabase()
const exportDatabase = useExportAdminDatabase()
const importDatabaseDump = useImportAdminDatabaseDump()
const analyzeDatabaseDump = useAnalyzeAdminDatabaseDump()
const mergeDatabaseDump = useMergeAdminDatabaseDump()
const cleanupDatabaseOrphans = useCleanupAdminDatabaseOrphans()

const isLoadingStats = ref(false)
const pgStats = ref<PgStats | null>(null)

const isScanning = ref(false)
const scanResult = ref<ScanResult | null>(null)

const isExporting = ref(false)
const isImporting = ref(false)

const selectedDump = ref<string | null>(null)
const isAnalyzingDump = ref(false)
const pgDumpAnalysis = ref<PgDumpAnalysis | null>(null)
const isMergingDump = ref(false)
const pgDumpMergeResult = ref<PgDumpMergeResult | null>(null)

const isDetectingOrphans = ref(false)
const orphans = ref<Record<string, number> | null>(null)
const isCleaningOrphans = ref(false)

const hasOrphans = computed(() => {
  if (!orphans.value) return false
  return Object.values(orphans.value).some((v) => v > 0)
})

const totalOrphans = computed(() => {
  if (!orphans.value) return 0
  return Object.values(orphans.value).reduce((s, v) => s + v, 0)
})

const sortedPgTables = computed(() => {
  if (!pgStats.value?.tables) return []
  return Object.entries(pgStats.value.tables)
    .sort(([, a], [, b]) => b - a)
    .map(([name, count]) => ({ name, count }))
})

const pgDumpAnalysisTableData = computed(() => {
  if (!pgDumpAnalysis.value?.per_table) return []
  return Object.entries(pgDumpAnalysis.value.per_table)
    .filter(([, v]) => v.staging_rows > 0)
    .sort(([, a], [, b]) => b.staging_rows - a.staging_rows)
    .map(([name, v]) => ({ name, ...v }))
})

const pgMergeResultTableData = computed(() => {
  if (!pgDumpMergeResult.value?.tables) return []
  return Object.entries(pgDumpMergeResult.value.tables)
    .filter(([, v]) => v.inserted > 0 || v.skipped > 0 || v.orphaned > 0)
    .sort(([, a], [, b]) => b.inserted - a.inserted)
    .map(([name, v]) => ({ name, ...v }))
})

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

async function loadStats() {
  isLoadingStats.value = true
  try {
    const result = await statsQuery.refetch()
    pgStats.value = (result.data as PgStats | undefined) ?? null
  } catch {
    notify.error(t('admin.database.statsError'))
  } finally {
    isLoadingStats.value = false
  }
}

async function scanBackup() {
  isScanning.value = true
  pgDumpAnalysis.value = null
  pgDumpMergeResult.value = null
  selectedDump.value = null
  try {
    scanResult.value = (await scanDatabase.mutateAsync()) as unknown as ScanResult
  } catch {
    notify.error(t('admin.database.scanError'))
  } finally {
    isScanning.value = false
  }
}

async function exportDump() {
  isExporting.value = true
  try {
    const result = (await exportDatabase.mutateAsync()) as unknown as {
      success: boolean
      filename?: string
    }
    if (result.success) {
      notify.success(t('admin.database.exportSuccess') + `: ${result.filename}`)
      scanBackup()
    } else {
      notify.error(t('admin.database.exportError'))
    }
  } catch {
    notify.error(t('admin.database.exportError'))
  } finally {
    isExporting.value = false
  }
}

async function importDump(filename: string) {
  try {
    await ElMessageBox.confirm(
      t('admin.database.importConfirmMsg'),
      t('admin.database.importConfirmTitle'),
      { confirmButtonText: t('admin.confirm'), cancelButtonText: t('admin.cancel'), type: 'error' }
    )
  } catch (err: unknown) {
    if (err === 'cancel' || err === 'close') return
    console.error('[AdminDB] ElMessageBox error:', err)
    return
  }

  isImporting.value = true
  try {
    const result = (await importDatabaseDump.mutateAsync({ filename })) as { success: boolean }
    if (result.success) {
      notify.success(t('admin.database.importSuccess'))
      loadStats()
    } else {
      notify.error(t('admin.database.importError'))
    }
  } catch (err: unknown) {
    console.error('[AdminDB] import error:', err)
    notify.error(t('admin.database.importError'))
  } finally {
    isImporting.value = false
  }
}

async function analyzeDump(filename: string) {
  selectedDump.value = filename
  isAnalyzingDump.value = true
  pgDumpAnalysis.value = null
  pgDumpMergeResult.value = null
  try {
    pgDumpAnalysis.value = (await analyzeDatabaseDump.mutateAsync({ filename })) as unknown as PgDumpAnalysis
  } catch (err: unknown) {
    console.error('[AdminDB] PG dump analyze error:', err)
    notify.error(t('admin.database.pgAnalyzeError'))
  } finally {
    isAnalyzingDump.value = false
  }
}

async function executePgMerge() {
  if (!selectedDump.value) return
  const filename = selectedDump.value

  try {
    await ElMessageBox.confirm(
      t('admin.database.pgMergeConfirmMsg'),
      t('admin.database.pgMergeConfirmTitle'),
      {
        confirmButtonText: t('admin.confirm'),
        cancelButtonText: t('admin.cancel'),
        type: 'warning',
      }
    )
  } catch (err: unknown) {
    if (err === 'cancel' || err === 'close') return
    console.error('[AdminDB] ElMessageBox error:', err)
    return
  }

  isMergingDump.value = true
  try {
    pgDumpMergeResult.value = (await mergeDatabaseDump.mutateAsync({ filename })) as unknown as PgDumpMergeResult
    notify.success(t('admin.database.pgMergeSuccess'))
    loadStats()
  } catch (err: unknown) {
    console.error('[AdminDB] PG dump merge error:', err)
    notify.error(t('admin.database.pgMergeError'))
  } finally {
    isMergingDump.value = false
  }
}

async function detectOrphans() {
  isDetectingOrphans.value = true
  try {
    const result = await orphansQuery.refetch()
    orphans.value = (result.data as Record<string, number> | undefined) ?? null
  } catch {
    notify.error(t('admin.database.orphanDetectError'))
  } finally {
    isDetectingOrphans.value = false
  }
}

async function cleanOrphans() {
  try {
    await ElMessageBox.confirm(
      t('admin.database.orphanCleanConfirmMsg'),
      t('admin.database.orphanCleanConfirmTitle'),
      {
        confirmButtonText: t('admin.confirm'),
        cancelButtonText: t('admin.cancel'),
        type: 'warning',
      }
    )
  } catch (err: unknown) {
    if (err === 'cancel' || err === 'close') return
    console.error('[AdminDB] ElMessageBox error:', err)
    return
  }

  isCleaningOrphans.value = true
  try {
    const result = (await cleanupDatabaseOrphans.mutateAsync({})) as Record<string, number>
    const total = Object.values(result).reduce((s, v) => s + v, 0)
    notify.success(`${t('admin.database.orphanCleanSuccess')}: ${total}`)
    detectOrphans()
    loadStats()
  } catch {
    notify.error(t('admin.database.orphanCleanError'))
  } finally {
    isCleaningOrphans.value = false
  }
}

onMounted(() => {
  loadStats()
  scanBackup()
})
</script>

<template>
  <div class="admin-database-tab space-y-6">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold">{{ t('admin.database.pgOverview') }}</span>
          <el-button
            size="small"
            :loading="isLoadingStats"
            @click="loadStats"
          >
            {{ t('admin.refresh') }}
          </el-button>
        </div>
      </template>

      <div
        v-if="pgStats"
        class="space-y-4"
      >
        <div class="grid grid-cols-3 gap-4">
          <AdminSwissKpiCard
            :title="t('admin.database.tables')"
            :value="pgStats.table_count"
            theme="neutral"
            compact
          />
          <AdminSwissKpiCard
            :title="t('admin.database.columns')"
            :value="pgStats.column_count"
            theme="neutral"
            compact
          />
          <AdminSwissKpiCard
            :title="t('admin.database.totalRows')"
            :value="pgStats.total_rows.toLocaleString()"
            theme="neutral"
            compact
          />
        </div>

        <el-table
          :data="sortedPgTables"
          size="small"
          max-height="300"
          stripe
        >
          <el-table-column
            prop="name"
            :label="t('admin.database.tableName')"
          />
          <el-table-column
            prop="count"
            :label="t('admin.database.rowCount')"
            width="140"
            align="right"
          >
            <template #default="{ row }">{{ row.count.toLocaleString() }}</template>
          </el-table-column>
        </el-table>
      </div>

      <el-skeleton
        v-else
        :rows="5"
        animated
      />
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold">{{ t('admin.database.pgExportImport') }}</span>
          <div class="flex gap-2">
            <el-button
              size="small"
              :loading="isScanning"
              @click="scanBackup"
            >
              {{ t('admin.database.scanBackup') }}
            </el-button>
            <el-button
              size="small"
              type="primary"
              :loading="isExporting"
              @click="exportDump"
            >
              {{ t('admin.database.exportNow') }}
            </el-button>
          </div>
        </div>
      </template>

      <p class="text-gray-500 text-sm mb-4">{{ t('admin.database.pgExportImportDesc') }}</p>

      <template v-if="scanResult && scanResult.pg_dumps.length > 0">
        <el-table
          :data="scanResult.pg_dumps"
          size="small"
          stripe
        >
          <el-table-column
            prop="name"
            :label="t('admin.database.fileName')"
          />
          <el-table-column
            :label="t('admin.database.fileSize')"
            width="120"
            align="right"
          >
            <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column
            :label="t('admin.database.modified')"
            width="180"
          >
            <template #default="{ row }">{{ formatDate(row.modified_at) }}</template>
          </el-table-column>
          <el-table-column
            :label="t('admin.actions')"
            width="240"
            align="center"
          >
            <template #default="{ row }">
              <div class="flex gap-1 justify-center">
                <el-button
                  size="small"
                  type="primary"
                  :loading="isAnalyzingDump && selectedDump === row.name"
                  @click="analyzeDump(row.name)"
                >
                  {{ t('admin.database.pgAnalyze') }}
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  :loading="isImporting"
                  @click="importDump(row.name)"
                >
                  {{ t('admin.database.restore') }}
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <div
        v-else-if="scanResult"
        class="text-gray-400 text-sm py-4 text-center"
      >
        {{ t('admin.database.noDumpFiles') }}
      </div>

      <template v-if="pgDumpAnalysis && !pgDumpMergeResult">
        <el-divider />
        <h4 class="font-medium mb-3">{{ t('admin.database.pgAnalysisResult') }}</h4>

        <div class="grid grid-cols-4 gap-3 mb-4">
          <AdminSwissKpiCard
            :title="t('admin.database.matchedUsers')"
            :value="pgDumpAnalysis.matched_users"
            theme="members"
            compact
          />
          <AdminSwissKpiCard
            :title="t('admin.database.newUsers')"
            :value="pgDumpAnalysis.new_users"
            theme="success"
            compact
          />
          <AdminSwissKpiCard
            :title="t('admin.database.matchedOrgs')"
            :value="pgDumpAnalysis.matched_orgs"
            theme="members"
            compact
          />
          <AdminSwissKpiCard
            :title="t('admin.database.newOrgs')"
            :value="pgDumpAnalysis.new_orgs"
            theme="success"
            compact
          />
        </div>

        <div
          v-if="pgDumpAnalysis.skipped_tables.length > 0"
          class="text-sm text-gray-500 mb-3"
        >
          {{ t('admin.database.pgSkippedTables') }}:
          <span class="font-mono">{{ pgDumpAnalysis.skipped_tables.join(', ') }}</span>
        </div>

        <el-table
          :data="pgDumpAnalysisTableData"
          size="small"
          max-height="360"
          stripe
        >
          <el-table-column
            prop="name"
            :label="t('admin.database.tableName')"
          />
          <el-table-column
            prop="staging_rows"
            :label="t('admin.database.pgStagingRows')"
            width="120"
            align="right"
          >
            <template #default="{ row }">{{ row.staging_rows.toLocaleString() }}</template>
          </el-table-column>
          <el-table-column
            prop="live_rows"
            :label="t('admin.database.pgLiveRows')"
            width="120"
            align="right"
          >
            <template #default="{ row }">{{ row.live_rows.toLocaleString() }}</template>
          </el-table-column>
          <el-table-column
            prop="new_rows"
            :label="t('admin.database.pgNewRows')"
            width="100"
            align="right"
          >
            <template #default="{ row }">
              <span class="text-green-600 font-medium">{{ row.new_rows.toLocaleString() }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="duplicate_rows"
            :label="t('admin.database.pgDuplicateRows')"
            width="110"
            align="right"
          >
            <template #default="{ row }">{{ row.duplicate_rows.toLocaleString() }}</template>
          </el-table-column>
          <el-table-column
            prop="orphaned_rows"
            :label="t('admin.database.pgOrphanedRows')"
            width="100"
            align="right"
          >
            <template #default="{ row }">
              <span :class="row.orphaned_rows ? 'text-orange-500' : ''">
                {{ row.orphaned_rows.toLocaleString() }}
              </span>
            </template>
          </el-table-column>
        </el-table>

        <div class="mt-4 flex justify-end">
          <el-button
            type="success"
            :loading="isMergingDump"
            @click="executePgMerge"
          >
            {{ t('admin.database.pgExecuteMerge') }}
          </el-button>
        </div>
      </template>

      <template v-if="pgDumpMergeResult">
        <el-divider />
        <el-result
          icon="success"
          :title="t('admin.database.pgMergeComplete')"
          :sub-title="`${pgDumpMergeResult.elapsed_seconds}s`"
        />

        <el-alert
          v-if="pgDumpMergeResult.file_warning"
          type="warning"
          :title="pgDumpMergeResult.file_warning"
          show-icon
          class="mb-4"
          :closable="false"
        />

        <p
          v-if="pgDumpMergeResult.stats_recomputed_users"
          class="text-sm text-gray-600 mb-3"
        >
          {{ t('admin.database.pgStatsRecomputed') }}:
          {{ pgDumpMergeResult.stats_recomputed_users }}
        </p>

        <el-table
          :data="pgMergeResultTableData"
          size="small"
          max-height="400"
          stripe
        >
          <el-table-column
            prop="name"
            :label="t('admin.database.tableName')"
          />
          <el-table-column
            :label="t('admin.database.inserted')"
            width="120"
            align="right"
          >
            <template #default="{ row }">
              <span class="text-green-600 font-medium">{{ row.inserted }}</span>
            </template>
          </el-table-column>
          <el-table-column
            :label="t('admin.database.skipped')"
            width="120"
            align="right"
          >
            <template #default="{ row }">{{ row.skipped }}</template>
          </el-table-column>
          <el-table-column
            :label="t('admin.database.orphaned')"
            width="120"
            align="right"
          >
            <template #default="{ row }">
              <span :class="row.orphaned ? 'text-orange-500' : ''">{{ row.orphaned ?? '-' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold">{{ t('admin.database.orphanCleanup') }}</span>
          <el-button
            size="small"
            :loading="isDetectingOrphans"
            @click="detectOrphans"
          >
            {{ t('admin.database.detectOrphans') }}
          </el-button>
        </div>
      </template>

      <p class="text-gray-500 text-sm mb-4">{{ t('admin.database.orphanCleanupDesc') }}</p>

      <template v-if="orphans !== null">
        <div
          v-if="!hasOrphans"
          class="text-green-600 text-sm py-2"
        >
          {{ t('admin.database.noOrphansFound') }}
        </div>

        <template v-else>
          <div class="space-y-1 mb-4">
            <div
              v-for="(count, label) in orphans"
              :key="label"
              class="text-sm flex justify-between max-w-md"
            >
              <span class="text-gray-600">{{ label }}</span>
              <span class="font-mono text-orange-600">{{ count }}</span>
            </div>
          </div>
          <div class="text-sm text-gray-500 mb-3">
            {{ t('admin.database.totalOrphans') }}:
            <strong class="text-orange-600">{{ totalOrphans }}</strong>
          </div>
          <el-button
            type="warning"
            :loading="isCleaningOrphans"
            @click="cleanOrphans"
          >
            {{ t('admin.database.cleanOrphans') }}
          </el-button>
        </template>
      </template>
    </el-card>
  </div>
</template>
