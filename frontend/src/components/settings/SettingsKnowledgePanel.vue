<script setup lang="ts">
/**
 * Settings → 个人知识库.
 * One default folder, more from the icon menu, ten files each, via MindChunk packages.
 * Tencent IMA credentials stay in this panel until retrieval is connected.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { Check, Folder, X } from '@lucide/vue'

import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  type KnowledgePackage,
  type PackageDetailResponse,
  useFileCenterMutations,
  usePackageDetail,
  usePackages,
} from '@/composables/fileCenter/useFileCenter'
import { apiRequestJson } from '@/utils/apiClient'
import {
  MAX_FILES_PER_PACKAGE,
  MAX_KNOWLEDGE_FILE_BYTES,
  MAX_KNOWLEDGE_PACKAGES,
} from '@/utils/knowledgePackageLimit'
import { folderWorkTone } from '@/utils/knowledgeWorkTone'

import SettingsKnowledgeBrowser from './SettingsKnowledgeBrowser.vue'

const MAX_FILE_BYTES = MAX_KNOWLEDGE_FILE_BYTES
const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt', 'md', 'jpg', 'jpeg', 'png']
const FOLDER_CLICK_MS = 220

const { t } = useLanguage()
const packagesQuery = usePackages()
const { createPackage, updatePackage, deletePackage, uploadFile, deleteSource, startProcessing } =
  useFileCenterMutations()

const menuRoot = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const dropping = ref(false)
const renameInput = ref<HTMLInputElement | null>(null)
const selectedId = ref<number | null>(null)
const placeholderOn = ref(false)
const draftName = ref('')
const openedId = ref<number | null>(null)
const pickedDocId = ref<number | null>(null)
const menuOpen = ref(false)
const menuInside = ref(false)
const menuFolderId = ref<number | null>(null)
const menuX = ref(0)
const menuY = ref(0)
const renaming = ref(false)
const renamingId = ref<number | null>(null)
const renameCancelled = ref(false)
const renameDraft = ref('')
const imaOpen = ref(false)
const imaConnected = ref(false)
const imaClientId = ref('')
const imaApiKey = ref('')

const packages = computed(() => packagesQuery.data.value?.packages ?? [])
const folders = computed(() =>
  packages.value
    .filter((item) => item.source === 'knowledge_space')
    .slice()
    .sort((left, right) => left.id - right.id)
)
const defaultFolderId = computed(() => folders.value[0]?.id ?? null)
const openedPackage = computed(
  (): KnowledgePackage | null => folders.value.find((item) => item.id === openedId.value) ?? null
)
const packageId = computed(() => openedId.value)
const detailQuery = usePackageDetail(packageId)
const documents = computed(() => detailQuery.data.value?.documents ?? [])
const loading = computed(
  () => packagesQuery.isLoading.value || (packageId.value !== null && detailQuery.isLoading.value)
)
const canAddFolder = computed(() => folders.value.length < MAX_KNOWLEDGE_PACKAGES)
const menuFolder = computed(
  (): KnowledgePackage | null =>
    folders.value.find((item) => item.id === menuFolderId.value) ?? null
)
function folderToneClass(folder: KnowledgePackage): string {
  const tone = folderWorkTone(folder)
  return tone === 'idle' ? '' : `is-${tone}`
}

watch(folders, (items) => {
  if (selectedId.value !== null && !items.some((item) => item.id === selectedId.value)) {
    selectedId.value = null
  }
  if (openedId.value !== null && !items.some((item) => item.id === openedId.value)) {
    openedId.value = null
  }
})

function folderLabel(folder: KnowledgePackage): string {
  return folder.name?.trim() || t('settings.knowledge.defaultPackage')
}

function voidKnowledgeSpace(): void {
  selectedId.value = null
  openedId.value = null
  pickedDocId.value = null
  placeholderOn.value = false
}

function useKnowledgeSpace(): void {
  if (!imaConnected.value) return
  imaConnected.value = false
  notify.warningKey('settings.knowledge.imaUseKnowledge')
}

let folderClickTimer: ReturnType<typeof setTimeout> | null = null

function clearFolderClick(): void {
  if (folderClickTimer === null) return
  clearTimeout(folderClickTimer)
  folderClickTimer = null
}

function onFolderClick(id: number): void {
  if (folderClickTimer !== null) {
    clearFolderClick()
    void openFolder(id)
    return
  }
  folderClickTimer = setTimeout(() => {
    folderClickTimer = null
    selectFolder(id)
  }, FOLDER_CLICK_MS)
}

function onPlaceholderClick(): void {
  if (folderClickTimer !== null) {
    clearFolderClick()
    void openFolder(null)
    return
  }
  folderClickTimer = setTimeout(() => {
    folderClickTimer = null
    togglePlaceholder()
  }, FOLDER_CLICK_MS)
}

async function openFolder(id: number | null): Promise<void> {
  menuOpen.value = false
  renaming.value = false
  useKnowledgeSpace()
  let next = id
  if (next === null) {
    if (createPackage.isPending.value) return
    try {
      const created = await createPackage.mutateAsync({
        name: draftName.value.trim() || t('settings.knowledge.defaultPackage'),
        source: 'knowledge_space',
      })
      draftName.value = ''
      next = created.id
    } catch {
      return
    }
  }
  pickedDocId.value = null
  openedId.value = next
}

function goBack(): void {
  menuOpen.value = false
  openedId.value = null
  pickedDocId.value = null
  renaming.value = false
}

function selectFolder(id: number): void {
  menuOpen.value = false
  renaming.value = false
  if (selectedId.value === id) {
    selectedId.value = null
    return
  }
  useKnowledgeSpace()
  selectedId.value = id
}

function togglePlaceholder(): void {
  placeholderOn.value = !placeholderOn.value
  menuOpen.value = false
  renaming.value = false
  if (placeholderOn.value) useKnowledgeSpace()
}

function placeMenu(): void {
  const root = menuRoot.value
  if (!root) return
  const rect = root.getBoundingClientRect()
  const pad = 8
  if (rect.right > window.innerWidth - pad) {
    menuX.value = Math.max(pad, window.innerWidth - rect.width - pad)
  }
  if (rect.bottom > window.innerHeight - pad) {
    menuY.value = Math.max(pad, window.innerHeight - rect.height - pad)
  }
}

function openMenu(event: MouseEvent, folderId: number | null): void {
  menuInside.value = false
  menuFolderId.value = folderId
  menuX.value = event.clientX
  menuY.value = event.clientY
  menuOpen.value = true
  requestAnimationFrame(placeMenu)
}

async function addFolder(): Promise<void> {
  menuOpen.value = false
  if (createPackage.isPending.value) return
  if (!canAddFolder.value) {
    notify.errorKey('settings.knowledge.folderLimit')
    return
  }
  const name =
    folders.value.length === 0
      ? draftName.value.trim() || t('settings.knowledge.defaultPackage')
      : t('settings.knowledge.folderName', { n: folders.value.length + 1 })
  try {
    await createPackage.mutateAsync({
      name,
      source: 'knowledge_space',
    })
    draftName.value = ''
    useKnowledgeSpace()
  } catch {
    return
  }
}

async function removeFolder(): Promise<void> {
  const current = menuFolder.value
  menuOpen.value = false
  if (!current || deletePackage.isPending.value) return
  try {
    await swissGlassConfirm(t('fileCenter.confirmDeletePackage'), t('fileCenter.deletePackage'), {
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })
    await deletePackage.mutateAsync(current.id)
    if (selectedId.value === current.id) {
      selectedId.value = null
    }
    if (openedId.value === current.id) openedId.value = null
  } catch (error) {
    if (error === 'cancel') return
  }
}

function closeMenu(event: MouseEvent): void {
  const root = menuRoot.value
  if (root && event.target instanceof Node && root.contains(event.target)) return
  menuOpen.value = false
}

function bindRenameInput(element: unknown): void {
  renameInput.value = element instanceof HTMLInputElement ? element : null
}

function beginRename(): void {
  const id = menuFolderId.value
  const folder = id === null ? null : (folders.value.find((item) => item.id === id) ?? null)
  menuOpen.value = false
  renamingId.value = id
  renameDraft.value = folder
    ? folderLabel(folder)
    : draftName.value || t('settings.knowledge.defaultPackage')
  renaming.value = true
  requestAnimationFrame(() => renameInput.value?.focus())
}

function cancelRename(): void {
  renameCancelled.value = true
  renaming.value = false
}

async function commitRename(): Promise<void> {
  if (renameCancelled.value) {
    renameCancelled.value = false
    return
  }
  const name = renameDraft.value.trim()
  const id = renamingId.value
  renaming.value = false
  if (!name) return
  const current = id === null ? null : (folders.value.find((item) => item.id === id) ?? null)
  if (!current) {
    draftName.value = name
    return
  }
  if (name === folderLabel(current)) return
  try {
    await updatePackage.mutateAsync({ packageId: current.id, name })
  } catch {
    return
  }
}

async function emptyFiles(): Promise<void> {
  const id = menuFolderId.value
  const folder = menuFolder.value
  menuOpen.value = false
  if (id === null || !folder || folder.document_count === 0 || deleteSource.isPending.value) return
  try {
    await swissGlassConfirm(
      t('settings.knowledge.emptyFilesConfirm'),
      t('settings.knowledge.emptyFiles'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
    const detail = await apiRequestJson<PackageDetailResponse>(
      `/api/knowledge-space/packages/${id}`
    )
    for (const doc of detail.documents) {
      await deleteSource.mutateAsync({ packageId: id, documentId: doc.id })
    }
  } catch (error) {
    if (error === 'cancel') return
  }
}

async function removeDocument(documentId: number): Promise<boolean> {
  const id = packageId.value
  if (id === null) return false
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
    await deleteSource.mutateAsync({ packageId: id, documentId })
    return true
  } catch (error) {
    if (error === 'cancel') return false
    return false
  }
}

async function deletePicked(): Promise<void> {
  const id = pickedDocId.value
  if (id === null) return
  if (await removeDocument(id)) pickedDocId.value = null
}

function extensionOf(name: string): string {
  const parts = name.split('.')
  return parts.length > 1 ? (parts.pop() ?? '').toLowerCase() : ''
}

function rejectFile(file: File): boolean {
  if (file.size > MAX_FILE_BYTES) {
    notify.errorKey('knowledge.upload.fileTooLarge')
    return true
  }
  if (!ALLOWED_EXTENSIONS.includes(extensionOf(file.name))) {
    notify.errorKey('knowledge.upload.unsupportedType')
    return true
  }
  return false
}

function onPanelMenu(event: MouseEvent): void {
  if (openedId.value === null || event.target instanceof HTMLInputElement) return
  event.preventDefault()
  menuInside.value = true
  menuFolderId.value = openedId.value
  menuX.value = event.clientX
  menuY.value = event.clientY
  menuOpen.value = true
  requestAnimationFrame(placeMenu)
}

function pickUploads(): void {
  menuOpen.value = false
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

function onPanelDragOver(event: DragEvent): void {
  if (openedId.value === null || !event.dataTransfer?.types.includes('Files')) return
  event.preventDefault()
  dropping.value = true
}

function onPanelDragLeave(event: DragEvent): void {
  const next = event.relatedTarget
  const current = event.currentTarget
  if (current instanceof Node && next instanceof Node && current.contains(next)) return
  dropping.value = false
}

function onPanelDrop(event: DragEvent): void {
  if (openedId.value === null) return
  event.preventDefault()
  dropping.value = false
  void storeFiles(Array.from(event.dataTransfer?.files ?? []))
}

function connectIma(): void {
  if (!imaClientId.value.trim() || !imaApiKey.value.trim()) {
    notify.errorKey('settings.knowledge.imaNeedBoth')
    return
  }
  imaConnected.value = true
  voidKnowledgeSpace()
  notify.warningKey('settings.knowledge.imaHeld')
}

function onMenuKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') menuOpen.value = false
}

watch(menuOpen, (open) => {
  if (open) {
    document.addEventListener('click', closeMenu)
    document.addEventListener('keydown', onMenuKey)
    return
  }
  document.removeEventListener('click', closeMenu)
  document.removeEventListener('keydown', onMenuKey)
})

onBeforeUnmount(() => {
  clearFolderClick()
  document.removeEventListener('click', closeMenu)
  document.removeEventListener('keydown', onMenuKey)
})
</script>

<template>
  <div class="knowledge-settings user-settings-tab-pad">
    <section
      class="knowledge-settings__panel"
      :class="{ 'is-off': imaConnected, 'is-dropping': dropping }"
      @contextmenu="onPanelMenu"
      @dragover="onPanelDragOver"
      @dragleave="onPanelDragLeave"
      @drop="onPanelDrop"
    >
      <SettingsKnowledgeBrowser
        v-if="openedPackage"
        v-model:rename-draft="renameDraft"
        :folder-name="folderLabel(openedPackage)"
        :renaming="renaming && renamingId === openedPackage.id"
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
        @commit-rename="commitRename"
        @cancel-rename="cancelRename"
        @pick="pickedDocId = $event"
        @clear-pick="pickedDocId = null"
        @upload="pickUploads"
        @delete-picked="deletePicked"
        @bind-rename="bindRenameInput"
      />
      <div
        v-else
        class="knowledge-settings__folders"
      >
        <button
          v-if="folders.length === 0"
          type="button"
          class="knowledge-settings__folder"
          :class="{ 'is-selected': placeholderOn }"
          @click="onPlaceholderClick"
        >
          <span
            class="knowledge-settings__glyph"
            @contextmenu.prevent.stop="openMenu($event, null)"
          >
            <Folder
              :size="40"
              :stroke-width="1.5"
            />
            <span
              v-if="placeholderOn"
              class="knowledge-settings__check"
            >
              <Check
                :size="12"
                :stroke-width="3"
              />
            </span>
          </span>
          <input
            v-if="renaming && renamingId === null"
            :ref="bindRenameInput"
            v-model="renameDraft"
            class="knowledge-settings__rename"
            type="text"
            maxlength="200"
            :placeholder="t('settings.knowledge.defaultPackage')"
            @click.stop
            @keydown.enter.prevent="commitRename"
            @keydown.esc.prevent="cancelRename"
            @blur="commitRename"
          />
          <span
            v-else
            class="knowledge-settings__caption"
          >
            {{ draftName || t('settings.knowledge.defaultPackage') }}
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
          :class="[folderToneClass(folder), { 'is-selected': folder.id === selectedId }]"
          @click="onFolderClick(folder.id)"
        >
          <span
            class="knowledge-settings__glyph"
            @contextmenu.prevent.stop="openMenu($event, folder.id)"
          >
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
              v-if="folder.id === selectedId"
              class="knowledge-settings__check"
            >
              <Check
                :size="12"
                :stroke-width="3"
              />
            </span>
          </span>
          <input
            v-if="renaming && folder.id === renamingId"
            :ref="bindRenameInput"
            v-model="renameDraft"
            class="knowledge-settings__rename"
            type="text"
            maxlength="200"
            :placeholder="t('settings.knowledge.defaultPackage')"
            @click.stop
            @keydown.enter.prevent="commitRename"
            @keydown.esc.prevent="cancelRename"
            @blur="commitRename"
          />
          <span
            v-else
            class="knowledge-settings__caption"
          >
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

    <p class="language-settings-swiss__hint">
      <I18nText k="settings.knowledge.panelHint" />
    </p>
    <p class="language-settings-swiss__hint">
      <I18nText k="settings.knowledge.chooseOne" />
    </p>

    <input
      ref="fileInput"
      class="knowledge-settings__file"
      type="file"
      multiple
      accept=".pdf,.docx,.txt,.md,.jpg,.jpeg,.png"
      @change="onPick"
    />

    <div class="knowledge-settings__ima">
      <button
        type="button"
        class="knowledge-settings__ima-toggle"
        :aria-expanded="imaOpen"
        @click="imaOpen = !imaOpen"
      >
        <I18nText k="settings.knowledge.imaButton" />
      </button>
      <div
        v-if="imaOpen"
        class="knowledge-settings__ima-body"
      >
        <p class="language-settings-swiss__hint">
          <I18nText k="settings.knowledge.imaHint" />
        </p>
        <label class="knowledge-settings__field">
          <span><I18nText k="settings.knowledge.imaClientId" /></span>
          <input
            v-model="imaClientId"
            type="text"
            autocomplete="off"
            spellcheck="false"
          />
        </label>
        <label class="knowledge-settings__field">
          <span><I18nText k="settings.knowledge.imaApiKey" /></span>
          <input
            v-model="imaApiKey"
            type="password"
            autocomplete="off"
            spellcheck="false"
          />
        </label>
        <div class="knowledge-settings__actions">
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
            @click="connectIma"
          >
            <I18nText k="settings.knowledge.imaConnect" />
          </button>
          <a
            class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
            href="https://ima.qq.com"
            target="_blank"
            rel="noopener noreferrer"
          >
            <I18nText k="settings.knowledge.imaOpen" />
          </a>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="menuOpen"
        ref="menuRoot"
        class="knowledge-settings__menu"
        :style="{ left: `${menuX}px`, top: `${menuY}px` }"
        role="menu"
        @click.stop
        @contextmenu.prevent
      >
        <button
          v-if="menuInside"
          type="button"
          class="knowledge-settings__menu-item"
          role="menuitem"
          @click="goBack"
        >
          <I18nText k="settings.knowledge.goBack" />
        </button>
        <button
          v-if="menuInside"
          type="button"
          class="knowledge-settings__menu-item"
          role="menuitem"
          :disabled="
            uploadFile.isPending.value ||
            startProcessing.isPending.value ||
            documents.length >= MAX_FILES_PER_PACKAGE
          "
          @click="pickUploads"
        >
          <I18nText k="settings.knowledge.uploadFiles" />
        </button>
        <button
          type="button"
          class="knowledge-settings__menu-item"
          role="menuitem"
          :disabled="!canAddFolder || createPackage.isPending.value"
          @click="addFolder"
        >
          <I18nText k="settings.knowledge.addFolder" />
        </button>
        <button
          type="button"
          class="knowledge-settings__menu-item"
          role="menuitem"
          :disabled="!menuFolder || deletePackage.isPending.value"
          @click="removeFolder"
        >
          <I18nText k="settings.knowledge.deleteFolder" />
        </button>
        <button
          type="button"
          class="knowledge-settings__menu-item"
          role="menuitem"
          @click="beginRename"
        >
          <I18nText k="settings.knowledge.rename" />
        </button>
        <button
          type="button"
          class="knowledge-settings__menu-item"
          role="menuitem"
          :disabled="!menuFolder || menuFolder.document_count === 0 || deleteSource.isPending.value"
          @click="emptyFiles"
        >
          <I18nText k="settings.knowledge.emptyFiles" />
        </button>
      </div>
    </Teleport>
  </div>
</template>
