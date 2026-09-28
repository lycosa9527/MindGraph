<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Folder } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { promptSwissGlassName } from '@/composables/sidebar/promptSwissGlassName'
import {
  type VodFolderItem,
  createVodFolder,
  deleteVodFolder,
  listVodFolders,
  renameVodFolder,
} from '@/utils/vodApi'

const props = defineProps<{
  organizationId?: number | null
  canEdit: boolean
  folderId: string
}>()

const emit = defineEmits<{
  'update:folderId': [value: string]
  folders: [items: VodFolderItem[]]
}>()

const FOLDER_NAME_MAX = 80

const { t } = useLanguage()
const notify = useNotifications()
const folders = ref<VodFolderItem[]>([])
const name = ref('')
const busy = ref(false)

const selected = computed(
  () => folders.value.find((folder) => folder.id === props.folderId) ?? null
)

function folderError(err: unknown): string {
  const message = err instanceof Error ? err.message : ''
  if (message.includes('_409') || message.endsWith('409')) {
    return String(t('admin.vod.folderExists'))
  }
  return String(t('admin.vod.folderFailed'))
}

async function load(): Promise<void> {
  if (props.organizationId == null) {
    folders.value = []
    return
  }
  try {
    folders.value = await listVodFolders(props.organizationId)
  } catch {
    folders.value = []
    notify.error(t('admin.vod.folderFailed'))
  }
  emit('folders', folders.value)
}

function onFilter(event: Event): void {
  emit('update:folderId', (event.target as HTMLSelectElement).value)
}

async function create(): Promise<void> {
  const label = name.value.trim()
  if (!label || busy.value) return
  busy.value = true
  try {
    const created = await createVodFolder(label, props.organizationId)
    name.value = ''
    await load()
    emit('update:folderId', created.id)
    notify.success(t('admin.vod.folderCreated'))
  } catch (err) {
    notify.error(folderError(err))
  } finally {
    busy.value = false
  }
}

async function rename(): Promise<void> {
  const current = selected.value
  if (!current || busy.value) return
  const next = await promptSwissGlassName(
    (key) => String(t(key)),
    'admin.vod.folderRenameTitle',
    'admin.vod.folderRenamePrompt',
    'admin.vod.folder',
    current.name,
    { icon: Folder, maxLength: FOLDER_NAME_MAX }
  )
  if (!next) return
  const collapsed = next.trim().split(/\s+/).join(' ')
  if (!collapsed || collapsed === current.name) return
  busy.value = true
  try {
    await renameVodFolder(current.id, collapsed, props.organizationId)
    await load()
    notify.success(t('admin.vod.folderRenamed'))
  } catch (err) {
    notify.error(folderError(err))
  } finally {
    busy.value = false
  }
}

async function remove(): Promise<void> {
  const id = props.folderId
  if (!id || id === 'none' || busy.value) return
  try {
    await swissGlassConfirm(
      String(t('admin.vod.folderDeleteConfirm')),
      String(t('admin.vod.folderDelete')),
      {
        type: 'warning',
      }
    )
  } catch {
    return
  }
  busy.value = true
  try {
    await deleteVodFolder(id, props.organizationId)
    emit('update:folderId', '')
    await load()
    notify.success(t('admin.vod.folderDeleted'))
  } catch {
    notify.error(t('admin.vod.folderFailed'))
  } finally {
    busy.value = false
  }
}

watch(
  () => props.organizationId,
  () => {
    void load()
  },
  { immediate: true }
)
</script>

<template>
  <div class="vod-folders">
    <select
      class="vod-select"
      :value="folderId"
      @change="onFilter"
    >
      <option value=""><I18nText k="admin.vod.folderAll" /></option>
      <option value="none"><I18nText k="admin.vod.folderNone" /></option>
      <option
        v-for="folder in folders"
        :key="folder.id"
        :value="folder.id"
      >
        {{ folder.name }}
      </option>
    </select>
    <template v-if="canEdit">
      <input
        v-model="name"
        class="vod-search"
        type="text"
        maxlength="80"
        :placeholder="t('admin.vod.folderName')"
        @keydown.enter="create"
      />
      <button
        type="button"
        class="vod-ghost"
        :disabled="busy || !name.trim()"
        @click="create"
      >
        <I18nText k="admin.vod.folderCreate" />
      </button>
      <button
        v-if="selected"
        type="button"
        class="vod-ghost"
        :disabled="busy"
        @click="rename"
      >
        <I18nText k="admin.vod.folderRename" />
      </button>
      <button
        v-if="selected"
        type="button"
        class="vod-ghost"
        :disabled="busy"
        @click="remove"
      >
        <I18nText k="admin.vod.folderDelete" />
      </button>
    </template>
  </div>
</template>

<style scoped>
.vod-folders {
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
  min-width: 10rem;
}
.vod-ghost {
  border-radius: 0.375rem;
  padding: 0.4rem 0.85rem;
  background: #f5f5f4;
  color: #44403c;
}
</style>
