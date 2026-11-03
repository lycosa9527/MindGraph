<script setup lang="ts">
/**
 * Opened knowledge folder: path, file area, upload and delete.
 */
import { X } from '@lucide/vue'

import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import { type KnowledgeWorkTone, documentWorkTone } from '@/utils/knowledgeWorkTone'

defineProps<{
  folderName: string
  renaming: boolean
  loading: boolean
  documents: KnowledgeDocument[]
  pickedId: number | null
  uploadDisabled: boolean
  deleteDisabled: boolean
  placeholder: string
}>()

const renameDraft = defineModel<string>('renameDraft', { required: true })

const emit = defineEmits<{
  back: []
  commitRename: []
  cancelRename: []
  pick: [id: number]
  clearPick: []
  upload: []
  deletePicked: []
  bindRename: [element: unknown]
}>()

function bindRename(element: unknown): void {
  emit('bindRename', element)
}

function workTone(doc: KnowledgeDocument): KnowledgeWorkTone {
  return documentWorkTone(doc.status)
}

function fileMark(doc: KnowledgeDocument): { label: string; tone: string } {
  const name = doc.file_name.toLowerCase()
  const type = doc.file_type.toLowerCase()
  const ext = name.includes('.') ? (name.split('.').pop() ?? '') : ''
  if (ext === 'pdf' || type.includes('pdf')) return { label: 'PDF', tone: 'pdf' }
  if (ext === 'docx' || ext === 'doc' || type.includes('word')) return { label: 'DOC', tone: 'doc' }
  if (ext === 'md' || type.includes('markdown')) return { label: 'MD', tone: 'md' }
  if (ext === 'txt' || type === 'text/plain') return { label: 'TXT', tone: 'txt' }
  if (type.startsWith('image/') || ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) {
    return { label: 'IMG', tone: 'img' }
  }
  return { label: 'FILE', tone: 'file' }
}
</script>

<template>
  <div class="knowledge-settings__opened">
    <button
      type="button"
      class="knowledge-settings__crumb"
      @click="emit('back')"
    >
      <I18nText k="settings.tabs.knowledge" />
    </button>
    <span class="knowledge-settings__crumb-sep">/</span>
    <input
      v-if="renaming"
      :ref="bindRename"
      v-model="renameDraft"
      class="knowledge-settings__opened-name knowledge-settings__rename"
      type="text"
      maxlength="200"
      :placeholder="placeholder"
      @click.stop
      @keydown.enter.prevent="emit('commitRename')"
      @keydown.esc.prevent="emit('cancelRename')"
      @blur="emit('commitRename')"
    />
    <span
      v-else
      class="knowledge-settings__opened-name"
      >{{ folderName }}</span
    >
  </div>
  <div
    class="knowledge-settings__room"
    @click="emit('clearPick')"
  >
    <p
      v-if="loading"
      class="language-settings-swiss__hint"
    >
      <I18nText k="settings.knowledge.loading" />
    </p>
    <ul
      v-else
      class="knowledge-settings__icons"
    >
      <li
        v-for="doc in documents"
        :key="doc.id"
      >
        <button
          type="button"
          class="knowledge-settings__file-icon"
          :class="{
            'is-picked': doc.id === pickedId,
            'is-working': workTone(doc) === 'working',
            'is-failed': workTone(doc) === 'failed',
            'is-ready': workTone(doc) === 'ready',
          }"
          @click.stop="emit('pick', doc.id)"
        >
          <span
            class="knowledge-settings__sheet"
            :class="`is-${fileMark(doc).tone}`"
          >
            <span class="knowledge-settings__mark">{{ fileMark(doc).label }}</span>
            <span
              v-if="workTone(doc) === 'failed'"
              class="knowledge-settings__fault"
            >
              <X
                :size="11"
                :stroke-width="3"
              />
            </span>
          </span>
          <span class="knowledge-settings__name">{{ doc.file_name }}</span>
        </button>
      </li>
    </ul>
  </div>
  <div class="knowledge-settings__dock">
    <button
      type="button"
      class="knowledge-settings__dock-btn"
      :disabled="uploadDisabled"
      @click="emit('upload')"
    >
      <I18nText k="settings.knowledge.upload" />
    </button>
    <button
      type="button"
      class="knowledge-settings__dock-btn"
      :disabled="deleteDisabled"
      @click="emit('deletePicked')"
    >
      <I18nText k="settings.knowledge.delete" />
    </button>
  </div>
</template>
