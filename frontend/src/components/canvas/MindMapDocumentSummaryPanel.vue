<script setup lang="ts">
/**
 * Document Summary (文档总结) — Knowledge Space portal on the mind map canvas.
 *
 * Resumes an existing session package on open; creates one only on first ingest
 * or when the user requests a chat pairing code.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import {
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
  ImageUp,
  Link2,
  Loader2,
  MessageSquare,
  Sparkles,
  Trash2,
  Upload,
  X,
} from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import MindMapSidePanelCloseButton from '@/components/canvas/MindMapSidePanelCloseButton.vue'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import {
  useFileCenterMutations,
  usePackageDetail,
} from '@/composables/fileCenter/useFileCenter'
import { useFileCenterActivePackage } from '@/composables/fileCenter/useFileCenterActivePackage'
import { useChatHandoff } from '@/composables/mindMap/useChatHandoff'
import { useMindMapDocumentSummary } from '@/composables/mindMap/useMindMapDocumentSummary'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { useDiagramStore } from '@/stores'

type SummaryTab = 'document' | 'image' | 'web' | 'chat'

const ALLOWED_IMAGE_MIME = new Set(['image/jpeg', 'image/png', 'image/jpg'])
const MAX_IMAGE_BYTES = 10 * 1024 * 1024

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const { featureKnowledgeSpace } = useFeatureFlags()
const useMindMapV2 = useMindMapV2Chrome()

const featureEnabled = computed(() => featureKnowledgeSpace.value && useMindMapV2.value)

const {
  linkedPackage,
  activePackageId,
  activeDiagramId,
  resolveSession,
  ensureSession,
  sessionStarting,
} = useFileCenterActivePackage(featureEnabled)

const detailQuery = usePackageDetail(activePackageId, { enabled: featureEnabled })
const { uploadFile, ingestText, ingestWebUrl, deleteSource, updatePackage } = useFileCenterMutations()
const {
  isGenerating,
  isIndexingCorpus,
  isAdding,
  generateFromPackage,
  validateDocumentFile,
  MAX_CONTENT_LENGTH,
} = useMindMapDocumentSummary()

const {
  pairingCode,
  handoffStatus,
  expiresInSeconds,
  isMinting,
  mintError,
  mintPairingCode,
} = useChatHandoff(activePackageId)

const activeTab = ref<SummaryTab>('document')
const corpusExpanded = ref(true)
const pastedText = ref('')
const uploadedDocName = ref('')
const uploadedDocFile = ref<File | null>(null)
const webUrl = ref('')
const imageFile = ref<File | null>(null)
const imagePreviewUrl = ref<string | null>(null)
const editingName = ref(false)
const nameDraft = ref('')

const docInputRef = ref<HTMLInputElement | null>(null)
const imageInputRef = ref<HTMLInputElement | null>(null)

const tabs: Array<{ id: SummaryTab; labelKey: string }> = [
  { id: 'document', labelKey: 'canvas.mindMapDocumentSummary.tabDocument' },
  { id: 'image', labelKey: 'canvas.mindMapDocumentSummary.tabImage' },
  { id: 'web', labelKey: 'canvas.mindMapDocumentSummary.tabWeb' },
  { id: 'chat', labelKey: 'canvas.mindMapDocumentSummary.tabChat' },
]

const collabActive = computed(() => diagramStore.collabSessionActive)
const documents = computed(() => detailQuery.data.value?.documents ?? [])
const completedCount = computed(
  () => documents.value.filter((doc) => doc.status === 'completed').length
)
const isIndexing = computed(
  () =>
    isIndexingCorpus.value ||
    documents.value.some((doc) => doc.status === 'processing')
)
const canGenerate = computed(
  () =>
    !isGenerating.value &&
    !collabActive.value &&
    documents.value.length > 0 &&
    activePackageId.value !== null
)

const pairingMinutes = computed(() => Math.max(1, Math.round(expiresInSeconds.value / 60)))

const fileReaderDownloadUrl = '/api/downloads/mindgraph-file-reader'

async function bootstrapSession(): Promise<void> {
  await resolveSession()
}

async function startChatPairing(): Promise<void> {
  if (collabActive.value || isMinting.value) {
    return
  }
  try {
    if (activePackageId.value === null) {
      await ensureSession()
    }
    const code = await mintPairingCode()
    if (!code && mintError.value) {
      notify.error(t('canvas.mindMapDocumentSummary.chatMintFailed'))
    }
  } catch (error) {
    console.error('[DocumentSummary] chat pairing failed:', error)
    notify.error(t('canvas.mindMapDocumentSummary.chatMintFailed'))
  }
}

onMounted(() => {
  if (featureEnabled.value) {
    void bootstrapSession()
  }
})

watch(featureEnabled, (enabled) => {
  if (enabled) {
    void bootstrapSession()
  }
})

onUnmounted(() => {
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
  }
})

function handleClose(): void {
  emit('close')
}

function switchTab(tab: SummaryTab): void {
  activeTab.value = tab
}

function statusLabel(status: string): string {
  switch (status) {
    case 'completed':
      return t('canvas.mindMapDocumentSummary.statusReady')
    case 'failed':
      return t('canvas.mindMapDocumentSummary.statusFailed')
    case 'processing':
      return t('canvas.mindMapDocumentSummary.statusIndexing')
    default:
      return t('canvas.mindMapDocumentSummary.statusPending')
  }
}

function startEditName(): void {
  if (collabActive.value) return
  nameDraft.value = linkedPackage.value?.name ?? ''
  editingName.value = true
}

async function commitName(): Promise<void> {
  if (collabActive.value) return
  editingName.value = false
  const id = activePackageId.value
  const name = nameDraft.value.trim()
  if (id === null || !name || name === linkedPackage.value?.name) return
  await updatePackage.mutateAsync({ packageId: id, name })
}

async function handleDeleteSource(documentId: number): Promise<void> {
  if (collabActive.value) {
    notify.warning(t('canvas.mindMapDocumentSummary.collabDisabled'))
    return
  }
  const id = activePackageId.value
  if (id === null) return
  await deleteSource.mutateAsync({ packageId: id, documentId })
}

function openDocPicker(): void {
  docInputRef.value?.click()
}

function openImagePicker(): void {
  imageInputRef.value?.click()
}

async function handleDocFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!validateDocumentFile(file)) return
  uploadedDocFile.value = file
  uploadedDocName.value = file.name
}

function handleImageFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  const ext = file.name.includes('.') ? `.${file.name.split('.').pop()?.toLowerCase()}` : ''
  if (!ALLOWED_IMAGE_MIME.has(file.type) && ext !== '.jpg' && ext !== '.jpeg' && ext !== '.png') {
    notify.warning(t('canvas.mindMapDocumentSummary.invalidImageType'))
    return
  }
  if (file.size > MAX_IMAGE_BYTES) {
    notify.warning(t('canvas.mindMapDocumentSummary.imageTooLarge'))
    return
  }

  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
  }
  imageFile.value = file
  imagePreviewUrl.value = URL.createObjectURL(file)
}

function clearImage(): void {
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
  }
  imageFile.value = null
  imagePreviewUrl.value = null
}

async function handleAddToCorpus(): Promise<void> {
  if (collabActive.value) {
    notify.warning(t('canvas.mindMapDocumentSummary.collabDisabled'))
    return
  }

  isAdding.value = true
  try {
    let id = activePackageId.value
    if (id === null) {
      const pkg = await ensureSession()
      id = pkg.id
    }

    if (activeTab.value === 'document') {
      if (uploadedDocFile.value) {
        await uploadFile.mutateAsync({ packageId: id, file: uploadedDocFile.value })
        uploadedDocFile.value = null
        uploadedDocName.value = ''
      } else {
        const content = pastedText.value.trim().slice(0, MAX_CONTENT_LENGTH)
        if (!content) {
          notify.warning(t('canvas.mindMapDocumentSummary.emptyDocument'))
          return
        }
        await ingestText.mutateAsync({
          packageId: id,
          payload: { content, title: uploadedDocName.value.trim() || undefined },
        })
        pastedText.value = ''
      }
    } else if (activeTab.value === 'image' && imageFile.value) {
      await uploadFile.mutateAsync({ packageId: id, file: imageFile.value })
      clearImage()
    } else if (activeTab.value === 'web') {
      const url = webUrl.value.trim()
      if (!url) {
        notify.warning(t('canvas.mindMapDocumentSummary.emptyUrl'))
        return
      }
      await ingestWebUrl.mutateAsync({ packageId: id, payload: { page_url: url } })
      webUrl.value = ''
    } else {
      return
    }
    notify.success(t('canvas.mindMapDocumentSummary.ingestSuccess'))
  } catch (error) {
    console.error('[DocumentSummary] ingest failed:', error)
  } finally {
    isAdding.value = false
  }
}

async function handleGenerate(): Promise<void> {
  if (collabActive.value || !canGenerate.value) return
  await generateFromPackage({
    packageId: activePackageId.value,
    diagramId: activeDiagramId.value,
    topicHint: diagramStore.effectiveTitle || undefined,
  })
}

const canAdd = computed(() => {
  if (collabActive.value || isAdding.value || sessionStarting.value) return false
  if (activeTab.value === 'document') {
    return pastedText.value.trim().length > 0 || uploadedDocFile.value !== null
  }
  if (activeTab.value === 'image') {
    return imageFile.value !== null
  }
  if (activeTab.value === 'web') {
    return webUrl.value.trim().length > 0
  }
  return false
})
</script>

<template>
  <aside
    class="mind-map-document-summary-panel pointer-events-auto absolute inset-y-3 left-3 z-40 flex w-80 flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm"
    :aria-label="t('canvas.mindMapSideToolbar.documentSummary')"
  >
    <header class="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-3 py-3">
      <h3 class="truncate text-sm font-semibold text-slate-800">
        {{ t('canvas.mindMapSideToolbar.documentSummary') }}
      </h3>
      <MindMapSidePanelCloseButton @close="handleClose" />
    </header>

    <div
      v-if="!featureEnabled"
      class="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center"
    >
      <p class="text-sm font-medium text-slate-600">
        {{ t('canvas.mindMapDocumentSummary.featureDisabledTitle') }}
      </p>
      <p class="text-xs leading-relaxed text-slate-400">
        {{ t('canvas.mindMapDocumentSummary.featureDisabledHint') }}
      </p>
    </div>

    <template v-else>
      <div
        v-if="sessionStarting"
        class="flex items-center justify-center gap-2 border-b border-slate-100 px-3 py-2 text-xs text-slate-500"
      >
        <Loader2
          class="h-3.5 w-3.5 animate-spin"
          :stroke-width="2"
        />
        …
      </div>

      <div
        v-if="!activeDiagramId"
        class="border-b border-amber-100 bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-800"
      >
        {{ t('canvas.mindMapDocumentSummary.saveDiagramHint') }}
      </div>

      <p class="shrink-0 px-3 pt-3 text-[11px] leading-relaxed text-slate-500">
        {{ t('canvas.mindMapDocumentSummary.intro') }}
      </p>

      <!-- Corpus header -->
      <div class="mx-3 mt-2 shrink-0 rounded-xl border border-slate-100 bg-slate-50/80">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left"
          @click="corpusExpanded = !corpusExpanded"
        >
          <div class="min-w-0 flex-1">
            <div
              v-if="!editingName"
              class="truncate text-xs font-semibold text-slate-800"
              @click.stop="startEditName"
            >
              {{ linkedPackage?.name || t('canvas.mindMapDocumentSummary.noPackageYet') }}
            </div>
            <input
              v-else
              v-model="nameDraft"
              type="text"
              class="w-full rounded border border-blue-300 bg-white px-2 py-1 text-xs"
              @blur="commitName"
              @keyup.enter="commitName"
              @click.stop
            />
            <div class="mt-1 flex items-center gap-1.5 text-[10px] text-slate-500">
              <span
                class="inline-block h-1.5 w-1.5 rounded-full"
                :class="completedCount > 0 ? 'bg-emerald-500' : 'bg-slate-300'"
              />
              {{
                t('canvas.mindMapDocumentSummary.corpusStatus', {
                  completed: completedCount,
                  total: documents.length,
                })
              }}
              <Loader2
                v-if="isIndexing"
                class="h-3 w-3 animate-spin text-blue-500"
                :stroke-width="2"
              />
            </div>
          </div>
          <component
            :is="corpusExpanded ? ChevronUp : ChevronDown"
            class="h-4 w-4 shrink-0 text-slate-400"
            :stroke-width="2"
          />
        </button>

        <div
          v-if="corpusExpanded"
          class="max-h-28 overflow-y-auto border-t border-slate-100 px-2 py-2"
        >
          <p
            v-if="documents.length === 0"
            class="px-1 py-1 text-[11px] text-slate-400"
          >
            {{ t('canvas.mindMapDocumentSummary.noSources') }}
          </p>
          <div
            v-for="doc in documents"
            :key="doc.id"
            class="group flex items-center gap-2 rounded-lg px-1.5 py-1.5 hover:bg-white"
          >
            <FileText
              class="h-3.5 w-3.5 shrink-0 text-slate-400"
              :stroke-width="2"
            />
            <div class="min-w-0 flex-1">
              <p class="truncate text-[11px] font-medium text-slate-700">
                {{ doc.file_name }}
              </p>
              <p
                class="text-[10px]"
                :class="{
                  'text-emerald-600': doc.status === 'completed',
                  'text-rose-500': doc.status === 'failed',
                  'text-blue-500': doc.status !== 'completed' && doc.status !== 'failed',
                }"
              >
                {{ statusLabel(doc.status) }}
              </p>
            </div>
            <button
              type="button"
              class="shrink-0 text-slate-300 opacity-0 transition-opacity hover:text-rose-500 group-hover:opacity-100"
              :aria-label="t('common.delete')"
              @click="handleDeleteSource(doc.id)"
            >
              <Trash2
                class="h-3 w-3"
                :stroke-width="2"
              />
            </button>
          </div>
        </div>
      </div>

      <div class="doc-summary-tab-strip mx-3 mt-3 shrink-0">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          class="doc-summary-tab"
          :class="{ 'doc-summary-tab--active': activeTab === tab.id }"
          @click="switchTab(tab.id)"
        >
          {{ t(tab.labelKey) }}
        </button>
      </div>

      <div class="flex min-h-0 flex-1 flex-col overflow-y-auto px-3 py-3">
        <!-- Document -->
        <div
          v-if="activeTab === 'document'"
          class="flex flex-col gap-3"
        >
          <button
            type="button"
            class="doc-summary-upload-box"
            @click="openDocPicker"
          >
            <Upload
              class="mb-2 h-5 w-5 text-slate-400"
              :stroke-width="1.75"
            />
            <span class="text-sm font-medium text-slate-700">
              {{ t('canvas.mindMapDocumentSummary.uploadDocHint') }}
            </span>
            <span
              v-if="uploadedDocName"
              class="mt-2 max-w-full truncate text-xs font-medium text-blue-600"
            >
              {{ uploadedDocName }}
            </span>
          </button>
          <input
            ref="docInputRef"
            type="file"
            class="hidden"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            @change="handleDocFileChange"
          />
          <textarea
            v-model="pastedText"
            class="doc-summary-textarea w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm leading-relaxed text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
            :placeholder="t('canvas.mindMapDocumentSummary.pastePlaceholder')"
            rows="4"
          />
        </div>

        <!-- Image -->
        <div
          v-else-if="activeTab === 'image'"
          class="flex flex-col gap-3"
        >
          <button
            v-if="!imagePreviewUrl"
            type="button"
            class="doc-summary-upload-box"
            @click="openImagePicker"
          >
            <ImageUp
              class="mb-2 h-5 w-5 text-slate-400"
              :stroke-width="1.75"
            />
            <span class="text-sm font-medium text-slate-700">
              {{ t('canvas.mindMapDocumentSummary.uploadImageHint') }}
            </span>
          </button>
          <div
            v-else
            class="relative overflow-hidden rounded-xl border border-slate-200 bg-slate-50"
          >
            <img
              :src="imagePreviewUrl"
              alt=""
              class="max-h-32 w-full object-contain"
            />
            <button
              type="button"
              class="absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/90 text-slate-500 shadow-sm"
              @click="clearImage"
            >
              <X
                class="h-3.5 w-3.5"
                :stroke-width="2"
              />
            </button>
          </div>
          <input
            ref="imageInputRef"
            type="file"
            class="hidden"
            accept="image/jpeg,image/png,.jpg,.jpeg,.png"
            @change="handleImageFileChange"
          />
        </div>

        <!-- Web -->
        <div
          v-else-if="activeTab === 'web'"
          class="flex flex-col gap-3"
        >
          <div class="relative">
            <Link2
              class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              :stroke-width="2"
            />
            <input
              v-model="webUrl"
              type="url"
              class="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
              :placeholder="t('canvas.mindMapDocumentSummary.webUrlPlaceholder')"
            />
          </div>
          <p class="text-[11px] leading-relaxed text-slate-400">
            {{ t('canvas.mindMapDocumentSummary.webLinkHint') }}
          </p>
        </div>

        <!-- Chat -->
        <div
          v-else
          class="flex flex-col gap-3"
        >
          <p class="text-[11px] leading-relaxed text-slate-500">
            {{ t('canvas.mindMapDocumentSummary.chatIntro') }}
          </p>
          <a
            :href="fileReaderDownloadUrl"
            class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-medium text-blue-700 hover:bg-blue-50"
          >
            <Download
              class="h-4 w-4"
              :stroke-width="2"
            />
            {{ t('canvas.mindMapDocumentSummary.downloadReader') }}
          </a>
          <div class="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-4 text-center">
            <MessageSquare
              class="mx-auto mb-2 h-5 w-5 text-slate-400"
              :stroke-width="1.75"
            />
            <p class="text-xs font-medium text-slate-600">
              {{ t('canvas.mindMapDocumentSummary.pairingCode') }}
            </p>
            <p
              v-if="pairingCode"
              class="mt-2 font-mono text-2xl font-bold tracking-[0.3em] text-slate-800"
            >
              {{ pairingCode }}
            </p>
            <p
              v-else-if="isMinting"
              class="mt-2 text-xs text-slate-400"
            >
              …
            </p>
            <p
              v-if="pairingCode"
              class="mt-1 text-[10px] text-slate-400"
            >
              {{ t('canvas.mindMapDocumentSummary.pairingExpires', { minutes: pairingMinutes }) }}
            </p>
            <p
              v-if="handoffStatus === 'waiting'"
              class="mt-2 text-[11px] text-blue-600"
            >
              {{ t('canvas.mindMapDocumentSummary.chatWaiting') }}
            </p>
            <p
              v-else-if="handoffStatus === 'received'"
              class="mt-2 text-[11px] font-medium text-emerald-600 animate-pulse"
            >
              {{ t('canvas.mindMapDocumentSummary.chatReceived') }}
            </p>
            <p
              v-else-if="handoffStatus === 'indexing'"
              class="mt-2 text-[11px] text-blue-600"
            >
              {{ t('canvas.mindMapDocumentSummary.chatIndexing') }}
            </p>
            <p
              v-else-if="handoffStatus === 'done'"
              class="mt-2 text-[11px] text-emerald-600"
            >
              {{ t('canvas.mindMapDocumentSummary.chatDone') }}
            </p>
            <p
              v-else-if="handoffStatus === 'failed'"
              class="mt-2 text-[11px] text-rose-500"
            >
              {{ t('canvas.mindMapDocumentSummary.chatHandoffFailed') }}
            </p>
            <p
              v-else-if="handoffStatus === 'expired'"
              class="mt-2 text-[11px] text-rose-500"
            >
              {{ t('canvas.mindMapDocumentSummary.chatExpired') }}
            </p>
            <button
              v-if="!pairingCode && handoffStatus !== 'done'"
              type="button"
              class="mt-3 rounded-lg bg-blue-600 px-3 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isMinting || collabActive"
              @click="startChatPairing()"
            >
              {{
                isMinting
                  ? '…'
                  : t('canvas.mindMapDocumentSummary.startPairingCode')
              }}
            </button>
            <button
              v-if="handoffStatus === 'expired' || handoffStatus === 'failed' || mintError"
              type="button"
              class="mt-2 text-[11px] font-medium text-blue-600 hover:underline"
              :disabled="isMinting || collabActive"
              @click="startChatPairing()"
            >
              {{ t('canvas.mindMapDocumentSummary.refreshPairingCode') }}
            </button>
          </div>
        </div>

        <button
          v-if="activeTab !== 'chat'"
          type="button"
          class="doc-summary-add-btn mt-3 w-full shrink-0"
          :disabled="!canAdd"
          @click="handleAddToCorpus"
        >
          {{ t('canvas.mindMapDocumentSummary.addToCorpus') }}
        </button>
      </div>

      <div class="shrink-0 border-t border-slate-100 px-3 py-3">
        <button
          type="button"
          class="one-sentence-generate-btn w-full"
          :disabled="!canGenerate"
          :title="collabActive ? t('canvas.mindMapDocumentSummary.collabDisabled') : undefined"
          @click="handleGenerate"
        >
          <Sparkles
            class="h-4 w-4 shrink-0"
            :stroke-width="2"
          />
          {{
            isGenerating
              ? t('canvas.toolbar.aiGenerating')
              : t('canvas.mindMapDocumentSummary.generateButton')
          }}
        </button>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.mind-map-document-summary-panel {
  max-height: calc(100% - 1.5rem);
}

.doc-summary-tab-strip {
  display: flex;
  gap: 4px;
  padding: 4px;
  overflow-x: auto;
  border-radius: 12px;
  background: rgb(241 245 249);
  scrollbar-width: thin;
}

.doc-summary-tab {
  flex: 1 0 auto;
  min-width: 0;
  padding: 7px 8px;
  border: none;
  border-radius: 9px;
  background: transparent;
  font-size: 11px;
  font-weight: 500;
  color: rgb(100 116 139);
  cursor: pointer;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.doc-summary-tab--active {
  background: white;
  color: rgb(30 41 59);
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.08);
}

.doc-summary-upload-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 100px;
  padding: 14px;
  border: 1.5px dashed rgb(203 213 225);
  border-radius: 14px;
  background: rgb(248 250 252);
  text-align: center;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.doc-summary-upload-box:hover {
  border-color: rgb(147 197 253);
  background: rgb(239 246 255);
}

.doc-summary-textarea {
  min-height: 88px;
}

.doc-summary-add-btn {
  padding: 9px 14px;
  border: 1px solid rgb(203 213 225);
  border-radius: 12px;
  background: white;
  font-size: 13px;
  font-weight: 500;
  color: rgb(51 65 85);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.doc-summary-add-btn:hover:not(:disabled) {
  border-color: rgb(147 197 253);
  background: rgb(248 250 252);
}

.doc-summary-add-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.one-sentence-generate-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, rgb(124 58 237) 0%, rgb(79 70 229) 100%);
  font-size: 14px;
  font-weight: 500;
  color: white;
  box-shadow: 0 2px 8px rgb(124 58 237 / 0.28);
  cursor: pointer;
  transition:
    opacity 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}

.one-sentence-generate-btn:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgb(124 58 237 / 0.35);
  transform: translateY(-1px);
}

.one-sentence-generate-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}
</style>
