<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { ElPagination } from 'element-plus'

import { useLanguage, useNotifications } from '@/composables'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useAdminOrgScope } from '@/composables/admin/useAdminOrgScope'
import {
  type VodFolderItem,
  type VodMediaItem,
  deleteVodMedia,
  fetchVodConfig,
  listVodMedia,
  moveVodMedia,
  refreshVodMedia,
} from '@/utils/vodApi'

import AdminVodFolderBar from './AdminVodFolderBar.vue'
import AdminVodLibrary from './AdminVodLibrary.vue'
import AdminVodPreviewDrawer from './AdminVodPreviewDrawer.vue'
import AdminVodUploadDialog from './AdminVodUploadDialog.vue'

const { t } = useLanguage()
const notify = useNotifications()
const { can } = useAdminAccess()
const { organizations, selectedOrgId, canPickOrganization, refetchOrganizations } =
  useAdminOrgScope()

const canEdit = computed(() => can('tab.vod.edit'))
const canPickOrg = canPickOrganization
const orgId = selectedOrgId

const PAGE_SIZE = 20

const items = ref<VodMediaItem[]>([])
const total = ref(0)
const offset = ref(0)
const query = ref('')
const status = ref('')
const folderId = ref('')
const folders = ref<VodFolderItem[]>([])
const view = ref<'grid' | 'table'>('grid')
const loading = ref(false)
const configured = ref(true)
const showUpload = ref(false)
const preview = ref<VodMediaItem | null>(null)
const showPreview = ref(false)

const currentPage = computed(() => Math.floor(offset.value / PAGE_SIZE) + 1)
let loadGen = 0

async function load(allowRetry = true): Promise<void> {
  const gen = ++loadGen
  loading.value = true
  try {
    const [cfg, list] = await Promise.all([
      fetchVodConfig(),
      listVodMedia({
        q: query.value,
        status: status.value,
        organizationId: orgId.value,
        folderId: folderId.value,
        offset: offset.value,
        limit: PAGE_SIZE,
      }),
    ])
    if (gen !== loadGen) {
      return
    }
    configured.value = cfg.configured
    if (allowRetry && list.items.length === 0 && offset.value > 0) {
      offset.value = 0
      await load(false)
      return
    }
    items.value = list.items
    total.value = list.total
  } catch {
    if (gen === loadGen) {
      notify.error(t('admin.vod.loadFailed'))
    }
  } finally {
    if (gen === loadGen) {
      loading.value = false
    }
  }
}

function reloadFromStart(): void {
  offset.value = 0
  void load()
}

function onPageChange(page: number): void {
  offset.value = Math.max(0, page - 1) * PAGE_SIZE
  void load()
}

function openPreview(item: VodMediaItem): void {
  preview.value = item
  showPreview.value = true
}

async function onRefresh(item: VodMediaItem): Promise<void> {
  try {
    const next = await refreshVodMedia(item.id, orgId.value)
    items.value = items.value.map((row) => (row.id === next.id ? next : row))
  } catch {
    notify.error(t('admin.vod.loadFailed'))
  }
}

async function onDelete(item: VodMediaItem): Promise<void> {
  try {
    await deleteVodMedia(item.id, orgId.value)
    if (preview.value?.id === item.id) {
      preview.value = null
      showPreview.value = false
    }
    await load()
  } catch {
    notify.error(t('admin.vod.loadFailed'))
  }
}

function onOrgChange(event: Event): void {
  const raw = (event.target as HTMLSelectElement).value
  selectedOrgId.value = raw === '' ? null : Number(raw)
}

const uploadFolderId = computed(() =>
  folderId.value && folderId.value !== 'none' ? folderId.value : null
)

async function onMove(item: VodMediaItem, nextFolderId: string | null): Promise<void> {
  try {
    await moveVodMedia(item.id, nextFolderId, orgId.value)
    await load()
  } catch {
    notify.error(t('admin.vod.folderFailed'))
  }
}

function onFolder(value: string): void {
  if (value === folderId.value) return
  folderId.value = value
  reloadFromStart()
}

watch(selectedOrgId, () => {
  folderId.value = ''
  reloadFromStart()
})

onMounted(() => {
  void refetchOrganizations()
  void load()
})
</script>

<template>
  <div class="vod-tab">
    <div class="vod-toolbar">
      <input
        v-model="query"
        type="search"
        class="vod-search"
        :placeholder="t('admin.vod.search')"
        @keydown.enter="reloadFromStart"
        @search="reloadFromStart"
      />
      <select
        v-if="canPickOrg"
        class="vod-select"
        :value="orgId ?? ''"
        @change="onOrgChange"
      >
        <option value="">{{ t('admin.allSchools') }}</option>
        <option
          v-for="org in organizations"
          :key="org.id"
          :value="org.id"
        >
          {{ org.name }}
        </option>
      </select>
      <select
        v-model="status"
        class="vod-select"
        @change="reloadFromStart"
      >
        <option value="">{{ t('admin.vod.statusAll') }}</option>
        <option value="pending">{{ t('admin.vod.statusPending') }}</option>
        <option value="processing">{{ t('admin.vod.statusProcessing') }}</option>
        <option value="ready">{{ t('admin.vod.statusReady') }}</option>
        <option value="failed">{{ t('admin.vod.statusFailed') }}</option>
      </select>
      <button
        type="button"
        class="vod-ghost"
        @click="view = view === 'grid' ? 'table' : 'grid'"
      >
        {{ view === 'grid' ? t('admin.vod.viewTable') : t('admin.vod.viewGrid') }}
      </button>
      <button
        v-if="canEdit"
        type="button"
        class="vod-primary"
        :disabled="!configured || (canPickOrg && orgId == null)"
        @click="showUpload = true"
      >
        {{ t('admin.vod.upload') }}
      </button>
    </div>
    <AdminVodFolderBar
      v-if="configured && !(canPickOrg && orgId == null)"
      :organization-id="orgId"
      :can-edit="canEdit"
      :folder-id="folderId"
      @update:folder-id="onFolder"
      @folders="folders = $event"
    />
    <p
      v-if="!configured"
      class="vod-hint"
    >
      {{ t('admin.vod.notConfigured') }}
    </p>
    <p
      v-else-if="canPickOrg && orgId == null"
      class="vod-hint"
    >
      {{ t('admin.vod.orgFilter') }}
    </p>
    <p
      v-else-if="loading && items.length === 0"
      class="vod-hint"
    >
      {{ t('common.loading') }}
    </p>
    <p
      v-else-if="items.length === 0"
      class="vod-hint"
    >
      {{ t('admin.vod.empty') }}
    </p>
    <AdminVodLibrary
      v-else
      :items="items"
      :folders="folders"
      :view="view"
      :can-edit="canEdit"
      @preview="openPreview"
      @refresh="onRefresh"
      @delete="onDelete"
      @move="onMove"
    />
    <ElPagination
      v-if="configured && !(canPickOrg && orgId == null) && total > PAGE_SIZE"
      class="vod-pager"
      :current-page="currentPage"
      :page-size="PAGE_SIZE"
      :total="total"
      layout="prev, pager, next"
      @current-change="onPageChange"
    />
    <AdminVodUploadDialog
      v-model="showUpload"
      :organization-id="orgId"
      :folder-id="uploadFolderId"
      @uploaded="reloadFromStart"
    />
    <AdminVodPreviewDrawer
      v-model="showPreview"
      :media="preview"
      :organization-id="orgId"
    />
  </div>
</template>

<style scoped>
.vod-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.vod-search,
.vod-select {
  border: 1px solid #d6d3d1;
  border-radius: 0.375rem;
  padding: 0.4rem 0.6rem;
}
.vod-search {
  min-width: 12rem;
  flex: 1;
}
.vod-ghost,
.vod-primary {
  border-radius: 0.375rem;
  padding: 0.4rem 0.85rem;
}
.vod-ghost {
  background: #f5f5f4;
  color: #44403c;
}
.vod-primary {
  background: #1c1917;
  color: #fff;
}
.vod-hint {
  color: #78716c;
  font-size: 0.875rem;
}
.vod-pager {
  display: flex;
  margin-top: 1rem;
  justify-content: center;
}
</style>
