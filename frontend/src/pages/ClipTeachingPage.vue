<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ClipTeachingComments from '@/components/clipTeaching/ClipTeachingComments.vue'
import ClipTeachingPlayer from '@/components/clipTeaching/ClipTeachingPlayer.vue'
import ClipTeachingSlideStrip from '@/components/clipTeaching/ClipTeachingSlideStrip.vue'
import ClipTeachingTrimBar from '@/components/clipTeaching/ClipTeachingTrimBar.vue'
import { uploadVodFile } from '@/composables/admin/uploadVodFile'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  addClipComment,
  deleteClipComment,
  fetchClipLesson,
  listClipComments,
  registerClipMedia,
  renameClipLesson,
  saveClipChapters,
  saveClipTrim,
  signClipUpload,
  uploadClipDeck,
  uploadClipVideo,
} from '@/utils/clipTeachingApi'
import type { ClipComment, ClipLessonDetail } from '@/utils/clipTeachingApi'
import type { TimelineChapter } from '@/utils/clipTeachingTimeline'

const route = useRoute()
const router = useRouter()
const { t } = useLanguage()
const notify = useNotifications()
const lesson = ref<ClipLessonDetail | null>(null)
const comments = ref<ClipComment[]>([])
const busy = ref(false)
const uploadPercent = ref(0)
const currentMs = ref(0)
let pollTimer: ReturnType<typeof setInterval> | null = null

const lessonId = computed(() => String(route.params.id || ''))
const chapters = computed<TimelineChapter[]>(() =>
  (lesson.value?.chapters ?? []).map((chapter) => ({
    id: chapter.id,
    title: chapter.title,
    startMs: chapter.start_ms,
  }))
)

function stopPoll(): void {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPoll(): void {
  stopPoll()
  if (lesson.value?.preview_status !== 'pending') return
  pollTimer = setInterval(() => {
    void refresh(false)
  }, 2000)
}

async function refresh(showError: boolean): Promise<void> {
  try {
    lesson.value = await fetchClipLesson(lessonId.value)
    comments.value = await listClipComments(lessonId.value)
    startPoll()
  } catch (error) {
    if (showError) {
      notify.error(error instanceof Error ? error.message : t('clipTeaching.loadFailed'))
    }
  }
}

async function run(task: () => Promise<void>): Promise<void> {
  busy.value = true
  try {
    await task()
  } catch (error) {
    const code = error instanceof Error ? error.message : ''
    const key =
      code === 'trim_invalid'
        ? 'clipTeaching.trimInvalid'
        : code === 'chapter_invalid'
          ? 'clipTeaching.chapterInvalid'
          : code === 'deck_invalid' || code === 'deck_too_large'
            ? 'clipTeaching.deckInvalid'
            : 'clipTeaching.saveFailed'
    notify.errorKey(key)
  } finally {
    busy.value = false
  }
}

async function onTitle(event: Event): Promise<void> {
  const input = event.target
  if (!(input instanceof HTMLInputElement) || !lesson.value?.is_owner) return
  const title = input.value.trim()
  if (!title || title === lesson.value.title) return
  await run(async () => {
    lesson.value = await renameClipLesson(lessonId.value, title)
  })
}

async function onVideo(event: Event): Promise<void> {
  const input = event.target
  if (!(input instanceof HTMLInputElement) || !input.files?.[0] || !lesson.value) return
  const file = input.files[0]
  input.value = ''
  uploadPercent.value = 0
  try {
    await run(async () => {
      if (lesson.value?.video_storage === 'local') {
        lesson.value = await uploadClipVideo(lessonId.value, file)
        return
      }
      await uploadVodFile({
        file,
        title: lesson.value?.title || file.name,
        onProgress: (progress) => {
          uploadPercent.value = Math.round(progress.percent * 100)
        },
        signUpload: () => signClipUpload(lessonId.value),
        registerMedia: async (payload) => {
          const updated = await registerClipMedia(lessonId.value, payload)
          lesson.value = updated
          return { id: updated.vod_media_id || updated.id }
        },
      })
    })
  } finally {
    uploadPercent.value = 0
  }
}

async function saveTrim(startMs: number, endMs: number | null): Promise<void> {
  await run(async () => {
    lesson.value = await saveClipTrim(lessonId.value, startMs, endMs)
  })
}

async function writeChapters(next: Array<{ title: string; start_ms: number }>): Promise<void> {
  await run(async () => {
    lesson.value = await saveClipChapters(lessonId.value, next)
  })
}

function onSetStart(): void {
  if (!lesson.value) return
  void saveTrim(currentMs.value, lesson.value.trim_end_ms)
}

function onSetEnd(): void {
  if (!lesson.value) return
  void saveTrim(lesson.value.trim_start_ms, currentMs.value)
}

function onClearEnd(): void {
  if (!lesson.value) return
  void saveTrim(lesson.value.trim_start_ms, null)
}

function onAddChapter(title: string): void {
  if (!lesson.value) return
  const next = lesson.value.chapters.map((chapter) => ({
    title: chapter.title,
    start_ms: chapter.start_ms,
  }))
  next.push({ title, start_ms: currentMs.value })
  void writeChapters(next)
}

function onRenameChapter(payload: { id: string; title: string }): void {
  if (!lesson.value) return
  void writeChapters(
    lesson.value.chapters.map((chapter) => ({
      title: chapter.id === payload.id ? payload.title : chapter.title,
      start_ms: chapter.start_ms,
    }))
  )
}

function onDeleteChapter(id: string): void {
  if (!lesson.value) return
  void writeChapters(
    lesson.value.chapters
      .filter((chapter) => chapter.id !== id)
      .map((chapter) => ({ title: chapter.title, start_ms: chapter.start_ms }))
  )
}

async function onDeck(file: File): Promise<void> {
  await run(async () => {
    lesson.value = await uploadClipDeck(lessonId.value, file)
    startPoll()
  })
}

async function onComment(payload: { body: string; parentId: number | null }): Promise<void> {
  await run(async () => {
    comments.value = await addClipComment(lessonId.value, payload.body, payload.parentId)
  })
}

async function onRemoveComment(id: number): Promise<void> {
  await run(async () => {
    comments.value = await deleteClipComment(lessonId.value, id)
  })
}

watch(
  lessonId,
  () => {
    void refresh(true)
  },
  { immediate: true }
)

onBeforeUnmount(stopPoll)
</script>

<template>
  <div class="clip-page">
    <header class="clip-page-head">
      <button
        type="button"
        @click="router.push('/clip-teaching')"
      >
        <I18nText k="clipTeaching.back" />
      </button>
      <input
        v-if="lesson"
        :value="lesson.title"
        :readonly="!lesson.is_owner"
        maxlength="200"
        @change="onTitle"
      />
    </header>
    <div
      v-if="lesson"
      class="clip-page-grid"
    >
      <div class="clip-page-main">
        <label
          v-if="!lesson.has_video && lesson.is_owner"
          class="clip-upload"
        >
          <I18nText k="clipTeaching.uploadVideo" />
          <input
            type="file"
            accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
            :disabled="busy"
            @change="onVideo"
          />
          <span v-if="uploadPercent">{{ uploadPercent }}%</span>
        </label>
        <template v-else-if="lesson.has_video">
          <ClipTeachingPlayer
            :lesson-id="lesson.id"
            :trim-start-ms="lesson.trim_start_ms"
            :trim-end-ms="lesson.trim_end_ms"
            :chapters="chapters"
            @time="currentMs = $event"
          />
          <div
            v-if="lesson.is_owner"
            class="clip-owner"
          >
            <label class="clip-replace">
              <I18nText k="clipTeaching.replaceVideo" />
              <input
                type="file"
                accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
                :disabled="busy"
                @change="onVideo"
              />
            </label>
            <span v-if="uploadPercent">{{ uploadPercent }}%</span>
            <ClipTeachingTrimBar
              :trim-start-ms="lesson.trim_start_ms"
              :trim-end-ms="lesson.trim_end_ms"
              :chapters="chapters"
              :current-ms="currentMs"
              :busy="busy"
              @set-start="onSetStart"
              @set-end="onSetEnd"
              @clear-end="onClearEnd"
              @add-chapter="onAddChapter"
              @rename-chapter="onRenameChapter"
              @delete-chapter="onDeleteChapter"
            />
          </div>
        </template>
        <p
          v-else
          class="clip-wait"
        >
          <I18nText k="clipTeaching.noVideo" />
        </p>
        <ClipTeachingComments
          :comments="comments"
          :busy="busy"
          @send="onComment"
          @remove="onRemoveComment"
        />
      </div>
      <ClipTeachingSlideStrip
        :lesson-id="lesson.id"
        :status="lesson.preview_status"
        :can-edit="lesson.is_owner"
        :busy="busy"
        @upload="onDeck"
      />
    </div>
  </div>
</template>

<style scoped>
.clip-page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #fafaf9;
}

.clip-page-head {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e7e5e4;
}

.clip-page-head input {
  flex: 1;
  border: 0;
  background: transparent;
  font-size: 18px;
  font-weight: 600;
}

.clip-page-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 12px;
  padding: 12px;
}

.clip-page-main {
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.clip-upload,
.clip-replace {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.clip-upload {
  min-height: 280px;
  border: 1px dashed #d6d3d1;
  border-radius: 12px;
  align-items: center;
  justify-content: center;
  background: #fff;
}

.clip-upload input,
.clip-replace input {
  display: none;
}

.clip-owner {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #fff;
  border: 1px solid #e7e5e4;
  border-radius: 12px;
  padding: 12px;
}

.clip-wait {
  color: #78716c;
}

.clip-page-head button {
  border: 1px solid #d6d3d1;
  border-radius: 8px;
  background: #fff;
  padding: 6px 10px;
  cursor: pointer;
}

@media (max-width: 900px) {
  .clip-page-grid {
    grid-template-columns: 1fr;
  }
}
</style>
