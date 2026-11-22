<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

import ClipTeachingChapterRail from '@/components/clipTeaching/ClipTeachingChapterRail.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { playClipLesson } from '@/utils/clipTeachingApi'
import { type TimelineChapter, clampPlayhead, playbackBounds } from '@/utils/clipTeachingTimeline'

interface Playable {
  dispose: () => void
  on: (event: string, handler: () => void) => void
  currentTime: (seconds?: number) => number
  duration: () => number
  pause: () => void
  play: () => Promise<void> | void
}

const props = defineProps<{
  lessonId: string
  trimStartMs: number
  trimEndMs: number | null
  chapters: TimelineChapter[]
}>()

const emit = defineEmits<{
  time: [ms: number]
}>()

const { isZh } = useLanguage()
const notify = useNotifications()
const playerId = `mg-clip-${useId().replace(/:/g, '')}`
const slot = ref(0)
const localUrl = ref('')
const localVideo = ref<HTMLVideoElement | null>(null)
const currentMs = ref(0)
const durationMs = ref(0)
let player: Playable | null = null
let generation = 0

const bounds = computed(() => playbackBounds(props.trimStartMs, props.trimEndMs, durationMs.value))
const ready = computed(() => durationMs.value > props.trimStartMs)

function resolvedEnd(): number {
  return bounds.value.endMs
}

function readSeconds(): number | null {
  if (localVideo.value) return localVideo.value.currentTime
  if (player) return player.currentTime()
  return null
}

function writeSeconds(seconds: number): void {
  if (localVideo.value) {
    localVideo.value.currentTime = seconds
    return
  }
  player?.currentTime(seconds)
}

function pauseMedia(): void {
  if (localVideo.value) {
    localVideo.value.pause()
    return
  }
  player?.pause()
}

function playMedia(): void {
  if (localVideo.value) {
    void localVideo.value.play()
    return
  }
  void player?.play()
}

function onTime(): void {
  const seconds = readSeconds()
  if (seconds == null || !Number.isFinite(seconds)) return
  const current = Math.round(seconds * 1000)
  currentMs.value = current
  emit('time', current)
  const decision = clampPlayhead(current, props.trimStartMs, resolvedEnd(), ready.value)
  if (decision.seekMs != null) {
    writeSeconds(decision.seekMs / 1000)
    return
  }
  if (decision.pause) {
    pauseMedia()
  }
}

function onPlay(): void {
  if (!ready.value) return
  const seconds = readSeconds()
  if (seconds == null) return
  if (seconds * 1000 >= resolvedEnd() - 80) {
    writeSeconds(props.trimStartMs / 1000)
  }
}

function onMeta(): void {
  const duration = localVideo.value ? localVideo.value.duration : player?.duration()
  if (duration == null) return
  durationMs.value = Number.isFinite(duration) ? Math.round(duration * 1000) : 0
  const seconds = readSeconds()
  if (ready.value && seconds != null && seconds * 1000 < props.trimStartMs) {
    writeSeconds(props.trimStartMs / 1000)
  }
}

function seek(ms: number): void {
  writeSeconds(ms / 1000)
  playMedia()
}

async function destroyPlayer(): Promise<void> {
  if (player) {
    player.dispose()
    player = null
  }
  localUrl.value = ''
  slot.value = 0
  await nextTick()
}

async function loadPlayer(): Promise<void> {
  const gen = ++generation
  await destroyPlayer()
  if (gen !== generation) return
  try {
    const token = await playClipLesson(props.lessonId)
    if (gen !== generation) return
    if (token.mode === 'local') {
      localUrl.value = token.url
      return
    }
    slot.value = gen
    await nextTick()
    const loaded = await import('tcplayer.js')
    await import('tcplayer.js/dist/tcplayer.min.css')
    if (gen !== generation) return
    const factory = loaded.default as unknown as (
      id: string,
      options: Record<string, unknown>
    ) => Playable
    player = factory(playerId, {
      fileID: token.fileId,
      appID: token.appId,
      psign: token.psign,
      licenseUrl: token.licenseUrl,
      licenseKey: token.licenseKey,
      language: isZh.value ? 'zh-CN' : 'en',
      autoplay: false,
      width: '100%',
      height: '100%',
      controlBar: { progressControl: false },
    })
    player.on('loadedmetadata', onMeta)
    player.on('timeupdate', onTime)
    player.on('play', onPlay)
  } catch {
    if (gen === generation) notify.errorKey('clipTeaching.playFailed')
  }
}

watch(
  () => props.lessonId,
  () => {
    currentMs.value = 0
    durationMs.value = 0
    void loadPlayer()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  generation += 1
  void destroyPlayer()
})

defineExpose({ currentMs })
</script>

<template>
  <div class="clip-player">
    <video
      v-if="localUrl"
      ref="localVideo"
      class="clip-player-stage"
      :src="localUrl"
      controls
      playsinline
      @loadedmetadata="onMeta"
      @timeupdate="onTime"
      @play="onPlay"
    />
    <video
      v-else-if="slot"
      :id="playerId"
      :key="slot"
      class="clip-player-stage"
      preload="auto"
      playsinline
    />
    <div
      v-else
      class="clip-player-stage"
    />
    <div class="clip-player-rail">
      <p
        v-if="chapters.length"
        class="clip-player-chapter"
      >
        <I18nText k="clipTeaching.chapterHint" />
      </p>
      <ClipTeachingChapterRail
        :chapters="chapters"
        :start-ms="bounds.startMs"
        :end-ms="bounds.endMs"
        :current-ms="currentMs"
        @seek="seek"
      />
    </div>
  </div>
</template>

<style scoped>
.clip-player {
  position: relative;
  background: #0c0a09;
  border-radius: 12px;
  overflow: hidden;
  min-height: 280px;
  aspect-ratio: 16 / 9;
}

.clip-player-stage {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #0c0a09;
}

.clip-player-rail {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 46px;
  z-index: 3;
}

.clip-player-chapter {
  margin: 0 0 4px;
  color: #fff;
  font-size: 12px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.6);
}

.clip-player :deep(.vjs-progress-control) {
  display: none;
}
</style>
