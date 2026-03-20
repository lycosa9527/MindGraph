<script setup lang="ts">
/**
 * FilePreview - Inline display of file attachments on a message.
 *
 * Images render as clickable thumbnails; other files render as
 * compact cards with an icon, name, size, and download link.
 */
import { computed, ref } from 'vue'

import { Download } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables/useLanguage'
import type { FileAttachment } from '@/stores/workshopChat'

import ImageLightbox from './ImageLightbox.vue'

const { t } = useLanguage()

const props = defineProps<{
  attachments: FileAttachment[]
}>()

const lightboxSrc = ref<string | null>(null)
const lightboxName = ref('')

const imageAttachments = computed(() =>
  props.attachments.filter((a) => a.content_type.startsWith('image/'))
)

const fileAttachments = computed(() =>
  props.attachments.filter((a) => !a.content_type.startsWith('image/'))
)

function openLightbox(att: FileAttachment): void {
  lightboxSrc.value = att.file_path
  lightboxName.value = att.filename
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fileIcon(contentType: string): string {
  if (contentType.includes('pdf')) return '📄'
  if (contentType.includes('word') || contentType.includes('document')) return '📝'
  if (contentType.includes('text')) return '📃'
  return '📎'
}
</script>

<template>
  <div
    v-if="attachments.length > 0"
    class="file-preview"
  >
    <!-- Image thumbnails -->
    <div
      v-if="imageAttachments.length > 0"
      class="file-preview__images"
    >
      <button
        v-for="att in imageAttachments"
        :key="att.id"
        class="file-preview__thumb"
        @click="openLightbox(att)"
      >
        <img
          :src="att.file_path"
          :alt="att.filename"
          loading="lazy"
        />
      </button>
    </div>

    <!-- File cards -->
    <div
      v-for="att in fileAttachments"
      :key="att.id"
    >
      <div class="file-preview__card">
        <span class="file-preview__icon">{{ fileIcon(att.content_type) }}</span>
        <div class="file-preview__info">
          <div class="file-preview__name">{{ att.filename }}</div>
          <div class="file-preview__size">{{ formatSize(att.file_size) }}</div>
        </div>
        <a
          :href="att.file_path"
          :download="att.filename"
          target="_blank"
          rel="noopener noreferrer"
          class="file-preview__download"
          :title="t('workshop.download')"
          @click.stop
        >
          <el-icon :size="14"><Download /></el-icon>
        </a>
      </div>
    </div>

    <!-- Lightbox overlay -->
    <ImageLightbox
      v-if="lightboxSrc"
      :src="lightboxSrc"
      :filename="lightboxName"
      @close="lightboxSrc = null"
    />
  </div>
</template>

<style scoped>
.file-preview {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-preview__images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.file-preview__thumb {
  position: relative;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid hsl(0deg 0% 0% / 10%);
  cursor: pointer;
  background: none;
  padding: 0;
  transition:
    border-color 150ms ease,
    box-shadow 150ms ease;
}

.file-preview__thumb:hover {
  border-color: hsl(0deg 0% 0% / 20%);
  box-shadow: 0 2px 6px hsl(0deg 0% 0% / 10%);
}

.file-preview__thumb img {
  max-width: 200px;
  max-height: 150px;
  object-fit: cover;
  display: block;
}

.file-preview__card {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid hsl(0deg 0% 0% / 10%);
  background: hsl(0deg 0% 98%);
  max-width: 280px;
}

.file-preview__icon {
  font-size: 18px;
  flex-shrink: 0;
}

.file-preview__info {
  min-width: 0;
  flex: 1;
}

.file-preview__name {
  font-size: 12px;
  font-weight: 600;
  color: hsl(0deg 0% 20%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-preview__size {
  font-size: 10px;
  color: hsl(0deg 0% 52%);
  margin-top: 1px;
}

.file-preview__download {
  flex-shrink: 0;
  color: hsl(0deg 0% 48%);
  transition: color 120ms ease;
}

.file-preview__download:hover {
  color: hsl(228deg 56% 52%);
}
</style>
