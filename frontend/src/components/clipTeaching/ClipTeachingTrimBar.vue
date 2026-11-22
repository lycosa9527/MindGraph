<script setup lang="ts">
import { ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { type TimelineChapter, formatClock } from '@/utils/clipTeachingTimeline'

const props = defineProps<{
  trimStartMs: number
  trimEndMs: number | null
  chapters: TimelineChapter[]
  currentMs: number
  busy: boolean
}>()

const emit = defineEmits<{
  setStart: []
  setEnd: []
  clearEnd: []
  addChapter: [title: string]
  renameChapter: [payload: { id: string; title: string }]
  deleteChapter: [id: string]
}>()

const { t } = useLanguage()
const chapterTitle = ref('')
const renameValue = ref('')
const renamingId = ref('')

function addChapter(): void {
  const title = chapterTitle.value.trim()
  if (!title) return
  emit('addChapter', title)
  chapterTitle.value = ''
}

function beginRename(chapter: TimelineChapter): void {
  renamingId.value = chapter.id
  renameValue.value = chapter.title
}

function commitRename(id: string): void {
  const title = renameValue.value.trim()
  renamingId.value = ''
  if (!title) return
  emit('renameChapter', { id, title })
}
</script>

<template>
  <div class="clip-trim">
    <p class="clip-trim-clock">
      {{ formatClock(props.currentMs) }}
      ·
      {{ formatClock(props.trimStartMs) }}
      –
      {{ props.trimEndMs == null ? '…' : formatClock(props.trimEndMs) }}
    </p>
    <div class="clip-trim-actions">
      <button
        type="button"
        :disabled="busy"
        @click="emit('setStart')"
      >
        <I18nText k="clipTeaching.trimStart" />
      </button>
      <button
        type="button"
        :disabled="busy"
        @click="emit('setEnd')"
      >
        <I18nText k="clipTeaching.trimEnd" />
      </button>
      <button
        type="button"
        :disabled="busy || trimEndMs == null"
        @click="emit('clearEnd')"
      >
        <I18nText k="clipTeaching.clearTrimEnd" />
      </button>
    </div>
    <div class="clip-trim-actions">
      <input
        v-model="chapterTitle"
        type="text"
        maxlength="80"
        :placeholder="t('clipTeaching.chapterTitle')"
        @keydown.enter.prevent="addChapter"
      />
      <button
        type="button"
        :disabled="busy || !chapterTitle.trim()"
        @click="addChapter"
      >
        <I18nText k="clipTeaching.addChapter" />
      </button>
    </div>
    <ul class="clip-chapters">
      <li
        v-for="chapter in chapters"
        :key="chapter.id"
      >
        <span>{{ formatClock(chapter.startMs) }}</span>
        <input
          v-if="renamingId === chapter.id"
          v-model="renameValue"
          type="text"
          maxlength="80"
          @keydown.enter.prevent="commitRename(chapter.id)"
        />
        <span v-else>{{ chapter.title }}</span>
        <button
          type="button"
          @click="renamingId === chapter.id ? commitRename(chapter.id) : beginRename(chapter)"
        >
          <I18nText
            v-if="renamingId === chapter.id"
            k="clipTeaching.saveChapter"
          /><I18nText
            v-else
            k="clipTeaching.renameChapter"
          />
        </button>
        <button
          type="button"
          @click="emit('deleteChapter', chapter.id)"
        >
          <I18nText k="clipTeaching.deleteChapter" />
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.clip-trim {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.clip-trim-clock {
  margin: 0;
  color: #57534e;
  font-size: 13px;
}

.clip-trim-actions,
.clip-chapters li {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.clip-chapters {
  list-style: none;
  margin: 0;
  padding: 0;
}

.clip-trim input {
  border: 1px solid #d6d3d1;
  border-radius: 8px;
  padding: 6px 8px;
  min-width: 160px;
  background: #fff;
}

.clip-trim button {
  border: 1px solid #d6d3d1;
  border-radius: 8px;
  background: #fff;
  padding: 6px 10px;
  cursor: pointer;
}

.clip-trim button:disabled {
  cursor: default;
  opacity: 0.5;
}
</style>
