<script setup lang="ts">
/**
 * Perched Kitty teacher caption for 图示生图 slides — speaks teacher_script via DashScope TTS.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { Volume2, VolumeX } from '@lucide/vue'

import KittyBlackCatMascot from '@/components/kitty/KittyBlackCatMascot.vue'

import { useLanguage } from '@/composables'
import type { KittyAgentState } from '@/composables/kitty/useKittyAgent'
import { apiPost } from '@/utils/apiClient'

const props = defineProps<{
  slideTitle?: string | null
  teacherScript?: string | null
  /** Auto-play narration when the script changes (default on). */
  autoPlay?: boolean
}>()

const { t } = useLanguage()

const muted = ref(false)
const speaking = ref(false)
const loading = ref(false)
const errorHint = ref('')

let audioEl: HTMLAudioElement | null = null
let objectUrl: string | null = null
let speakSeq = 0

const audioCache = new Map<string, Blob>()

const agentState = computed<KittyAgentState>(() => {
  if (loading.value) return 'connecting'
  if (speaking.value) return 'speaking'
  return 'idle'
})

const hasScript = computed(() => Boolean((props.teacherScript || '').trim()))

/** Short on-screen caption; full teacher_script still drives TTS. */
const captionText = computed(() => {
  const title = (props.slideTitle || '').trim()
  if (title) return title
  return (props.teacherScript || '').trim()
})

const hasCaption = computed(() => Boolean(captionText.value))

function stopAudio(): void {
  if (audioEl) {
    audioEl.pause()
    audioEl.onended = null
    audioEl.onerror = null
    audioEl.src = ''
    audioEl = null
  }
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = null
  }
  speaking.value = false
  loading.value = false
}

async function fetchAudioBlob(text: string): Promise<Blob> {
  const cached = audioCache.get(text)
  if (cached) return cached
  const response = await apiPost('/api/zhihui/teacher-tts', { text })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail?: unknown }).detail || '')
        : ''
    throw new Error(detail || response.statusText || 'TTS failed')
  }
  const blob = await response.blob()
  if (blob.size < 32) {
    throw new Error('Empty audio')
  }
  audioCache.set(text, blob)
  return blob
}

async function speak(text: string): Promise<void> {
  const trimmed = text.trim()
  if (!trimmed || muted.value) return
  const seq = ++speakSeq
  stopAudio()
  loading.value = true
  errorHint.value = ''
  try {
    const blob = await fetchAudioBlob(trimmed)
    if (seq !== speakSeq) return
    objectUrl = URL.createObjectURL(blob)
    audioEl = new Audio(objectUrl)
    audioEl.onended = () => {
      if (seq !== speakSeq) return
      speaking.value = false
    }
    audioEl.onerror = () => {
      if (seq !== speakSeq) return
      speaking.value = false
      errorHint.value = String(t('zhihui.diagram.ttsFailed'))
    }
    speaking.value = true
    loading.value = false
    await audioEl.play()
  } catch (err) {
    if (seq !== speakSeq) return
    loading.value = false
    speaking.value = false
    errorHint.value = err instanceof Error ? err.message : String(t('zhihui.diagram.ttsFailed'))
  }
}

function toggleMute(): void {
  muted.value = !muted.value
  if (muted.value) {
    stopAudio()
  } else if (hasScript.value) {
    void speak(props.teacherScript || '')
  }
}

function onKittyClick(): void {
  if (!hasScript.value) return
  if (speaking.value || loading.value) {
    stopAudio()
    return
  }
  void speak(props.teacherScript || '')
}

watch(
  () => [props.teacherScript, props.autoPlay] as const,
  ([script, auto]) => {
    stopAudio()
    errorHint.value = ''
    if (auto !== false && !muted.value && (script || '').trim()) {
      void speak(script || '')
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  speakSeq += 1
  stopAudio()
})
</script>

<template>
  <div class="zhihui-teacher-caption">
    <div
      v-if="hasCaption"
      class="zhihui-teacher-caption__stack"
    >
      <button
        v-if="hasScript"
        type="button"
        class="zhihui-teacher-caption__kitty"
        :aria-label="
          speaking || loading
            ? t('zhihui.diagram.ttsStop')
            : t('zhihui.diagram.ttsPlay')
        "
        @click="onKittyClick"
      >
        <KittyBlackCatMascot :agent-state="agentState" />
      </button>

      <div class="zhihui-teacher-caption__field">
        <p
          class="zhihui-teacher-caption__text"
          :title="teacherScript || captionText"
        >
          <span class="sr-only">{{ t('zhihui.diagram.teacherScript') }}：</span>
          {{ captionText }}
        </p>
        <button
          v-if="hasScript"
          type="button"
          class="zhihui-teacher-caption__mute"
          :aria-pressed="muted"
          :aria-label="muted ? t('zhihui.diagram.ttsUnmute') : t('zhihui.diagram.ttsMute')"
          @click="toggleMute"
        >
          <VolumeX
            v-if="muted"
            class="h-3.5 w-3.5"
            :stroke-width="2"
          />
          <Volume2
            v-else
            class="h-3.5 w-3.5"
            :stroke-width="2"
          />
        </button>
      </div>
    </div>
    <p
      v-if="errorHint"
      class="zhihui-teacher-caption__error"
      role="status"
    >
      {{ errorHint }}
    </p>
  </div>
</template>

<style scoped>
.zhihui-teacher-caption {
  width: 50%;
  max-width: 22rem;
  min-width: 11rem;
  margin-inline: auto;
  overflow: visible;
}

.zhihui-teacher-caption__stack {
  position: relative;
  padding-top: 1.85rem;
}

.zhihui-teacher-caption__kitty {
  position: absolute;
  left: 6px;
  bottom: calc(100% - 6px);
  z-index: 5;
  display: block;
  width: 2.35rem;
  max-height: 3rem;
  aspect-ratio: 272 / 344;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 10px;
  transition: transform 0.15s ease;
}

.zhihui-teacher-caption__kitty:hover {
  transform: translateY(-1px);
}

.zhihui-teacher-caption__kitty:focus-visible {
  outline: 2px solid rgb(245 158 11 / 0.55);
  outline-offset: 2px;
}

.zhihui-teacher-caption__kitty:deep(.kitty-black-cat-mascot) {
  width: 100%;
  max-width: none;
  max-height: none;
  aspect-ratio: 272 / 344;
  margin: 0;
}

.zhihui-teacher-caption__kitty:deep(.black-cat-container) {
  width: 100%;
  height: 100%;
}

.zhihui-teacher-caption__kitty:deep(.black-cat-container .kitty-svg) {
  width: 100%;
  height: 100%;
  overflow: visible;
  filter: drop-shadow(0 2px 4px rgb(15 23 42 / 0.12));
}

.zhihui-teacher-caption__field {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  min-height: 2.25rem;
  padding: 0.4rem 0.45rem 0.4rem 0.7rem;
  border: 1px solid #e7e5e4;
  border-radius: 999px;
  background: rgb(255 255 255 / 0.96);
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.04);
}

.zhihui-teacher-caption__text {
  margin: 0;
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8125rem;
  font-weight: 500;
  line-height: 1.35;
  color: #44403c;
  text-align: left;
}

.zhihui-teacher-caption__mute {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #a8a29e;
  cursor: pointer;
}

.zhihui-teacher-caption__mute:hover {
  background: #f5f5f4;
  color: #57534e;
}

.zhihui-teacher-caption__error {
  margin: 0.3rem 0 0;
  font-size: 11px;
  color: #e11d48;
  text-align: center;
}
</style>
