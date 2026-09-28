<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { playTrainingVod } from '@/utils/trainingVodApi'
import { playVodMedia } from '@/utils/vodApi'

const DEFAULT_WIDTH = 42
const DEFAULT_HEIGHT = 36
const SPAN_MIN = 20
const SPAN_MAX = 92

const props = withDefaults(
  defineProps<{
    mediaId: string
    autoplay?: boolean
    source?: 'training' | 'admin'
    organizationId?: number | null
    width?: number | null
    height?: number | null
    stepKey?: string
    canNext?: boolean
  }>(),
  {
    autoplay: false,
    source: 'training',
    organizationId: null,
    width: null,
    height: null,
    stepKey: '',
    canNext: true,
  }
)

const emit = defineEmits<{
  resize: [size: { width: number; height: number }]
  next: []
}>()

const { t, isZh } = useLanguage()
const notify = useNotifications()
const playerId = `mg-vod-${useId().replace(/:/g, '')}`
const playerSlot = ref(0)
const loading = ref(false)
const dismissed = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const stageRef = ref<HTMLElement | null>(null)
const localWidth = ref(props.width ?? DEFAULT_WIDTH)
const localHeight = ref(props.height ?? DEFAULT_HEIGHT)
let player: { dispose: () => void } | null = null
let loadGen = 0
let dragging = false

function clampSpan(value: number): number {
  return Math.round(Math.min(SPAN_MAX, Math.max(SPAN_MIN, value)))
}

function fitPlayer(): void {
  const stage = stageRef.value
  if (!stage) return
  const box = stage.getBoundingClientRect()
  for (const node of stage.children) {
    if (!(node instanceof HTMLElement)) continue
    node.style.width = `${box.width}px`
    node.style.height = `${box.height}px`
  }
}

function onResizeDown(event: PointerEvent): void {
  const host = rootRef.value
  const bounds = host?.offsetParent
  if (!(host instanceof HTMLElement) || !(bounds instanceof HTMLElement)) return
  event.preventDefault()
  event.stopPropagation()
  const parentBox = bounds.getBoundingClientRect()
  const box = host.getBoundingClientRect()
  const startX = event.clientX
  const startY = event.clientY
  dragging = true
  const move = (ev: PointerEvent): void => {
    if (parentBox.width <= 0 || parentBox.height <= 0) return
    localWidth.value = clampSpan(((box.width + ev.clientX - startX) / parentBox.width) * 100)
    localHeight.value = clampSpan(((box.height + ev.clientY - startY) / parentBox.height) * 100)
    void nextTick().then(fitPlayer)
  }
  const up = (): void => {
    dragging = false
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', up)
    emit('resize', { width: localWidth.value, height: localHeight.value })
    void nextTick().then(fitPlayer)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
}

function onSkip(): void {
  dismissed.value = true
  void destroyPlayer()
}

async function destroyPlayer(): Promise<void> {
  if (player) {
    player.dispose()
    player = null
  }
  playerSlot.value = 0
  await nextTick()
}

async function loadPlayer(): Promise<void> {
  const gen = ++loadGen
  await destroyPlayer()
  if (!props.mediaId || gen !== loadGen) return
  loading.value = true
  try {
    const token =
      props.source === 'admin'
        ? await playVodMedia(props.mediaId, props.organizationId)
        : await playTrainingVod(props.mediaId)
    if (gen !== loadGen) return
    playerSlot.value = gen
    await nextTick()
    if (gen !== loadGen) return
    const [TCPlayer] = await Promise.all([
      import('tcplayer.js').then((mod) => mod.default),
      import('tcplayer.js/dist/tcplayer.min.css'),
    ])
    if (gen !== loadGen) return
    player = TCPlayer(playerId, {
      fileID: token.fileId,
      appID: token.appId,
      psign: token.psign,
      licenseUrl: token.licenseUrl,
      licenseKey: token.licenseKey,
      language: isZh.value ? 'zh-CN' : 'en',
      autoplay: props.autoplay,
      muted: props.autoplay,
      width: '100%',
      height: '100%',
    })
    await nextTick()
    fitPlayer()
  } catch {
    if (gen === loadGen) {
      notify.errorKey('admin.vod.playFailed')
    }
  } finally {
    if (gen === loadGen) loading.value = false
  }
}

watch(
  () => [props.mediaId, props.autoplay, props.stepKey] as const,
  () => {
    dismissed.value = false
    localWidth.value = props.width ?? DEFAULT_WIDTH
    localHeight.value = props.height ?? DEFAULT_HEIGHT
    void loadPlayer()
  },
  { immediate: true }
)

watch(
  () => [props.width, props.height] as const,
  () => {
    if (dragging) return
    localWidth.value = props.width ?? DEFAULT_WIDTH
    localHeight.value = props.height ?? DEFAULT_HEIGHT
  }
)

onBeforeUnmount(() => {
  void destroyPlayer()
})
</script>

<template>
  <div
    v-if="!dismissed"
    ref="rootRef"
    class="vod-player"
    :style="{ width: `${localWidth}%`, height: `${localHeight}%` }"
  >
    <div class="vod-player__bar">
      <button
        type="button"
        class="vod-player__skip"
        @click="onSkip"
      >
        <I18nText k="training.vod.skip" />
      </button>
      <button
        v-if="canNext"
        type="button"
        class="vod-player__next"
        @click="emit('next')"
      >
        <I18nText k="training.vod.next" />
      </button>
    </div>
    <p
      v-if="loading"
      class="vod-player__hint"
    >
      <I18nText k="common.loading" />
    </p>
    <div
      ref="stageRef"
      class="vod-player__stage"
    >
      <video
        v-if="playerSlot"
        :id="playerId"
        :key="playerSlot"
        class="vod-player__video"
        preload="auto"
        playsinline
      />
    </div>
    <button
      type="button"
      class="vod-player__resize"
      :aria-label="t('training.vod.resize')"
      @pointerdown="onResizeDown"
    />
  </div>
</template>

<style scoped>
.vod-player {
  position: absolute;
  display: flex;
  flex-direction: column;
  min-width: 12rem;
  min-height: 8rem;
  background: #111;
  border-radius: 0.5rem;
  overflow: hidden;
  box-shadow: 0 10px 28px rgb(0 0 0 / 0.28);
}
.vod-player__bar {
  display: flex;
  flex-shrink: 0;
  justify-content: flex-end;
  gap: 0.35rem;
  padding: 0.35rem;
  background: #1c1917;
}
.vod-player__skip,
.vod-player__next {
  border: 0;
  border-radius: 0.25rem;
  padding: 0.22rem 0.6rem;
  font-size: 0.75rem;
  cursor: pointer;
}
.vod-player__skip {
  background: transparent;
  color: #fafaf9;
}
.vod-player__next {
  background: #fafaf9;
  color: #1c1917;
}
.vod-player__hint {
  margin: 0;
  padding: 0.75rem;
  color: #e7e5e4;
  font-size: 0.8rem;
}
.vod-player__stage {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.vod-player__video {
  display: block;
  width: 100%;
  height: 100%;
  background: #111;
}
.vod-player__resize {
  position: absolute;
  right: 0;
  bottom: 0;
  z-index: 5;
  width: 1.1rem;
  height: 1.1rem;
  border: 0;
  background:
    linear-gradient(135deg, transparent 50%, #fafaf9 50%, #fafaf9 62%, transparent 62%),
    linear-gradient(135deg, transparent 70%, #fafaf9 70%, #fafaf9 82%, transparent 82%);
  cursor: nwse-resize;
}
</style>
