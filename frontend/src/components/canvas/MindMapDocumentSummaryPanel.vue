<script setup lang="ts">
/**
 * Mind map document summary panel — document extract, image upload, web link tabs.
 */
import { computed, ref } from 'vue'

import { ImageUp, Link2, Sparkles, Upload, X } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { useMindMapDocumentSummary } from '@/composables/mindMap/useMindMapDocumentSummary'
import { useDiagramStore } from '@/stores'

type SummaryTab = 'document' | 'image' | 'web'

const ALLOWED_IMAGE_MIME = new Set(['image/jpeg', 'image/png', 'image/jpg'])

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const {
  isGenerating,
  generateFromDocumentContent,
  generateFromDocumentFile,
  generateFromWebUrl,
  generateFromImageFile,
  validateDocumentFile,
} = useMindMapDocumentSummary()

const activeTab = ref<SummaryTab>('document')
const pastedText = ref('')
const uploadedDocName = ref('')
const uploadedDocFile = ref<File | null>(null)
const webUrl = ref('')
const imageFile = ref<File | null>(null)
const imagePreviewUrl = ref<string | null>(null)

const docInputRef = ref<HTMLInputElement | null>(null)
const imageInputRef = ref<HTMLInputElement | null>(null)

const tabs: Array<{ id: SummaryTab; labelKey: string }> = [
  { id: 'document', labelKey: 'canvas.mindMapDocumentSummary.tabDocument' },
  { id: 'image', labelKey: 'canvas.mindMapDocumentSummary.tabImage' },
  { id: 'web', labelKey: 'canvas.mindMapDocumentSummary.tabWeb' },
]

const canGenerate = computed(() => {
  if (isGenerating.value || diagramStore.collabSessionActive) return false
  if (activeTab.value === 'document') {
    return pastedText.value.trim().length > 0 || uploadedDocFile.value !== null
  }
  if (activeTab.value === 'image') {
    return imageFile.value !== null
  }
  return webUrl.value.trim().length > 0
})

function handleClose(): void {
  emit('close')
}

function switchTab(tab: SummaryTab): void {
  activeTab.value = tab
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

async function handleGenerate(): Promise<void> {
  if (diagramStore.collabSessionActive) return

  if (activeTab.value === 'document') {
    if (uploadedDocFile.value) {
      await generateFromDocumentFile(uploadedDocFile.value)
      return
    }
    await generateFromDocumentContent(pastedText.value, {
      pageTitle: uploadedDocName.value || undefined,
    })
    return
  }

  if (activeTab.value === 'image' && imageFile.value) {
    await generateFromImageFile(imageFile.value)
    return
  }

  if (activeTab.value === 'web') {
    await generateFromWebUrl(webUrl.value)
  }
}
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
      <!-- Document extract -->
      <div
        v-if="activeTab === 'document'"
        class="flex flex-col gap-3"
      >
        <div>
          <p class="mb-2 text-xs font-semibold text-slate-700">
            {{ t('canvas.mindMapDocumentSummary.localDocumentLabel') }}
          </p>
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
            <span class="mt-1 text-[11px] leading-snug text-slate-400">
              {{ t('canvas.mindMapDocumentSummary.uploadDocSubhint') }}
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
        </div>

        <div>
          <p class="mb-2 text-xs font-semibold text-slate-700">
            {{ t('canvas.mindMapDocumentSummary.pasteLabel') }}
          </p>
          <textarea
            v-model="pastedText"
            class="doc-summary-textarea w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm leading-relaxed text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
            :placeholder="t('canvas.mindMapDocumentSummary.pastePlaceholder')"
            rows="6"
          />
        </div>
      </div>

      <!-- Image upload -->
      <div
        v-else-if="activeTab === 'image'"
        class="flex flex-col gap-3"
      >
        <p class="text-xs font-semibold text-slate-700">
          {{ t('canvas.mindMapDocumentSummary.imageUploadLabel') }}
        </p>
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
          <span class="mt-1 text-[11px] leading-snug text-slate-400">
            {{ t('canvas.mindMapDocumentSummary.uploadImageSubhint') }}
          </span>
        </button>
        <div
          v-else
          class="relative overflow-hidden rounded-xl border border-slate-200 bg-slate-50"
        >
          <img
            :src="imagePreviewUrl"
            alt=""
            class="max-h-40 w-full object-contain"
          />
          <button
            type="button"
            class="absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/90 text-slate-500 shadow-sm hover:text-slate-700"
            :aria-label="t('canvas.mindMapDocumentSummary.removeImage')"
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
        <p class="text-[11px] leading-relaxed text-slate-400">
          {{ t('canvas.mindMapDocumentSummary.imageOcrHint') }}
        </p>
      </div>

      <!-- Web link -->
      <div
        v-else
        class="flex flex-col gap-3"
      >
        <p class="text-xs font-semibold text-slate-700">
          {{ t('canvas.mindMapDocumentSummary.webLinkLabel') }}
        </p>
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

      <button
        type="button"
        class="one-sentence-generate-btn mt-3 w-full shrink-0"
        :disabled="!canGenerate"
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
  border-radius: 12px;
  background: rgb(241 245 249);
}

.doc-summary-tab {
  flex: 1;
  min-width: 0;
  padding: 7px 6px;
  border: none;
  border-radius: 9px;
  background: transparent;
  font-size: 12px;
  font-weight: 500;
  color: rgb(100 116 139);
  cursor: pointer;
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
  min-height: 120px;
  padding: 16px;
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
  min-height: 120px;
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
