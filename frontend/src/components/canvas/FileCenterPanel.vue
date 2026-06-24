<script setup lang="ts">
/**
 * File Center (文件中心) — Zotero-like package panel for the mind map canvas.
 *
 * Manages the knowledge package bound to the current diagram: create/rename,
 * add sources (file upload, pasted text, web URL), watch indexing status, and
 * delete sources. Completed sources scope RAG retrieval for diagram completion.
 */
import { computed, ref, watch } from 'vue'

import { ElMessageBox } from 'element-plus'

import { FileText, Globe, Link2, Loader2, Plus, Trash2, Upload, X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import {
  useFileCenterMutations,
  usePackageDetail,
} from '@/composables/fileCenter/useFileCenter'
import {
  useFileCenterActivePackage,
} from '@/composables/fileCenter/useFileCenterActivePackage'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { useDiagramStore } from '@/stores'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'

type AddTab = 'file' | 'paste' | 'web'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const diagramStore = useDiagramStore()
const { featureKnowledgeSpace } = useFeatureFlags()

const useMindMapV2 = useMindMapV2Chrome()
const featureEnabled = computed(() => featureKnowledgeSpace.value && useMindMapV2.value)

const { linkedPackage, activePackageId, activeDiagramId, rememberPendingPackage } =
  useFileCenterActivePackage(featureEnabled)

const detailQuery = usePackageDetail(activePackageId, { enabled: featureEnabled })

const {
  createPackage,
  updatePackage,
  deletePackage,
  uploadFile,
  ingestText,
  ingestWeb,
  deleteSource,
} = useFileCenterMutations()

const newPackageName = ref('')
const activeTab = ref<AddTab>('file')
const pastedText = ref('')
const pasteTitle = ref('')
const webUrl = ref('')
const webPageContent = ref('')
const editingName = ref(false)
const nameDraft = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

const collabActive = computed(() => diagramStore.collabSessionActive)

const documents = computed(() => detailQuery.data.value?.documents ?? [])
const completedCount = computed(
  () => documents.value.filter((doc) => doc.status === 'completed').length
)
const isIndexing = computed(() =>
  documents.value.some((doc) => doc.status === 'pending' || doc.status === 'processing')
)
const ragActive = computed(
  () => activeDiagramId.value !== null && completedCount.value > 0
)
const diagramSaved = computed(() => activeDiagramId.value !== null)

function defaultPackageName(): string {
  return (
    diagramStore.getTopicNodeText?.() ||
    diagramStore.effectiveTitle ||
    t('fileCenter.defaultPackageName')
  )
}

watch(
  linkedPackage,
  (pkg) => {
    if (pkg && !newPackageName.value) {
      newPackageName.value = pkg.name ?? ''
    }
  },
  { immediate: true }
)

function handleClose(): void {
  emit('close')
}

async function handleCreatePackage(): Promise<void> {
  const name = (newPackageName.value || defaultPackageName()).trim()
  if (!name) return
  const created = await createPackage.mutateAsync({
    name,
    diagram_id: activeDiagramId.value ?? undefined,
    source: 'canvas',
  })
  if (!activeDiagramId.value) {
    rememberPendingPackage(created.id)
  }
}

function startEditName(): void {
  nameDraft.value = linkedPackage.value?.name ?? ''
  editingName.value = true
}

async function commitName(): Promise<void> {
  editingName.value = false
  const id = activePackageId.value
  const name = nameDraft.value.trim()
  if (id === null || !name || name === linkedPackage.value?.name) return
  await updatePackage.mutateAsync({ packageId: id, name })
}

function openFilePicker(): void {
  fileInputRef.value?.click()
}

async function handleFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  const id = activePackageId.value
  if (!file || id === null) return
  await uploadFile.mutateAsync({ packageId: id, file })
}

async function handleAddPaste(): Promise<void> {
  const id = activePackageId.value
  const content = pastedText.value.trim()
  if (id === null || !content) return
  await ingestText.mutateAsync({
    packageId: id,
    payload: { content, title: pasteTitle.value.trim() || undefined },
  })
  pastedText.value = ''
  pasteTitle.value = ''
}

async function handleAddWeb(): Promise<void> {
  const id = activePackageId.value
  const url = webUrl.value.trim()
  const content = webPageContent.value.trim()
  if (id === null || !url || !content) return
  await ingestWeb.mutateAsync({
    packageId: id,
    payload: { page_content: content, page_url: url },
  })
  webUrl.value = ''
  webPageContent.value = ''
}

async function handleDeleteSource(documentId: number): Promise<void> {
  const id = activePackageId.value
  if (id === null) return
  await deleteSource.mutateAsync({ packageId: id, documentId })
}

async function handleDeletePackage(): Promise<void> {
  const id = activePackageId.value
  if (id === null) return
  try {
    await ElMessageBox.confirm(
      t('fileCenter.confirmDeletePackage'),
      t('fileCenter.deletePackage'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  await deletePackage.mutateAsync(id)
  newPackageName.value = ''
}

function statusLabel(status: string): string {
  switch (status) {
    case 'completed':
      return t('fileCenter.statusReady')
    case 'failed':
      return t('fileCenter.statusFailed')
    default:
      return t('fileCenter.statusIndexing')
  }
}

function chunkingLabel(doc: KnowledgeDocument): string {
  if (!doc.chunking_engine) {
    return ''
  }
  const engine = doc.chunking_engine === 'mindchunk' ? 'MindChunk' : 'semchunk'
  return doc.chunking_mode === 'hierarchical' ? `${engine} · H` : engine
}
</script>

<template>
  <aside
    class="file-center-panel pointer-events-auto absolute inset-y-3 left-3 z-40 flex w-80 flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm"
    :aria-label="t('canvas.mindMapSideToolbar.documentSummary')"
  >
    <header
      class="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-3 py-3"
    >
      <h3 class="truncate text-sm font-semibold text-slate-800">
        {{ t('canvas.mindMapSideToolbar.documentSummary') }}
      </h3>
      <button
        type="button"
        class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
        :aria-label="t('canvas.mindMapSideToolbar.closePanel')"
        @click="handleClose"
      >
        <X
          class="h-4 w-4"
          :stroke-width="2"
        />
      </button>
    </header>

    <!-- Feature disabled -->
    <div
      v-if="!featureEnabled"
      class="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center"
    >
      <p class="text-sm font-medium text-slate-600">
        {{ t('fileCenter.featureDisabledTitle') }}
      </p>
      <p class="text-xs leading-relaxed text-slate-400">
        {{ t('fileCenter.featureDisabledHint') }}
      </p>
    </div>

    <!-- No package yet -->
    <div
      v-else-if="!linkedPackage"
      class="flex min-h-0 flex-1 flex-col gap-3 px-4 py-5"
    >
      <p class="text-xs leading-relaxed text-slate-500">
        {{ t('fileCenter.intro') }}
      </p>
      <label class="text-xs font-semibold text-slate-700">
        {{ t('fileCenter.packageNameLabel') }}
      </label>
      <input
        v-model="newPackageName"
        type="text"
        class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
        :placeholder="defaultPackageName()"
      />
      <button
        type="button"
        class="file-center-primary-btn"
        :disabled="createPackage.isPending.value"
        @click="handleCreatePackage"
      >
        <Plus
          class="h-4 w-4"
          :stroke-width="2"
        />
        {{ t('fileCenter.createPackage') }}
      </button>
    </div>

    <!-- Package detail -->
    <div
      v-else
      class="flex min-h-0 flex-1 flex-col overflow-y-auto"
    >
      <div
        v-if="!diagramSaved"
        class="border-b border-amber-100 bg-amber-50 px-4 py-2.5 text-[11px] leading-relaxed text-amber-800"
      >
        {{ t('fileCenter.saveDiagramForRag') }}
      </div>
      <!-- Package name + corpus status -->
      <div class="border-b border-slate-100 px-4 py-3">
        <div
          v-if="!editingName"
          class="flex items-center justify-between gap-2"
        >
          <button
            type="button"
            class="truncate text-left text-sm font-semibold text-slate-800 hover:text-blue-600"
            @click="startEditName"
          >
            {{ linkedPackage.name }}
          </button>
          <button
            type="button"
            class="shrink-0 text-slate-300 transition-colors hover:text-rose-500"
            :aria-label="t('fileCenter.deletePackage')"
            @click="handleDeletePackage"
          >
            <Trash2
              class="h-4 w-4"
              :stroke-width="2"
            />
          </button>
        </div>
        <input
          v-else
          v-model="nameDraft"
          type="text"
          class="w-full rounded-lg border border-blue-300 bg-white px-2 py-1.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-100"
          @blur="commitName"
          @keyup.enter="commitName"
        />

        <div class="mt-2 flex items-center gap-2 text-[11px]">
          <span
            class="inline-block h-1.5 w-1.5 rounded-full"
            :class="ragActive ? 'bg-emerald-500' : 'bg-slate-300'"
          />
          <span class="text-slate-500">
            {{
              t('fileCenter.corpusStatus', { completed: completedCount, total: documents.length })
            }}
          </span>
          <Loader2
            v-if="isIndexing"
            class="h-3 w-3 animate-spin text-blue-500"
            :stroke-width="2"
          />
        </div>
      </div>

      <!-- Source list -->
      <div class="flex min-h-0 flex-col gap-1.5 px-3 py-3">
        <p
          v-if="documents.length === 0"
          class="px-1 py-2 text-xs text-slate-400"
        >
          {{ t('fileCenter.noSources') }}
        </p>
        <div
          v-for="doc in documents"
          :key="doc.id"
          class="group flex items-center gap-2 rounded-lg border border-slate-100 px-2.5 py-2 hover:border-slate-200"
        >
          <component
            :is="doc.file_type && doc.file_type.includes('markdown') ? Globe : FileText"
            class="h-4 w-4 shrink-0 text-slate-400"
            :stroke-width="2"
          />
          <div class="min-w-0 flex-1">
            <p class="truncate text-xs font-medium text-slate-700">
              {{ doc.file_name }}
            </p>
            <p class="flex items-center gap-1.5">
              <span
                class="text-[10px]"
                :class="{
                  'text-emerald-600': doc.status === 'completed',
                  'text-rose-500': doc.status === 'failed',
                  'text-blue-500': doc.status !== 'completed' && doc.status !== 'failed',
                }"
              >
                {{ statusLabel(doc.status) }}
              </span>
              <span
                v-if="chunkingLabel(doc)"
                class="rounded bg-slate-100 px-1 py-px text-[9px] font-medium uppercase tracking-wide text-slate-400"
                :title="t('fileCenter.chunkingTooltip')"
              >
                {{ chunkingLabel(doc) }}
              </span>
            </p>
          </div>
          <button
            type="button"
            class="shrink-0 text-slate-300 opacity-0 transition-opacity hover:text-rose-500 group-hover:opacity-100"
            :aria-label="t('common.delete')"
            @click="handleDeleteSource(doc.id)"
          >
            <Trash2
              class="h-3.5 w-3.5"
              :stroke-width="2"
            />
          </button>
        </div>
      </div>

      <!-- Add source -->
      <div class="mt-auto border-t border-slate-100 px-3 py-3">
        <div class="file-center-tab-strip mb-3">
          <button
            type="button"
            class="file-center-tab"
            :class="{ 'file-center-tab--active': activeTab === 'file' }"
            @click="activeTab = 'file'"
          >
            {{ t('fileCenter.tabFile') }}
          </button>
          <button
            type="button"
            class="file-center-tab"
            :class="{ 'file-center-tab--active': activeTab === 'paste' }"
            @click="activeTab = 'paste'"
          >
            {{ t('fileCenter.tabPaste') }}
          </button>
          <button
            type="button"
            class="file-center-tab"
            :class="{ 'file-center-tab--active': activeTab === 'web' }"
            @click="activeTab = 'web'"
          >
            {{ t('fileCenter.tabWeb') }}
          </button>
        </div>

        <div v-if="activeTab === 'file'">
          <button
            type="button"
            class="file-center-upload-box"
            :disabled="collabActive || uploadFile.isPending.value"
            @click="openFilePicker"
          >
            <Upload
              class="mb-1.5 h-5 w-5 text-slate-400"
              :stroke-width="1.75"
            />
            <span class="text-xs font-medium text-slate-600">
              {{ t('fileCenter.uploadHint') }}
            </span>
          </button>
          <input
            ref="fileInputRef"
            type="file"
            class="hidden"
            accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.png,.jpg,.jpeg,.mp3,.wav,.m4a,.aac,.flac,.ogg,.opus,.amr,.wma"
            @change="handleFileChange"
          />
        </div>

        <div
          v-else-if="activeTab === 'paste'"
          class="flex flex-col gap-2"
        >
          <input
            v-model="pasteTitle"
            type="text"
            class="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
            :placeholder="t('fileCenter.pasteTitlePlaceholder')"
          />
          <textarea
            v-model="pastedText"
            class="w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs leading-relaxed text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
            :placeholder="t('fileCenter.pastePlaceholder')"
            rows="4"
          />
          <button
            type="button"
            class="file-center-primary-btn"
            :disabled="!pastedText.trim() || ingestText.isPending.value"
            @click="handleAddPaste"
          >
            <Plus
              class="h-4 w-4"
              :stroke-width="2"
            />
            {{ t('fileCenter.addSource') }}
          </button>
        </div>

        <div
          v-else
          class="flex flex-col gap-2"
        >
          <div class="relative">
            <Link2
              class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              :stroke-width="2"
            />
            <input
              v-model="webUrl"
              type="url"
              class="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
              :placeholder="t('fileCenter.webUrlPlaceholder')"
            />
          </div>
          <textarea
            v-model="webPageContent"
            rows="4"
            class="w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
            :placeholder="t('fileCenter.webContentPlaceholder')"
          />
          <button
            type="button"
            class="file-center-primary-btn"
            :disabled="!webUrl.trim() || !webPageContent.trim() || ingestWeb.isPending.value"
            @click="handleAddWeb"
          >
            <Plus
              class="h-4 w-4"
              :stroke-width="2"
            />
            {{ t('fileCenter.addSource') }}
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.file-center-panel {
  max-height: calc(100% - 1.5rem);
}

.file-center-tab-strip {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
  background: rgb(241 245 249);
}

.file-center-tab {
  flex: 1;
  min-width: 0;
  padding: 6px 6px;
  border: none;
  border-radius: 9px;
  background: transparent;
  font-size: 12px;
  font-weight: 500;
  color: rgb(100 116 139);
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.file-center-tab--active {
  background: white;
  color: rgb(30 41 59);
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.08);
}

.file-center-upload-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 90px;
  padding: 14px;
  border: 1.5px dashed rgb(203 213 225);
  border-radius: 12px;
  background: rgb(248 250 252);
  text-align: center;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.file-center-upload-box:hover:not(:disabled) {
  border-color: rgb(147 197 253);
  background: rgb(239 246 255);
}

.file-center-upload-box:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.file-center-primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 9px 16px;
  border: none;
  border-radius: 11px;
  background: linear-gradient(135deg, rgb(124 58 237) 0%, rgb(79 70 229) 100%);
  font-size: 13px;
  font-weight: 500;
  color: white;
  box-shadow: 0 2px 8px rgb(124 58 237 / 0.24);
  cursor: pointer;
  transition:
    opacity 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}

.file-center-primary-btn:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgb(124 58 237 / 0.32);
  transform: translateY(-1px);
}

.file-center-primary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}
</style>
