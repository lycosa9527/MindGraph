<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ElMessageBox } from 'element-plus'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

// ── types ────────────────────────────────────────────────────────────

interface BackupFile {
  name: string
  size_bytes: number
  modified_at: string
  manifest?: Record<string, unknown>
}

interface ScanResult {
  sqlite: BackupFile[]
  pg_dumps: BackupFile[]
}

interface AnalysisResult {
  sqlite_tables: Record<string, number>
  orphans: Record<string, number>
  user_mapping: Record<string, number>
  org_mapping: Record<string, number>
  new_users: number
  matched_users: number
  new_orgs: number
  matched_orgs: number
  skipped_tables: string[]
  merge_preview: Record<string, { total: number; new: number; skip: number }>
}

interface MergeResult {
  tables: Record<string, { inserted: number; skipped: number; orphaned?: number; rejected?: number }>
  elapsed_seconds: number
}

interface PgStats {
  table_count: number
  column_count: number
  total_rows: number
  tables: Record<string, number>
}

// ── composables ──────────────────────────────────────────────────────

const { t } = useLanguage()
const notify = useNotifications()

// ── state ────────────────────────────────────────────────────────────

const isLoadingStats = ref(false)
const pgStats = ref<PgStats | null>(null)

const isScanning = ref(false)
const scanResult = ref<ScanResult | null>(null)

const selectedSqlite = ref<string | null>(null)
const isAnalyzing = ref(false)
const analysis = ref<AnalysisResult | null>(null)

const isCleaningSqliteOrphans = ref(false)

const isMerging = ref(false)
const mergeResult = ref<MergeResult | null>(null)

const isExporting = ref(false)
const isImporting = ref(false)

const isDetectingOrphans = ref(false)
const orphans = ref<Record<string, number> | null>(null)
const isCleaningOrphans = ref(false)

// ── computed ─────────────────────────────────────────────────────────

const hasSqliteOrphans = computed(() => {
  if (!analysis.value?.orphans) return false
  return Object.values(analysis.value.orphans).some((v) => v > 0)
})

const totalSqliteOrphans = computed(() => {
  if (!analysis.value?.orphans) return 0
  return Object.values(analysis.value.orphans).reduce((s, v) => s + v, 0)
})

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

// ── helpers ──────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

// ── API calls ────────────────────────────────────────────────────────

async function loadStats() {
  isLoadingStats.value = true
  try {
    const response = await apiRequest('/api/auth/admin/database/stats')
    if (!response.ok) throw new Error('stats request failed')
    pgStats.value = (await response.json()) as PgStats
  } catch {
    notify.error(t('admin.database.statsError'))
  } finally {
    isLoadingStats.value = false
  }
}

async function scanBackup() {
  isScanning.value = true
  analysis.value = null
  mergeResult.value = null
  selectedSqlite.value = null
  try {
    const response = await apiRequest('/api/auth/admin/database/scan')
    if (!response.ok) throw new Error('scan request failed')
    scanResult.value = (await response.json()) as ScanResult
  } catch {
    notify.error(t('admin.database.scanError'))
  } finally {
    isScanning.value = false
  }
}

async function analyzeSqlite(filename: string) {
  selectedSqlite.value = filename
  isAnalyzing.value = true
  analysis.value = null
  mergeResult.value = null
  try {
    const response = await apiRequest('/api/auth/admin/database/analyze', {
      method: 'POST',
      body: JSON.stringify({ filename }),
    })
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail = body?.detail ?? response.statusText
      notify.error(`${t('admin.database.analyzeError')}: ${detail}`)
      return
    }
    analysis.value = (await response.json()) as AnalysisResult
  } catch (err: unknown) {
    console.error('[AdminDB] analyze error:', err)
    notify.error(t('admin.database.analyzeError'))
  } finally {
    isAnalyzing.value = false
  }
}

async function cleanSqliteOrphans() {
  if (!selectedSqlite.value) return
  const filename = selectedSqlite.value

  try {
    await ElMessageBox.confirm(
      `Delete ${totalSqliteOrphans.value} orphaned records from the SQLite file? This modifies the file on disk.`,
      'Clean SQLite Orphans',
      { confirmButtonText: t('admin.confirm'), cancelButtonText: t('admin.cancel'), type: 'warning' },
    )
  } catch (err: unknown) {
    if (err === 'cancel' || err === 'close') return
    console.error('[AdminDB] ElMessageBox error:', err)
    return
  }

  isCleaningSqliteOrphans.value = true
  try {
    const response = await apiRequest('/api/auth/admin/database/cleanup-sqlite-orphans', {
      method: 'POST',
      body: JSON.stringify({ filename }),
    })
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail = body?.detail ?? response.statusText
      notify.error(`Cleanup failed: ${detail}`)
      return
    }
    const result = (await response.json()) as Record<string, number>
    const total = Object.values(result).reduce((s, v) => s + v, 0)
    notify.success(`Cleaned ${total} orphaned records from SQLite`)
    await analyzeSqlite(filename)
  } catch (err: unknown) {
    console.error('[AdminDB] SQLite orphan cleanup error:', err)
    notify.error('SQLite orphan cleanup failed')
  } finally {
    isCleaningSqliteOrphans.value = false
  }
}

async function executeMerge() {
  if (!selectedSqlite.value) return
  const filename = selectedSqlite.value

  try {
    await ElMessageBox.confirm(
      t('admin.database.mergeConfirmMsg'),
      t('admin.database.mergeConfirmTitle'),
      { confirmButtonText: t('admin.confirm'), cancelButtonText: t('admin.cancel'), type: 'warning' },
    )
  } catch (err: unknown) {
    if (err === 'cancel' || err === 'close') return
    console.error('[AdminDB] ElMessageBox error:', err)
    return
  }

  isMerging.value = true
  try {
    const response = await apiRequest('/api/auth/admin/database/merge', {
      method: 'POST',
      body: JSON.stringify({ filename }),
    })
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail = body?.detail ?? response.statusText
      notify.error(`${t('admin.database.mergeError')}: ${detail}`)
      return
    }
    mergeResult.value = (await response.json()) as MergeResult
    notify.success(t('admin.database.mergeSuccess'))
    loadStats()
  } catch (err: unknown) {
    console.error('[AdminDB] merge error:', err)
    notify.error(t('admin.database.mergeError'))
  } finally {
    isMerging.value = false
  }
}

async function exportDump() {
  isExporting.value = true
  try {
    const response = await apiRequest('/api/auth/admin/database/export', { method: 'POST' })
    if (!response.ok) throw new Error('export request failed')
    const result = (await response.json()) as { success: boolean; filename?: string }
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
      { confirmButtonText: t('admin.confirm'), cancelButtonText: t('admin.cancel'), type: 'error' },
    )
  } catch (err: unknown) {
    if (err === 'cancel' || err === 'close') return
    console.error('[AdminDB] ElMessageBox error:', err)
    return
  }

  isImporting.value = true
  try {
    const response = await apiRequest('/api/auth/admin/database/import-dump', {
      method: 'POST',
      body: JSON.stringify({ filename }),
    })
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail = body?.detail ?? response.statusText
      notify.error(`${t('admin.database.importError')}: ${detail}`)
      return
    }
    const result = (await response.json()) as { success: boolean }
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

async function detectOrphans() {
  isDetectingOrphans.value = true
  try {
    const response = await apiRequest('/api/auth/admin/database/orphans')
    if (!response.ok) throw new Error('orphan detect failed')
    orphans.value = (await response.json()) as Record<string, number>
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
      { confirmButtonText: t('admin.confirm'), cancelButtonText: t('admin.cancel'), type: 'warning' },
    )
  } catch (err: unknown) {
    if (err === 'cancel' || err === 'close') return
    console.error('[AdminDB] ElMessageBox error:', err)
    return
  }

  isCleaningOrphans.value = true
  try {
    const response = await apiRequest('/api/auth/admin/database/cleanup-orphans', { method: 'POST' })
    if (!response.ok) throw new Error('orphan cleanup failed')
    const result = (await response.json()) as Record<string, number>
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

// ── lifecycle ────────────────────────────────────────────────────────

onMounted(() => {
  loadStats()
})
</script>

<template>
  <div class="admin-database-tab space-y-6">
    <!-- ═══ Section 1: DB Overview ═══ -->
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
          <div class="stat-card">
            <div class="stat-value">{{ pgStats.table_count }}</div>
            <div class="stat-label">{{ t('admin.database.tables') }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ pgStats.column_count }}</div>
            <div class="stat-label">{{ t('admin.database.columns') }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ pgStats.total_rows.toLocaleString() }}</div>
            <div class="stat-label">{{ t('admin.database.totalRows') }}</div>
          </div>
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

    <!-- ═══ Section 2: SQLite Merge ═══ -->
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold">{{ t('admin.database.sqliteMerge') }}</span>
          <el-button
            size="small"
            :loading="isScanning"
            @click="scanBackup"
          >
            {{ t('admin.database.scanBackup') }}
          </el-button>
        </div>
      </template>

      <p class="text-gray-500 text-sm mb-4">{{ t('admin.database.sqliteMergeDesc') }}</p>

      <!-- file list -->
      <template v-if="scanResult">
        <div
          v-if="scanResult.sqlite.length === 0"
          class="text-gray-400 text-sm py-4 text-center"
        >
          {{ t('admin.database.noSqliteFiles') }}
        </div>

        <el-table
          v-else
          :data="scanResult.sqlite"
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
            width="120"
            align="center"
          >
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                :loading="isAnalyzing && selectedSqlite === row.name"
                @click="analyzeSqlite(row.name)"
              >
                {{ t('admin.database.analyze') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <!-- analysis result -->
      <template v-if="analysis && !mergeResult">
        <el-divider />
        <h4 class="font-medium mb-3">{{ t('admin.database.analysisResult') }}</h4>

        <!-- summary cards -->
        <div class="grid grid-cols-4 gap-3 mb-4">
          <div class="stat-card stat-card-sm">
            <div class="stat-value text-blue-600">{{ analysis.matched_users }}</div>
            <div class="stat-label">{{ t('admin.database.matchedUsers') }}</div>
          </div>
          <div class="stat-card stat-card-sm">
            <div class="stat-value text-green-600">{{ analysis.new_users }}</div>
            <div class="stat-label">{{ t('admin.database.newUsers') }}</div>
          </div>
          <div class="stat-card stat-card-sm">
            <div class="stat-value text-blue-600">{{ analysis.matched_orgs }}</div>
            <div class="stat-label">{{ t('admin.database.matchedOrgs') }}</div>
          </div>
          <div class="stat-card stat-card-sm">
            <div class="stat-value text-green-600">{{ analysis.new_orgs }}</div>
            <div class="stat-label">{{ t('admin.database.newOrgs') }}</div>
          </div>
        </div>

        <!-- orphans -->
        <div
          v-if="Object.keys(analysis.orphans).length > 0"
          class="mb-4"
        >
          <h5 class="text-sm font-medium text-orange-600 mb-2">{{ t('admin.database.orphansFound') }}</h5>
          <div
            v-for="(count, label) in analysis.orphans"
            :key="label"
            class="text-sm text-gray-600"
          >
            {{ label }}: <span class="font-mono text-orange-600">{{ count }}</span>
          </div>
          <el-button
            v-if="hasSqliteOrphans"
            type="warning"
            size="small"
            class="mt-2"
            :loading="isCleaningSqliteOrphans"
            @click="cleanSqliteOrphans"
          >
            {{ t('admin.database.cleanSqliteOrphans') }} ({{ totalSqliteOrphans }})
          </el-button>
        </div>

        <!-- per-table preview -->
        <el-table
          :data="Object.entries(analysis.merge_preview).map(([name, v]) => ({ name, ...v }))"
          size="small"
          stripe
        >
          <el-table-column
            prop="name"
            :label="t('admin.database.tableName')"
          />
          <el-table-column
            prop="total"
            :label="t('admin.database.sqliteTotal')"
            width="120"
            align="right"
          >
            <template #default="{ row }">{{ row.total.toLocaleString() }}</template>
          </el-table-column>
          <el-table-column
            prop="new"
            :label="t('admin.database.toInsert')"
            width="120"
            align="right"
          >
            <template #default="{ row }">
              <span class="text-green-600 font-medium">{{ row.new.toLocaleString() }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="skip"
            :label="t('admin.database.toSkip')"
            width="120"
            align="right"
          >
            <template #default="{ row }">
              <span class="text-gray-400">{{ row.skip.toLocaleString() }}</span>
            </template>
          </el-table-column>
        </el-table>

        <div class="mt-4 flex justify-end">
          <el-button
            type="primary"
            :loading="isMerging"
            @click="executeMerge"
          >
            {{ t('admin.database.executeMerge') }}
          </el-button>
        </div>
      </template>

      <!-- merge result -->
      <template v-if="mergeResult">
        <el-divider />
        <el-result
          icon="success"
          :title="t('admin.database.mergeComplete')"
          :sub-title="`${mergeResult.elapsed_seconds}s`"
        />
        <el-table
          :data="Object.entries(mergeResult.tables).map(([name, v]) => ({ name, ...v }))"
          size="small"
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
          <el-table-column
            label="Rejected"
            width="120"
            align="right"
          >
            <template #default="{ row }">
              <span :class="row.rejected ? 'text-red-500' : ''">{{ row.rejected ?? '-' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <!-- ═══ Section 3: PG Export / Import ═══ -->
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
              {{ t('admin.refresh') }}
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
            width="120"
            align="center"
          >
            <template #default="{ row }">
              <el-button
                size="small"
                type="danger"
                :loading="isImporting"
                @click="importDump(row.name)"
              >
                {{ t('admin.database.restore') }}
              </el-button>
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
    </el-card>

    <!-- ═══ Section 4: Orphan Cleanup ═══ -->
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
        <div v-if="!hasOrphans" class="text-green-600 text-sm py-2">
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
            {{ t('admin.database.totalOrphans') }}: <strong class="text-orange-600">{{ totalOrphans }}</strong>
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

<style scoped>
.stat-card {
  background-color: #f9fafb;
  border-radius: 0.5rem;
  padding: 1rem;
  text-align: center;
}
.stat-card-sm {
  padding: 0.75rem;
}
.stat-value {
  font-size: 1.5rem;
  line-height: 2rem;
  font-weight: 700;
  color: #111827;
}
.stat-card-sm .stat-value {
  font-size: 1.25rem;
  line-height: 1.75rem;
}
.stat-label {
  font-size: 0.75rem;
  line-height: 1rem;
  color: #6b7280;
  margin-top: 0.25rem;
}
</style>
