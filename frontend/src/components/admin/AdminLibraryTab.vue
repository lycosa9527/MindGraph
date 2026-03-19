<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

interface BookEntry {
  folder_name: string
  page_count: number
  exists_on_disk: boolean
  in_db: boolean
  document_id: number | null
  title: string | null
  is_active: boolean | null
  needs_repair: boolean
  created_at: string | null
}

interface ScanResponse {
  scanned_at: string
  storage_dir: string
  books: BookEntry[]
  total: number
}

interface RenamePreviewItem {
  from: string
  to: string
}

interface RenameResult {
  book_name: string
  total_pages: number
  rename_count: number
  skip_count: number
  error_count: number
  dry_run: boolean
  preview: RenamePreviewItem[]
}

const { t } = useLanguage()
const notify = useNotifications()

const isScanning = ref(false)
const scanData = ref<ScanResponse | null>(null)
const registeringFolders = ref<Set<string>>(new Set())
const togglingIds = ref<Set<number>>(new Set())
const isRegisteringAll = ref(false)
const generatingCoverIds = ref<Set<number>>(new Set())
const coverTimestamps = ref<Record<number, number>>({})
const deletingIds = ref<Set<number>>(new Set())

const renameDialog = reactive({
  visible: false,
  book: null as BookEntry | null,
  bookName: '',
  isLoadingPreview: false,
  isApplying: false,
  result: null as RenameResult | null,
})

const displayLabel = (book: BookEntry) => book.title || book.folder_name

const newBooks = computed(() => scanData.value?.books.filter((b) => !b.in_db) ?? [])
const registeredCount = computed(() => scanData.value?.books.filter((b) => b.in_db).length ?? 0)
const activeCount = computed(
  () => scanData.value?.books.filter((b) => b.is_active === true).length ?? 0
)

type BookStatus = 'new' | 'registered' | 'repair' | 'orphaned'

function getStatus(book: BookEntry): BookStatus {
  if (!book.in_db) return 'new'
  if (!book.exists_on_disk) return 'orphaned'
  if (book.needs_repair) return 'repair'
  return 'registered'
}

const STATUS_DOT_CLASS: Record<BookStatus, string> = {
  new: 'dot-new',
  registered: 'dot-registered',
  repair: 'dot-repair',
  orphaned: 'dot-orphaned',
}

function statusLabel(book: BookEntry): string {
  const map: Record<BookStatus, string> = {
    registered: t('admin.library.statusRegistered'),
    new: t('admin.library.statusNew'),
    repair: t('admin.library.statusRepair'),
    orphaned: t('admin.library.statusOrphaned'),
  }
  return map[getStatus(book)]
}

function sortedBooks(books: BookEntry[]): BookEntry[] {
  const order: Record<BookStatus, number> = { new: 0, repair: 1, registered: 2, orphaned: 3 }
  return [...books].sort((a, b) => order[getStatus(a)] - order[getStatus(b)])
}

async function scan() {
  isScanning.value = true
  try {
    const res = await apiRequest('/api/library/admin/scan')
    if (res.ok) {
      scanData.value = await res.json()
    } else {
      const data = await res.json().catch(() => ({}))
      notify.error(data.detail || t('admin.library.scanError'))
    }
  } catch {
    notify.error(t('admin.library.scanError'))
  } finally {
    isScanning.value = false
  }
}

async function registerBook(book: BookEntry) {
  registeringFolders.value.add(book.folder_name)
  try {
    const res = await apiRequest('/api/library/books/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: book.folder_name }),
    })
    if (res.ok) {
      notify.success(t('admin.library.registerSuccess'))
      await scan()
    } else {
      const data = await res.json().catch(() => ({}))
      notify.error(data.detail || t('admin.library.registerError'))
    }
  } catch {
    notify.error(t('admin.library.registerError'))
  } finally {
    registeringFolders.value.delete(book.folder_name)
  }
}

async function registerAll() {
  const folders = newBooks.value.map((b) => b.folder_name)
  if (!folders.length) return
  isRegisteringAll.value = true
  try {
    const res = await apiRequest('/api/library/books/register-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_paths: folders }),
    })
    if (res.ok) {
      const data = await res.json()
      notify.success(
        `${t('admin.library.registerAllSuccess')}: ${data.successful_count} / ${data.total}`
      )
      await scan()
    } else {
      notify.error(t('admin.library.registerError'))
    }
  } catch {
    notify.error(t('admin.library.registerError'))
  } finally {
    isRegisteringAll.value = false
  }
}

async function toggleVisibility(book: BookEntry) {
  if (book.document_id === null || book.is_active === null) return
  const docId = book.document_id
  togglingIds.value.add(docId)
  const newValue = !book.is_active
  try {
    const res = await apiRequest(`/api/library/documents/${docId}/visibility`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: newValue }),
    })
    if (res.ok) {
      book.is_active = newValue
    } else {
      notify.error(t('admin.library.visibilityError'))
    }
  } catch {
    notify.error(t('admin.library.visibilityError'))
  } finally {
    togglingIds.value.delete(docId)
  }
}

async function generateCover(book: BookEntry) {
  if (book.document_id === null) return
  const docId = book.document_id
  generatingCoverIds.value.add(docId)
  try {
    const res = await apiRequest(`/api/library/admin/documents/${docId}/generate-cover`, {
      method: 'POST',
    })
    if (res.ok) {
      coverTimestamps.value[docId] = Date.now()
      notify.success(t('admin.library.generateCoverSuccess'))
    } else {
      const data = await res.json().catch(() => ({}))
      notify.error(data.detail || t('admin.library.generateCoverError'))
    }
  } catch {
    notify.error(t('admin.library.generateCoverError'))
  } finally {
    generatingCoverIds.value.delete(docId)
  }
}

async function deleteBook(book: BookEntry, deleteFiles: boolean) {
  if (book.document_id === null) return
  const confirmMsg = deleteFiles
    ? t('admin.library.deleteBookConfirmMsg')
        .replace('{name}', displayLabel(book))
        .replace('{count}', String(book.page_count || '?'))
    : t('admin.library.deleteConfirmMsg').replace('{name}', displayLabel(book))
  const confirmTitle = deleteFiles
    ? t('admin.library.deleteBookTitle')
    : t('admin.library.deleteConfirmTitle')
  try {
    await ElMessageBox.confirm(confirmMsg, confirmTitle, {
      type: 'warning',
      confirmButtonText: deleteFiles ? t('admin.library.deleteBookConfirm') : undefined,
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }
  const docId = book.document_id
  deletingIds.value.add(docId)
  try {
    const url = deleteFiles
      ? `/api/library/admin/documents/${docId}?delete_files=true`
      : `/api/library/admin/documents/${docId}`
    const res = await apiRequest(url, { method: 'DELETE' })
    if (res.ok) {
      notify.success(deleteFiles ? t('admin.library.deleteBookSuccess') : t('admin.library.deleteSuccess'))
      await scan()
    } else {
      const data = await res.json().catch(() => ({}))
      notify.error(data.detail || t('admin.library.deleteError'))
    }
  } catch {
    notify.error(t('admin.library.deleteError'))
  } finally {
    deletingIds.value.delete(docId)
  }
}

function openRenameDialog(book: BookEntry) {
  renameDialog.book = book
  renameDialog.bookName = book.title || book.folder_name
  renameDialog.result = null
  renameDialog.isApplying = false
  renameDialog.visible = true
}

async function previewRename() {
  if (!renameDialog.book) return
  renameDialog.isLoadingPreview = true
  try {
    const res = await apiRequest('/api/library/admin/rename-pages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder_name: renameDialog.book.folder_name,
        book_name: renameDialog.bookName || renameDialog.book.folder_name,
        dry_run: true,
      }),
    })
    if (res.ok) {
      renameDialog.result = await res.json()
    } else {
      const data = await res.json().catch(() => ({}))
      notify.error(data.detail || t('admin.library.renameError'))
    }
  } catch {
    notify.error(t('admin.library.renameError'))
  } finally {
    renameDialog.isLoadingPreview = false
  }
}

async function applyRename() {
  if (!renameDialog.book || !renameDialog.result?.rename_count) return
  renameDialog.isApplying = true
  try {
    const res = await apiRequest('/api/library/admin/rename-pages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder_name: renameDialog.book.folder_name,
        book_name: renameDialog.bookName || renameDialog.book.folder_name,
        dry_run: false,
      }),
    })
    if (res.ok) {
      const data: RenameResult = await res.json()
      notify.success(
        `${t('admin.library.renameSuccess').replace('{count}', String(data.rename_count))}`
      )
      renameDialog.visible = false
      await registerBook(renameDialog.book)
    } else {
      const errData = await res.json().catch(() => ({}))
      notify.error(errData.detail || t('admin.library.renameError'))
    }
  } catch {
    notify.error(t('admin.library.renameError'))
  } finally {
    renameDialog.isApplying = false
  }
}

watch(
  () => renameDialog.visible,
  (open) => {
    if (open) previewRename()
  }
)

onMounted(() => {
  scan()
})
</script>

<template>
  <div class="px-0.5">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4 mb-5">
      <div>
        <h2 class="text-sm font-semibold text-stone-800 m-0 mb-0.5">{{ t('admin.library.tabTitle') }}</h2>
        <p class="text-xs text-stone-400 m-0">{{ t('admin.library.tabSubtitle') }}</p>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        <span
          v-if="scanData"
          class="text-[11px] text-stone-400"
        >
          {{ t('admin.library.lastScanned') }}:
          {{ new Date(scanData.scanned_at + 'Z').toLocaleTimeString() }}
        </span>
        <el-button
          :loading="isScanning"
          :icon="isScanning ? undefined : 'Refresh'"
          @click="scan"
        >
          {{ t('admin.library.scan') }}
        </el-button>
        <el-button
          v-if="newBooks.length > 0"
          type="primary"
          :loading="isRegisteringAll"
          @click="registerAll"
        >
          {{ t('admin.library.registerAll') }}
          <el-tag
            size="small"
            effect="dark"
            round
            class="ml-1.5 !bg-white/20 !border-0 !text-white !text-xs !px-1.5 !py-0 !h-4 !leading-4"
          >{{ newBooks.length }}</el-tag>
        </el-button>
      </div>
    </div>

    <!-- Storage path strip (always visible) -->
    <div class="flex items-center gap-1.5 mb-4 px-3 py-2 rounded-lg bg-stone-50 border border-stone-100">
      <el-icon class="text-stone-400 flex-shrink-0"><FolderOpened /></el-icon>
      <span class="text-[11px] text-stone-400 flex-shrink-0">{{ t('admin.library.storageDir') }}:</span>
      <span
        v-if="scanData"
        class="font-mono text-[11px] text-stone-600 truncate"
      >{{ scanData.storage_dir }}</span>
      <span
        v-else
        class="font-mono text-[11px] text-stone-300"
      >storage/library/</span>
    </div>

    <!-- Stats row -->
    <div
      v-if="scanData"
      class="grid grid-cols-4 gap-2.5 mb-4"
    >
      <div class="stat-card stat-default">
        <p class="text-[11px] text-stone-400 truncate mb-1">{{ t('admin.library.totalFolders') }}</p>
        <p class="stat-value">{{ scanData.total }}</p>
      </div>
      <div class="stat-card stat-green">
        <p class="text-[11px] text-stone-400 truncate mb-1">{{ t('admin.library.registered') }}</p>
        <p class="stat-value">{{ registeredCount }}</p>
      </div>
      <div class="stat-card stat-blue">
        <p class="text-[11px] text-stone-400 truncate mb-1">{{ t('admin.library.visible') }}</p>
        <p class="stat-value">{{ activeCount }}</p>
      </div>
      <div class="stat-card stat-amber">
        <p class="text-[11px] text-stone-400 truncate mb-1">{{ t('admin.library.newUnregistered') }}</p>
        <p class="stat-value">{{ newBooks.length }}</p>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div
      v-if="isScanning && !scanData"
      class="text-center py-14 text-stone-400"
    >
      <el-icon
        class="is-loading"
        :size="28"
      ><Loading /></el-icon>
      <p class="mt-3 text-sm">{{ t('admin.library.scanning') }}</p>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="scanData && scanData.total === 0"
      class="text-center py-14 text-stone-400"
    >
      <el-icon :size="36"><FolderOpened /></el-icon>
      <p class="mt-3 text-sm font-medium">{{ t('admin.library.noFolders') }}</p>
      <p class="text-xs mt-1 font-mono text-stone-400">{{ scanData.storage_dir }}</p>
    </div>

    <!-- Books table -->
    <el-table
      v-else-if="scanData && scanData.total > 0"
      :data="sortedBooks(scanData.books)"
      :stripe="true"
      class="w-full"
    >
      <!-- Cover thumbnail -->
      <el-table-column
        width="52"
        align="center"
      >
        <template #default="{ row }">
          <div
            v-if="row.document_id"
            class="cover-thumb-wrap"
          >
            <img
              :src="`/api/library/documents/${row.document_id}/cover?t=${coverTimestamps[row.document_id] ?? 0}`"
              class="cover-thumb"
              alt=""
              @error="(e: Event) => ((e.target as HTMLImageElement).style.opacity = '0')"
            >
          </div>
        </template>
      </el-table-column>

      <!-- Title / folder -->
      <el-table-column
        :label="t('admin.library.colTitle')"
        min-width="200"
      >
        <template #default="{ row }">
          <div class="flex items-center gap-2.5">
            <el-tooltip
              :content="
                row.exists_on_disk
                  ? t('admin.library.diskPresent')
                  : t('admin.library.diskMissing')
              "
            >
              <el-icon
                class="flex-shrink-0"
                :class="row.exists_on_disk ? 'text-green-400' : 'text-red-400'"
              >
                <component :is="row.exists_on_disk ? 'FolderOpened' : 'FolderRemove'" />
              </el-icon>
            </el-tooltip>
            <div class="min-w-0">
              <p class="text-[13px] font-medium text-stone-800 m-0 truncate">{{ displayLabel(row) }}</p>
              <p
                v-if="row.title && row.title !== row.folder_name"
                class="book-folder text-[11px] text-stone-400 mt-px m-0 truncate"
              >
                {{ row.folder_name }}
              </p>
            </div>
          </div>
        </template>
      </el-table-column>

      <!-- Pages -->
      <el-table-column
        :label="t('admin.library.colPages')"
        width="76"
        align="center"
      >
        <template #default="{ row }">
          <span class="text-sm tabular-nums text-stone-500">{{ row.page_count || '—' }}</span>
        </template>
      </el-table-column>

      <!-- Status -->
      <el-table-column
        :label="t('admin.library.colStatus')"
        width="148"
        align="center"
      >
        <template #default="{ row }">
          <div class="inline-flex items-center gap-1.5">
            <span
              class="status-dot"
              :class="STATUS_DOT_CLASS[getStatus(row)]"
            />
            <span class="text-xs text-stone-500">{{ statusLabel(row) }}</span>
          </div>
        </template>
      </el-table-column>

      <!-- Visibility -->
      <el-table-column
        :label="t('admin.library.colVisible')"
        width="88"
        align="center"
      >
        <template #default="{ row }">
          <el-switch
            v-if="row.in_db && row.document_id !== null"
            :model-value="row.is_active === true"
            :loading="row.document_id !== null && togglingIds.has(row.document_id)"
            :disabled="!row.exists_on_disk"
            size="small"
            @change="toggleVisibility(row)"
          />
          <span
            v-else
            class="text-stone-300 text-xs"
          >—</span>
        </template>
      </el-table-column>

      <!-- Actions -->
      <el-table-column
        :label="t('admin.library.colActions')"
        width="160"
        align="center"
      >
        <template #default="{ row }">
          <!-- New book: direct register button -->
          <el-button
            v-if="!row.in_db"
            type="primary"
            size="small"
            :loading="registeringFolders.has(row.folder_name)"
            :disabled="!row.exists_on_disk"
            @click="registerBook(row)"
          >
            {{ t('admin.library.register') }}
          </el-button>

          <!-- Registered book: dropdown actions -->
          <el-dropdown
            v-else
            trigger="click"
            size="small"
          >
            <el-button
              size="small"
              :disabled="!row.exists_on_disk"
            >
              {{ t('admin.library.colActions') }}
              <el-icon class="ml-1"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  :disabled="registeringFolders.has(row.folder_name)"
                  @click="registerBook(row)"
                >
                  <el-icon><Refresh /></el-icon>
                  {{ t('admin.library.reRegister') }}
                </el-dropdown-item>
                <el-dropdown-item
                  :disabled="!row.exists_on_disk || generatingCoverIds.has(row.document_id)"
                  @click="generateCover(row)"
                >
                  <el-icon><Picture /></el-icon>
                  {{ t('admin.library.generateCover') }}
                </el-dropdown-item>
                <el-dropdown-item
                  divided
                  :disabled="!row.exists_on_disk"
                  @click="openRenameDialog(row)"
                >
                  <el-icon><EditPen /></el-icon>
                  {{ t('admin.library.renamePages') }}
                </el-dropdown-item>
                <el-dropdown-item
                  divided
                  class="text-red-500"
                  :disabled="deletingIds.has(row.document_id)"
                  @click="deleteBook(row, row.exists_on_disk)"
                >
                  <el-icon><Delete /></el-icon>
                  {{ row.exists_on_disk ? t('admin.library.deleteBook') : t('admin.library.deleteRecord') }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>


    <!-- Rename Pages Dialog -->
    <el-dialog
      v-model="renameDialog.visible"
      :title="t('admin.library.renameDialogTitle')"
      width="560px"
      destroy-on-close
    >
      <div class="py-1">
        <!-- Book name prefix -->
        <div class="mb-5">
          <label class="block text-[13px] font-medium text-stone-600 mb-1">
            {{ t('admin.library.renameBookNameLabel') }}
          </label>
          <div class="flex gap-2">
            <el-input
              v-model="renameDialog.bookName"
              :placeholder="renameDialog.book?.folder_name"
              class="flex-1"
              @keyup.enter="previewRename"
            />
            <el-button
              :loading="renameDialog.isLoadingPreview"
              @click="previewRename"
            >
              {{ t('admin.library.renamePreview') }}
            </el-button>
          </div>
          <p class="mt-1.5 text-[11px] text-stone-400">
            {{ t('admin.library.renameBookNameHint') }}:
            <span class="font-mono text-stone-500">
              {{ renameDialog.bookName || '…' }}_01.jpg,
              {{ renameDialog.bookName || '…' }}_02.jpg …
            </span>
          </p>
        </div>

        <!-- Preview loading -->
        <div
          v-if="renameDialog.isLoadingPreview"
          class="flex items-center py-5"
        >
          <el-icon class="is-loading"><Loading /></el-icon>
          <span class="ml-2 text-sm text-stone-400">{{ t('admin.library.renamePreviewLoading') }}</span>
        </div>

        <!-- No changes needed -->
        <div
          v-else-if="renameDialog.result && renameDialog.result.rename_count === 0"
          class="text-center py-6 text-green-500"
        >
          <el-icon :size="28"><CircleCheck /></el-icon>
          <p class="mt-2 text-sm">{{ t('admin.library.renameNoChanges') }}</p>
        </div>

        <!-- Preview table -->
        <template v-else-if="renameDialog.result">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-[13px] font-semibold text-stone-800">
              {{ renameDialog.result.rename_count }}
              {{ t('admin.library.renameFilesToRename') }}
            </span>
            <span class="text-stone-300">·</span>
            <span class="text-stone-400 text-sm">
              {{ renameDialog.result.skip_count }}
              {{ t('admin.library.renameFilesAlreadyOk') }}
            </span>
          </div>
          <el-table
            :data="renameDialog.result.preview"
            size="small"
            max-height="220"
            class="rename-table"
          >
            <el-table-column
              :label="t('admin.library.renameColFrom')"
              prop="from"
            />
            <el-table-column
              :label="t('admin.library.renameColTo')"
              prop="to"
            />
          </el-table>
        </template>
      </div>

      <template #footer>
        <el-button @click="renameDialog.visible = false">{{ t('common.cancel') }}</el-button>
        <el-button
          v-if="renameDialog.result && renameDialog.result.rename_count > 0"
          type="primary"
          :loading="renameDialog.isApplying"
          @click="applyRename"
        >
          {{ t('admin.library.renameApply') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.stat-card {
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--el-fill-color-lighter);
  border-left: 3px solid transparent;
}

.stat-default { border-left-color: var(--el-border-color); }
.stat-green   { border-left-color: #22c55e; }
.stat-blue    { border-left-color: #3b82f6; }
.stat-amber   { border-left-color: #f59e0b; }

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1;
  margin: 0;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-new        { background: #3b82f6; }
.dot-registered { background: #22c55e; }
.dot-repair     { background: #f59e0b; }
.dot-orphaned   { background: #ef4444; }

.book-folder {
  font-family: ui-monospace, monospace;
}

.cover-thumb-wrap {
  width: 32px;
  height: 42px;
  margin: 0 auto;
  border-radius: 3px;
  overflow: hidden;
  background: var(--el-fill-color);
}

.cover-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: opacity 0.2s;
}

.rename-table {
  border-radius: 6px;
  overflow: hidden;
}
</style>
