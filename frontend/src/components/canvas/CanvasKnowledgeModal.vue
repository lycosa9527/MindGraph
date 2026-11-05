<script setup lang="ts">
/**
 * Canvas personal-knowledge picker.
 * One folder at a time. An empty folder can be opened and filled, and does not become the source.
 */
import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'

import { Check, Folder, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import SettingsKnowledgeBrowser from '@/components/settings/SettingsKnowledgeBrowser.vue'
import { useDiagramKnowledgeSelection } from '@/composables/canvas/useDiagramKnowledgeSelection'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  type KnowledgePackage,
  useFileCenterMutations,
  usePackageDetail,
  usePackages,
} from '@/composables/fileCenter/useFileCenter'
import '@/styles/settings-language-swiss.css'
import { MAX_FILES_PER_PACKAGE, MAX_KNOWLEDGE_FILE_BYTES } from '@/utils/knowledgePackageLimit'
import { folderIsReady, folderWorkTone } from '@/utils/knowledgeWorkTone'

const open = defineModel<boolean>('open', { required: true })

const MAX_FILE_BYTES = MAX_KNOWLEDGE_FILE_BYTES
const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt', 'md', 'jpg', 'jpeg', 'png']
const FOLDER_CLICK_MS = 220

const { t } = useLanguage()
const { selectedPackageId, chooseFolder } = useDiagramKnowledgeSelection()
const packagesQuery = usePackages()
const { createPackage, uploadFile, deleteSource, startProcessing } = useFileCenterMutations()

const openedId = shallowRef<number | null>(null)
const pickedDocId = shallowRef<number | null>(null)
const renameDraft = shallowRef('')
const dropping = shallowRef(false)
const fileInput = shallowRef<HTMLInputElement | null>(null)
let folderClickTimer: ReturnType<typeof setTimeout> | null = null

const folders = computed(() =>
  (packagesQuery.data.value?.packages ?? [])
    .filter((item) => item.source === 'knowledge_space')
    .slice()
    .sort((left, right) => left.id - right.id)
)
const openedPackage = computed(
  (): KnowledgePackage | null => folders.value.find((item) => item.id === openedId.value) ?? null
)
const defaultFolderId = computed(() => folders.value[0]?.id ?? null)
const detailQuery = usePackageDetail(openedId)
const documents = computed(() => detailQuery.data.value?.documents ?? [])
const loading = computed(
  () => packagesQuery.isLoading.value || (openedId.value !== null && detailQuery.isLoading.value)
)

function folderLabel(folder: KnowledgePackage): string {
  return folder.name?.trim() || t('settings.knowledge.defaultPackage')
}

function folderSelected(folder: KnowledgePackage): boolean {
  return folder.id === selectedPackageId.value
}

function folderToneClass(folder: KnowledgePackage): string {
  const tone = folderWorkTone(folder)
  return tone === 'idle' ? '' : `is-${tone}`
}

function clearFolderClick(): void {
  if (folderClickTimer === null) return
  clearTimeout(folderClickTimer)
  folderClickTimer = null
}

function onFolderClick(folder: KnowledgePackage): void {
  if (folderClickTimer !== null) {
    clearFolderClick()
    openedId.value = folder.id
    pickedDocId.value = null
    return
  }
  folderClickTimer = setTimeout(() => {
    folderClickTimer = null
    chooseFolder(folder.id, folderIsReady(folder))
  }, FOLDER_CLICK_MS)
}

async function openPlaceholder(): Promise<void> {
  if (createPackage.isPending.value) return
  try {
    const created = await createPackage.mutateAsync({
      name: t('settings.knowledge.defaultPackage'),
      source: 'knowledge_space',
    })
    openedId.value = created.id
    pickedDocId.value = null
  } catch {
    return
  }
}

function onPlaceholderClick(): void {
  if (folderClickTimer !== null) {
    clearFolderClick()
    void openPlaceholder()
    return
  }
  folderClickTimer = setTimeout(() => {
    folderClickTimer = null
  }, FOLDER_CLICK_MS)
}

function goBack(): void {
  openedId.value = null
  pickedDocId.value = null
}

watch(open, (visible) => {
  if (visible) return
  openedId.value = null
  pickedDocId.value = null
})

onBeforeUnmount(() => {
  clearFolderClick()
})

function extensionOf(name: string): string {
  const parts = name.split('.')
  return parts.length > 1 ? (parts.pop() ?? '').toLowerCase() : ''
}

function rejectFile(file: File): boolean {
  if (file.size > MAX_FILE_BYTES) {
    notify.errorKey('settings.knowledge.fileTooLarge')
    return true
  }
  if (!ALLOWED_EXTENSIONS.includes(extensionOf(file.name))) {
    notify.errorKey('settings.knowledge.unsupportedType')
    return true
  }
  return false
}

function pickUploads(): void {
  if (openedId.value === null) return
  if (documents.value.length >= MAX_FILES_PER_PACKAGE) {
    notify.errorKey('settings.knowledge.folderFull')
    return
  }
  fileInput.value?.click()
}

async function storeFiles(files: File[]): Promise<void> {
  const id = openedId.value
  if (id === null || files.length === 0 || uploadFile.isPending.value) return
  let room = MAX_FILES_PER_PACKAGE - documents.value.length
  let stored = 0
  for (const file of files) {
    if (room <= 0) {
      notify.errorKey('settings.knowledge.folderFull')
      break
    }
    if (rejectFile(file)) continue
    try {
      await uploadFile.mutateAsync({ packageId: id, file })
      room -= 1
      stored += 1
    } catch {
      return
    }
  }
  if (stored === 0) return
  try {
    await startProcessing.mutateAsync(id)
    notify.successKey('knowledgeSpace.uploadSuccessProcessing')
  } catch {
    return
  }
}

function onPick(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  void storeFiles(files)
}

async function deletePicked(): Promise<void> {
  const documentId = pickedDocId.value
  const packageId = openedId.value
  if (documentId === null || packageId === null) return
  try {
    await swissGlassConfirm(
      t('knowledgeSpace.confirmDeleteBody'),
      t('knowledgeSpace.confirmDeleteTitle'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
    await deleteSource.mutateAsync({ packageId, documentId })
    pickedDocId.value = null
  } catch (error) {
    if (error === 'cancel') return
  }
}

function onPanelDragOver(event: DragEvent): void {
  if (openedId.value === null || !event.dataTransfer?.types.includes('Files')) return
  event.preventDefault()
  dropping.value = true
}

function onPanelDragLeave(): void {
  dropping.value = false
}

function onPanelDrop(event: DragEvent): void {
  if (openedId.value === null) return
  event.preventDefault()
  dropping.value = false
  void storeFiles(Array.from(event.dataTransfer?.files ?? []))
}
</script>

<template>
  <SwissGlassDialog
    v-model="open"
    width="min(520px, 92vw)"
    :ribbon="t('settings.knowledge.testing')"
    ribbon-key="settings.knowledge.testing"
    :title="t('settings.tabs.knowledge')"
    title-key="settings.tabs.knowledge"
    :line1="t('canvas.knowledge.emptyIgnored')"
    line1-key="canvas.knowledge.emptyIgnored"
    :icon="Folder"
  >
    <div class="canvas-knowledge-body">
      <section
        class="knowledge-settings__panel"
        :class="{ 'is-dropping': dropping }"
        @dragover="onPanelDragOver"
        @dragleave="onPanelDragLeave"
        @drop="onPanelDrop"
      >
        <SettingsKnowledgeBrowser
          v-if="openedPackage"
          v-model:rename-draft="renameDraft"
          :folder-name="folderLabel(openedPackage)"
          :renaming="false"
          :loading="loading"
          :documents="documents"
          :picked-id="pickedDocId"
          :upload-disabled="
            uploadFile.isPending.value ||
            startProcessing.isPending.value ||
            documents.length >= MAX_FILES_PER_PACKAGE
          "
          :delete-disabled="pickedDocId === null || deleteSource.isPending.value"
          :placeholder="t('settings.knowledge.defaultPackage')"
          @back="goBack"
          @pick="pickedDocId = $event"
          @clear-pick="pickedDocId = null"
          @upload="pickUploads"
          @delete-picked="deletePicked"
        />
        <div
          v-else
          class="knowledge-settings__folders"
        >
          <button
            v-if="folders.length === 0"
            type="button"
            class="knowledge-settings__folder"
            @click="onPlaceholderClick"
          >
            <span class="knowledge-settings__glyph">
              <Folder
                :size="40"
                :stroke-width="1.5"
              />
            </span>
            <span class="knowledge-settings__caption">
              <I18nText k="settings.knowledge.defaultPackage" />
            </span>
            <span class="knowledge-settings__badge">
              <I18nText k="settings.knowledge.defaultBadge" />
            </span>
          </button>
          <button
            v-for="folder in folders"
            :key="folder.id"
            type="button"
            class="knowledge-settings__folder"
            :class="[folderToneClass(folder), { 'is-selected': folderSelected(folder) }]"
            @click="onFolderClick(folder)"
          >
            <span class="knowledge-settings__glyph">
              <Folder
                :size="40"
                :stroke-width="1.5"
              />
              <span
                v-if="folderToneClass(folder) === 'is-failed'"
                class="knowledge-settings__fault"
              >
                <X
                  :size="12"
                  :stroke-width="3"
                />
              </span>
              <span
                v-if="folderSelected(folder)"
                class="knowledge-settings__check"
              >
                <Check
                  :size="12"
                  :stroke-width="3"
                />
              </span>
            </span>
            <span class="knowledge-settings__caption">
              {{ folderLabel(folder) }}
            </span>
            <span
              v-if="folder.id === defaultFolderId"
              class="knowledge-settings__badge"
            >
              <I18nText k="settings.knowledge.defaultBadge" />
            </span>
          </button>
        </div>
      </section>
      <input
        ref="fileInput"
        class="knowledge-settings__file"
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.md,.jpg,.jpeg,.png"
        @change="onPick"
      />
    </div>
  </SwissGlassDialog>
</template>

<style scoped>
.canvas-knowledge-body :deep(.knowledge-settings__panel) {
  margin-bottom: 4px;
}
</style>
