<script setup lang="ts">
/**
 * Seminar chat file row: type badge, size, and time.
 * Documents open in the right-hand preview. Images open larger.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { Download } from '@lucide/vue'

import ImagePreviewModal from '@/components/common/ImagePreviewModal.vue'
import MindmateSeminarShelfMenu from '@/components/mindmate/MindmateSeminarShelfMenu.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  openSeminarDoc,
  seminarFileDocId,
  seminarSpectator,
} from '@/composables/mindmate/mindmateSeminarChrome'
import { formatCollabMessageStamp } from '@/utils/mindmateCollabRead'
import {
  type SeminarBackgroundFile,
  downloadSeminarBackgroundFile,
  fetchSeminarBackgroundBlob,
  fetchSeminarBackgroundFile,
  formatSeminarFileSize,
  seminarFilePreviewMode,
  shelveSeminarItem,
} from '@/utils/mindmateSeminarFolder'

const props = defineProps<{
  sessionId: string
  fileId: string
  filename: string
  sentAt?: string
}>()

const { t } = useLanguage()
const notify = useNotifications()

const meta = ref<SeminarBackgroundFile | null>(null)
const thumbUrl = ref('')
const enlarged = ref(false)
const downloading = ref(false)
const shelving = ref(false)

const previewKind = computed(() =>
  seminarFilePreviewMode(meta.value?.contentType || '', props.filename)
)
const isImage = computed(() => previewKind.value === 'image')

const badge = computed(() => fileBadge(props.filename))

const metaLine = computed(() => {
  const parts: string[] = []
  if (meta.value && meta.value.sizeBytes > 0) {
    parts.push(formatSeminarFileSize(meta.value.sizeBytes))
  }
  const time = formatCollabMessageStamp(props.sentAt)
  if (time) {
    parts.push(time)
  }
  return parts.join(' · ')
})

const imageCaption = computed(() => {
  const name = props.filename.trim()
  const size =
    meta.value && meta.value.sizeBytes > 0 ? formatSeminarFileSize(meta.value.sizeBytes) : ''
  return [name, size].filter(Boolean).join(' · ')
})

watch(
  () => [props.sessionId, props.fileId] as const,
  () => {
    void loadMeta()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  revokeThumb()
})

function fileBadge(filename: string): { label: string; color: string } {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  if (ext === 'pdf') {
    return { label: 'PDF', color: '#e11d48' }
  }
  if (ext === 'doc' || ext === 'docx') {
    return { label: 'DOC', color: '#3b82f6' }
  }
  if (ext === 'xls' || ext === 'xlsx') {
    return { label: 'XLS', color: '#16a34a' }
  }
  if (ext === 'ppt' || ext === 'pptx') {
    return { label: 'PPT', color: '#ea580c' }
  }
  if (ext === 'zip') {
    return { label: 'ZIP', color: '#a16207' }
  }
  if (ext === 'png' || ext === 'jpg' || ext === 'jpeg' || ext === 'webp' || ext === 'gif') {
    return { label: 'IMG', color: '#64748b' }
  }
  return { label: 'DOC', color: '#94a3b8' }
}

function revokeThumb(): void {
  if (thumbUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(thumbUrl.value)
  }
  thumbUrl.value = ''
}

async function loadMeta(): Promise<void> {
  meta.value = await fetchSeminarBackgroundFile(props.sessionId, props.fileId)
  if (isImage.value) {
    void loadThumb()
  }
}

async function loadThumb(): Promise<void> {
  if (!props.sessionId || !props.fileId || thumbUrl.value) {
    return
  }
  try {
    const blob = await fetchSeminarBackgroundBlob(props.sessionId, props.fileId)
    revokeThumb()
    thumbUrl.value = URL.createObjectURL(blob)
  } catch {
    thumbUrl.value = ''
  }
}

function openDocument(): void {
  openSeminarDoc({
    id: seminarFileDocId(props.fileId),
    kind: 'file',
    title: props.filename,
    fileId: props.fileId,
    contentType: meta.value?.contentType || '',
    filename: props.filename,
  })
}

function enlargeImage(): void {
  if (!thumbUrl.value) {
    void loadThumb().then(() => {
      if (thumbUrl.value) {
        enlarged.value = true
      }
    })
    return
  }
  enlarged.value = true
}

async function downloadFile(): Promise<void> {
  if (downloading.value || !props.sessionId) {
    return
  }
  downloading.value = true
  try {
    await downloadSeminarBackgroundFile(props.sessionId, {
      id: props.fileId,
      filename: props.filename,
      contentType: meta.value?.contentType || 'application/octet-stream',
      sizeBytes: meta.value?.sizeBytes || 0,
      uploaderName: meta.value?.uploaderName || '',
      pinned: false,
      pinnedAt: null,
      createdAt: meta.value?.createdAt || '',
      sourceMessageId: meta.value?.sourceMessageId ?? null,
      listed: meta.value?.listed ?? false,
      artifact: meta.value?.artifact ?? false,
      diagramId: meta.value?.diagramId ?? null,
    })
  } catch {
    notify.errorKey('mindmate.folder.loadFailed')
  } finally {
    downloading.value = false
  }
}

async function shelveFile(destination: 'resource' | 'artifact'): Promise<void> {
  if (shelving.value || !props.sessionId) {
    return
  }
  shelving.value = true
  try {
    meta.value = await shelveSeminarItem(props.sessionId, {
      kind: 'file',
      destination,
      fileId: props.fileId,
    })
    notify.successKey(
      destination === 'resource' ? 'mindmate.shelf.savedResource' : 'mindmate.shelf.savedArtifact'
    )
  } catch {
    notify.errorKey('mindmate.shelf.failed')
  } finally {
    shelving.value = false
  }
}
</script>

<template>
  <div
    v-if="isImage"
    class="mm-file-shot"
  >
    <button
      type="button"
      class="mm-file-shot__frame"
      @click.stop="enlargeImage"
    >
      <img
        v-if="thumbUrl"
        :src="thumbUrl"
        alt=""
      />
      <span
        v-else
        class="mm-file-shot__placeholder"
      >
        {{ filename }}
      </span>
    </button>
    <div class="mm-file-shot__foot">
      <span class="mm-file-shot__caption">{{ imageCaption }}</span>
      <button
        type="button"
        class="mm-file-shot__enlarge"
        @click.stop="enlargeImage"
      >
        {{ t('mindmate.fileCard.viewLarge') }}
      </button>
    </div>
    <ImagePreviewModal
      v-model:visible="enlarged"
      :title="filename"
      :image-url="thumbUrl"
    />
  </div>
  <div
    v-else
    class="mm-file-card"
  >
    <button
      type="button"
      class="mm-file-card__main"
      @click.stop="openDocument"
    >
      <span
        class="mm-file-card__badge"
        :style="{ background: badge.color }"
      >
        {{ badge.label }}
      </span>
      <span class="mm-file-card__text">
        <span class="mm-file-card__name">{{ filename }}</span>
        <span
          v-if="metaLine"
          class="mm-file-card__meta"
        >
          {{ metaLine }}
        </span>
      </span>
    </button>
    <MindmateSeminarShelfMenu
      v-if="!seminarSpectator"
      :busy="shelving"
      @pick="shelveFile"
    />
    <button
      v-if="!seminarSpectator"
      type="button"
      class="mm-file-card__download"
      :aria-label="t('mindmate.docViewer.download')"
      :disabled="downloading"
      @click.stop="downloadFile"
    >
      <Download
        :size="16"
        aria-hidden="true"
      />
    </button>
  </div>
</template>

<style scoped>
.mm-file-card {
  display: flex;
  align-items: center;
  gap: 8px;
  width: max-content;
  max-width: min(22rem, 100%);
  padding: 8px 8px 8px 10px;
  border: 1px solid #efeae4;
  border-radius: 12px;
  background: #fff;
}

.mm-file-card__main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.mm-file-card__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.mm-file-card__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.mm-file-card__name {
  overflow: hidden;
  max-width: 15rem;
  color: #1c1917;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-file-card__meta {
  color: #a8a29e;
  font-size: 12px;
  line-height: 1.3;
}

.mm-file-card__download {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 999px;
  background: #f5f3ff;
  color: #7c3aed;
  cursor: pointer;
}

.mm-file-card__download:disabled {
  opacity: 0.6;
  cursor: default;
}

.mm-file-shot {
  width: 100%;
  min-width: 240px;
}

.mm-file-shot__frame {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 148px;
  padding: 0;
  overflow: hidden;
  border: none;
  border-radius: 12px;
  background: #e7e5e4;
  cursor: zoom-in;
}

.mm-file-shot__frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mm-file-shot__placeholder {
  padding: 0 16px;
  color: #a8a29e;
  font-size: 14px;
  text-align: center;
}

.mm-file-shot__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
}

.mm-file-shot__caption {
  min-width: 0;
  overflow: hidden;
  color: #78716c;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-file-shot__enlarge {
  flex-shrink: 0;
  padding: 0;
  border: none;
  background: transparent;
  color: #7c3aed;
  font-size: 12px;
  cursor: pointer;
}
</style>
