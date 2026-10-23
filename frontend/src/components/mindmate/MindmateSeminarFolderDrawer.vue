<script setup lang="ts">
/**
 * Shared folder for seminar background files.
 */
import { onMounted, ref, watch } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu, ElMessageBox } from 'element-plus'

import { FileText, MoreHorizontal, Pin, Quote, Upload, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  bumpSeminarFolderReload,
  citeSeminarFile,
  closeSeminarDoc,
  openSeminarDoc,
  seminarFileDocId,
  seminarFolderReloadToken,
  seminarSpectator,
} from '@/composables/mindmate/mindmateSeminarChrome'
import {
  SEMINAR_BACKGROUND_FILE_ACCEPT,
  type SeminarBackgroundFile,
  deleteSeminarBackgroundFile,
  formatSeminarFileSize,
  listSeminarBackgroundFiles,
  pinSeminarBackgroundFile,
  renameSeminarBackgroundFile,
  seminarFolderErrorKey,
  uploadSeminarBackgroundFile,
} from '@/utils/mindmateSeminarFolder'

const props = withDefaults(
  defineProps<{
    sessionId: string
    /** Hide chrome when mounted inside the seminar task pane. */
    embedded?: boolean
  }>(),
  {
    embedded: false,
  }
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const files = ref<SeminarBackgroundFile[]>([])
const loading = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

async function reload(): Promise<void> {
  if (!props.sessionId) {
    files.value = []
    return
  }
  loading.value = true
  try {
    files.value = await listSeminarBackgroundFiles(props.sessionId)
  } catch {
    notify.errorKey('mindmate.folder.loadFailed')
  } finally {
    loading.value = false
  }
}

function openPicker(): void {
  fileInput.value?.click()
}

async function onPick(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const picked = input.files ? Array.from(input.files) : []
  input.value = ''
  if (!picked.length || !props.sessionId || uploading.value) {
    return
  }
  uploading.value = true
  try {
    for (const file of picked) {
      const saved = await uploadSeminarBackgroundFile(props.sessionId, file)
      files.value = [saved, ...files.value.filter((item) => item.id !== saved.id)]
    }
    bumpSeminarFolderReload()
  } catch (error) {
    console.error('[SeminarFolder] upload failed', error)
    notify.errorKey(seminarFolderErrorKey(error))
  } finally {
    uploading.value = false
  }
}

function openFile(file: SeminarBackgroundFile): void {
  if (file.diagramId) {
    openSeminarDoc({
      id: `canvas:${file.diagramId}`,
      kind: 'diagram',
      title: file.filename,
      diagramId: file.diagramId,
    })
    return
  }
  openSeminarDoc({
    id: seminarFileDocId(file.id),
    kind: 'file',
    title: file.filename,
    fileId: file.id,
    contentType: file.contentType,
    filename: file.filename,
  })
}

function citeFile(file: SeminarBackgroundFile): void {
  citeSeminarFile({
    fileId: file.id,
    filename: file.filename,
    contentType: file.contentType,
    sizeBytes: file.sizeBytes,
  })
  notify.successKey('mindmate.docViewer.cited')
}

async function renameFile(file: SeminarBackgroundFile): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt(
      t('mindmate.folder.renameHint'),
      t('mindmate.folder.rename'),
      {
        inputValue: file.filename,
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        inputValidator: (raw) => {
          const next = (raw || '').trim()
          if (!next) {
            return t('mindmate.folder.renameRequired')
          }
          return true
        },
      }
    )
    const saved = await renameSeminarBackgroundFile(props.sessionId, file.id, value.trim())
    files.value = files.value.map((item) => (item.id === saved.id ? saved : item))
    bumpSeminarFolderReload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    notify.errorKey(seminarFolderErrorKey(error))
  }
}

async function togglePin(file: SeminarBackgroundFile): Promise<void> {
  try {
    const saved = await pinSeminarBackgroundFile(props.sessionId, file.id, !file.pinned)
    files.value = [saved, ...files.value.filter((item) => item.id !== saved.id)].sort(
      (left, right) => Number(right.pinned) - Number(left.pinned)
    )
    bumpSeminarFolderReload()
  } catch (error) {
    notify.errorKey(seminarFolderErrorKey(error))
  }
}

async function removeFile(file: SeminarBackgroundFile): Promise<void> {
  try {
    await ElMessageBox.confirm(
      t('mindmate.folder.deleteConfirm', { name: file.filename }),
      t('mindmate.folder.delete'),
      {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      }
    )
    await deleteSeminarBackgroundFile(props.sessionId, file.id)
    files.value = files.value.filter((item) => item.id !== file.id)
    closeSeminarDoc(seminarFileDocId(file.id))
    bumpSeminarFolderReload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    notify.errorKey(seminarFolderErrorKey(error))
  }
}

async function onCommand(command: string, file: SeminarBackgroundFile): Promise<void> {
  if (command === 'rename') {
    await renameFile(file)
    return
  }
  if (command === 'pin') {
    await togglePin(file)
    return
  }
  if (command === 'delete') {
    await removeFile(file)
  }
}

onMounted(() => {
  void reload()
})

watch(
  () => [props.sessionId, seminarFolderReloadToken.value] as const,
  () => {
    void reload()
  }
)
</script>

<template>
  <aside
    class="mm-folder-side"
    :class="{ 'is-embedded': embedded }"
    :aria-label="t('mindmate.folder.title')"
  >
    <header
      v-if="!embedded"
      class="mm-folder-side__header"
    >
      <h2 class="mm-folder-side__title">
        <I18nText k="mindmate.folder.title" />
      </h2>
      <button
        type="button"
        class="mm-folder-side__close"
        :aria-label="t('common.close')"
        @click="emit('close')"
      >
        <X
          :size="16"
          aria-hidden="true"
        />
      </button>
    </header>
    <p class="mm-folder-side__hint">
      <I18nText k="mindmate.folder.hint" />
    </p>
    <div
      v-if="!seminarSpectator"
      class="mm-folder-side__upload"
    >
      <input
        ref="fileInput"
        class="mm-folder-side__input"
        type="file"
        multiple
        :accept="SEMINAR_BACKGROUND_FILE_ACCEPT"
        @change="onPick"
      />
      <button
        type="button"
        class="mm-folder-side__upload-btn"
        :disabled="uploading || !sessionId"
        @click="openPicker"
      >
        <Upload
          :size="14"
          aria-hidden="true"
        />
        <I18nText
          k="mindmate.folder.upload"
          dense
        />
      </button>
    </div>
    <p
      v-if="loading"
      class="mm-folder-side__empty"
    >
      <I18nText k="common.loading" />
    </p>
    <p
      v-else-if="files.length === 0"
      class="mm-folder-side__empty"
    >
      <I18nText k="mindmate.folder.empty" />
    </p>
    <ul
      v-else
      class="mm-folder-side__list"
    >
      <li
        v-for="file in files"
        :key="file.id"
        class="mm-folder-side__item"
      >
        <button
          type="button"
          class="mm-folder-side__row"
          @click="openFile(file)"
        >
          <Pin
            v-if="file.pinned"
            :size="14"
            class="mm-folder-side__pin"
            aria-hidden="true"
          />
          <FileText
            v-else
            :size="16"
            class="mm-folder-side__icon"
            aria-hidden="true"
          />
          <span class="mm-folder-side__meta">
            <span class="mm-folder-side__name">{{ file.filename }}</span>
            <span class="mm-folder-side__sub">
              {{ formatSeminarFileSize(file.sizeBytes) }}
              <template v-if="file.uploaderName"> · {{ file.uploaderName }}</template>
            </span>
          </span>
        </button>
        <button
          v-if="!seminarSpectator"
          type="button"
          class="mm-folder-side__cite"
          :aria-label="t('mindmate.docViewer.cite')"
          :title="t('mindmate.docViewer.cite')"
          @click.stop="citeFile(file)"
        >
          <Quote
            :size="15"
            aria-hidden="true"
          />
        </button>
        <ElDropdown
          v-if="!seminarSpectator"
          trigger="click"
          popper-class="mm-folder-side__menu"
          @command="(cmd: string) => onCommand(cmd, file)"
        >
          <button
            type="button"
            class="mm-folder-side__more"
            :aria-label="t('mindmate.folder.more')"
            @click.stop
          >
            <MoreHorizontal
              :size="16"
              aria-hidden="true"
            />
          </button>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem command="rename">
                <I18nText k="mindmate.folder.rename" />
              </ElDropdownItem>
              <ElDropdownItem command="pin">
                <I18nText :k="file.pinned ? 'mindmate.folder.unpin' : 'mindmate.folder.pin'" />
              </ElDropdownItem>
              <ElDropdownItem
                command="delete"
                divided
              >
                <I18nText k="mindmate.folder.delete" />
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.mm-folder-side {
  display: flex;
  flex-direction: column;
  width: 300px;
  max-width: 38vw;
  min-width: 0;
  min-height: 0;
  height: 100%;
  border-left: 1px solid #e9e5ff;
  background: #fff;
  box-shadow: -8px 0 24px rgba(109, 94, 252, 0.05);
  overflow: auto;
}

.mm-folder-side.is-embedded {
  width: 100%;
  max-width: none;
  border-left: none;
  box-shadow: none;
  background: transparent;
}

.mm-folder-side__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 14px 4px;
}

.mm-folder-side__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1c1917;
}

.mm-folder-side__close {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #78716c;
  cursor: pointer;
}

.mm-folder-side__close:hover {
  background: #f5f5f4;
}

.mm-folder-side__hint {
  margin: 0;
  padding: 0 14px 10px;
  font-size: 12px;
  line-height: 1.5;
  color: #a8a29e;
}

.mm-folder-side__upload {
  padding: 0 14px 12px;
}

.mm-folder-side__input {
  display: none;
}

.mm-folder-side__upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  background: #fff;
  color: #44403c;
  font-size: 13px;
  cursor: pointer;
}

.mm-folder-side__upload-btn:hover:not(:disabled) {
  border-color: #c4b5fd;
  color: #6d28d9;
  background: #f5f3ff;
}

.mm-folder-side__upload-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.mm-folder-side__empty {
  margin: 0;
  padding: 0 14px;
  font-size: 12px;
  color: #a8a29e;
}

.mm-folder-side__list {
  list-style: none;
  margin: 0;
  padding: 0 8px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mm-folder-side__item {
  display: flex;
  align-items: center;
  gap: 2px;
}

.mm-folder-side__row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.mm-folder-side__row:hover {
  background: #f5f5f4;
}

.mm-folder-side__icon,
.mm-folder-side__pin {
  flex-shrink: 0;
  color: #78716c;
}

.mm-folder-side__pin {
  color: #7c3aed;
}

.mm-folder-side__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mm-folder-side__name {
  font-size: 13px;
  color: #1c1917;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-folder-side__sub {
  font-size: 11px;
  color: #a8a29e;
}

.mm-folder-side__cite,
.mm-folder-side__more {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #a8a29e;
  cursor: pointer;
}

.mm-folder-side__cite:hover,
.mm-folder-side__more:hover {
  background: #f5f3ff;
  color: #6d5efc;
}
</style>

<style>
.mm-folder-side__menu.el-dropdown__popper,
.mm-folder-side__menu.el-popper {
  border: 1px solid #e9e5ff !important;
  border-radius: 12px !important;
  box-shadow: 0 10px 28px rgba(28, 25, 23, 0.1) !important;
  overflow: hidden;
}

.mm-folder-side__menu .el-dropdown-menu {
  padding: 6px;
  background: #fff;
  border: none;
}

.mm-folder-side__menu .el-dropdown-menu__item {
  border-radius: 8px;
  color: #44403c;
  font-size: 13px;
  padding: 8px 12px;
  line-height: 1.3;
}

.mm-folder-side__menu .el-dropdown-menu__item:not(.is-disabled):hover {
  background: #f5f3ff;
  color: #5b21b6;
}

.mm-folder-side__menu .el-dropdown-menu__item--divided {
  margin-top: 6px;
  border-top-color: #f3f0ff;
}

.mm-folder-side__menu .el-dropdown-menu__item--divided::before {
  background: #f3f0ff;
}
</style>
