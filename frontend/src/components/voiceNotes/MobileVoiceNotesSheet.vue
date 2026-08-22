<script setup lang="ts">
/**
 * In-page mobile Voice Notes recorder. Stop saves the transcript;
 * Generate mindmap is a separate Swiss action.
 */
import { computed } from 'vue'

import { Loader2, Mic, Pause, Play, Square } from '@lucide/vue'

import VoiceNotesSpeakerEditor from '@/components/voiceNotes/VoiceNotesSpeakerEditor.vue'
import VoiceNotesTranscriptPane from '@/components/voiceNotes/VoiceNotesTranscriptPane.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import type { useMobileVoiceNotesSession } from '@/composables/voiceNotes/useMobileVoiceNotesSession'
import { useVoiceNotesSessionChrome } from '@/composables/voiceNotes/useVoiceNotesSessionChrome'

const props = defineProps<{
  session: ReturnType<typeof useMobileVoiceNotesSession>
}>()

const { t } = useLanguage()
const voiceNotes = props.session.voiceNotes
const isBusy = computed(() => props.session.busy.value)
const { sessionLabel, actions } = useVoiceNotesSessionChrome({
  generating: props.session.generating,
  persisting: props.session.persisting,
})
const isLiveLevel = computed(() => voiceNotes.recording && !voiceNotes.paused)
const levelRingStyle = computed(() => {
  const level = isLiveLevel.value ? Math.min(1, Math.max(0, voiceNotes.inputLevel)) : 0
  return {
    transform: `scale(${1 + level * 0.32})`,
    opacity: isLiveLevel.value ? String(0.2 + level * 0.55) : '0',
  }
})
const mainLevelStyle = computed(() => {
  const level = isLiveLevel.value ? Math.min(1, Math.max(0, voiceNotes.inputLevel)) : 0
  const spread = 7 + level * 18
  const alpha = isLiveLevel.value ? 0.14 + level * 0.3 : 0.1
  return {
    boxShadow: `0 0 0 ${spread}px rgba(220, 38, 38, ${alpha})`,
  }
})

const mainActionLabel = computed(() => {
  if (actions.value.canResume) return t('auth.voiceNotes.resume')
  if (actions.value.canPause) return t('auth.voiceNotes.pause')
  return t('auth.voiceNotes.start')
})

function onStart(): void {
  void voiceNotes.startRecording()
}

function onMainAction(): void {
  if (actions.value.canResume) {
    onResume()
    return
  }
  if (actions.value.canStart) {
    onStart()
    return
  }
  if (actions.value.canPause) {
    onPause()
  }
}

function onPause(): void {
  voiceNotes.pauseRecording()
}

function onResume(): void {
  voiceNotes.resumeRecording()
}

function onStop(): void {
  void props.session.stopRecordingOnly()
}

function onGenerate(): void {
  void props.session.generateMindmap()
}
</script>

<template>
  <div
    class="vn-mobile-sheet"
    role="region"
    :aria-label="t('auth.voiceNotes.modalTitle')"
  >
    <div class="vn-mobile-sheet__status">
      <span
        class="vn-mobile-sheet__dot"
        :class="{
          'vn-mobile-sheet__dot--live': voiceNotes.recording && !voiceNotes.paused,
          'vn-mobile-sheet__dot--paused': voiceNotes.paused,
        }"
      />
      <span>{{ sessionLabel }}</span>
      <Loader2
        v-if="isBusy || voiceNotes.connecting"
        class="vn-mobile-sheet__spin"
        :size="16"
      />
    </div>

    <div class="vn-mobile-sheet__body">
      <VoiceNotesTranscriptPane />
    </div>

    <footer class="vn-dock">
      <div class="vn-dock__bar">
        <div class="vn-dock__wing vn-dock__wing--start">
          <VoiceNotesSpeakerEditor variant="dock" />
        </div>
        <div class="vn-dock__row">
          <button
            type="button"
            class="vn-dock__side"
            :disabled="!actions.canPause"
            :aria-label="t('auth.voiceNotes.pause')"
            @click="onPause"
          >
            <span class="vn-dock__side-icon">
              <Pause
                :size="22"
                :stroke-width="2.2"
              />
            </span>
            <span class="vn-dock__side-label">{{ t('auth.voiceNotes.pause') }}</span>
          </button>

          <div class="vn-dock__main-wrap">
            <span
              class="vn-dock__main-ring"
              aria-hidden="true"
              :style="levelRingStyle"
            />
            <button
              type="button"
              class="vn-dock__main"
              :class="{ 'vn-dock__main--resume': actions.canResume }"
              :style="mainLevelStyle"
              :disabled="!actions.canStart && !actions.canResume && !actions.canPause"
              :aria-label="mainActionLabel"
              @click="onMainAction"
            >
              <Loader2
                v-if="voiceNotes.connecting || voiceNotes.sessionStatus === 'starting'"
                class="vn-mobile-sheet__spin"
                :size="28"
              />
              <Play
                v-else-if="actions.canResume"
                :size="30"
                :stroke-width="2.2"
                fill="currentColor"
              />
              <Mic
                v-else
                :size="28"
                :stroke-width="2"
              />
            </button>
          </div>

          <button
            type="button"
            class="vn-dock__side"
            :disabled="!actions.canStop"
            :aria-label="t('auth.voiceNotes.stop')"
            @click="onStop"
          >
            <span class="vn-dock__side-icon vn-dock__side-icon--stop">
              <Square
                :size="18"
                :stroke-width="2.5"
                fill="currentColor"
              />
            </span>
            <span class="vn-dock__side-label">{{ t('auth.voiceNotes.stop') }}</span>
          </button>
        </div>
        <div class="vn-dock__wing vn-dock__wing--end">
          <button
            type="button"
            class="vn-swiss-opt vn-swiss-opt--solid"
            :disabled="!actions.canGenerate"
            @click="onGenerate"
          >
            {{ t('auth.voiceNotes.retryGenerate') }}
          </button>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.vn-mobile-sheet {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  background: #f9fafb;
  color: #1c1917;
  padding-bottom: env(safe-area-inset-bottom);
}

.vn-mobile-sheet__status {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.75rem 1.15rem 0.55rem;
  font-size: 0.8125rem;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: -0.01em;
  color: #57534e;
}

.vn-mobile-sheet__dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 9999px;
  background: #a8a29e;
}

.vn-mobile-sheet__dot--live {
  background: #dc2626;
  box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.15);
}

.vn-mobile-sheet__dot--paused {
  background: #d97706;
}

.vn-mobile-sheet__spin {
  animation: vn-spin 0.8s linear infinite;
}

.vn-mobile-sheet__body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  margin: 0 1rem;
  padding: 0;
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  background: #ffffff;
}

.vn-dock {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.65rem;
  padding: 1rem 1rem 1.15rem;
  overflow: visible;
  background: #ffffff;
  border-top: 1px solid #e5e7eb;
}

.vn-dock__bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  column-gap: 1.25rem;
  width: 100%;
}

.vn-dock__wing {
  display: flex;
  min-width: 0;
}

.vn-dock__wing--start {
  justify-content: flex-end;
}

.vn-dock__wing--end {
  justify-content: flex-start;
}

.vn-dock__row {
  display: grid;
  grid-template-columns: 3.25rem 4.5rem 3.25rem;
  align-items: center;
  justify-items: center;
}

.vn-swiss-opt {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 1;
  box-sizing: border-box;
  width: 7.5rem;
  min-height: 2.15rem;
  padding: 0.35rem 0.55rem;
  border: 1px solid #1c1917;
  border-radius: 9999px;
  background: transparent;
  color: #1c1917;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  line-height: 1.2;
  text-align: center;
  white-space: nowrap;
  max-width: 100%;
}

.vn-swiss-opt:disabled {
  opacity: 0.35;
}

.vn-swiss-opt:active:not(:disabled) {
  background: #f5f5f4;
}

.vn-swiss-opt--on {
  background: #1c1917;
  color: #fafaf9;
}

.vn-swiss-opt--on:active:not(:disabled),
.vn-swiss-opt--solid:active:not(:disabled) {
  background: #292524;
}

.vn-swiss-opt--solid {
  background: #1c1917;
  color: #fafaf9;
}

.vn-dock__side {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  border: 0;
  background: transparent;
  color: #374151;
}

.vn-dock__side:disabled {
  opacity: 0.28;
}

.vn-dock__side-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 3.25rem;
  height: 3.25rem;
  border-radius: 9999px;
  background: #f3f4f6;
  color: #111827;
}

.vn-dock__side-icon--stop {
  color: #b91c1c;
}

.vn-dock__side-label {
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.vn-dock__main-wrap {
  position: relative;
  width: 4.5rem;
  height: 4.5rem;
  margin: 0 auto;
}

.vn-dock__main-ring {
  position: absolute;
  inset: -5px;
  border: 2px solid #dc2626;
  border-radius: 9999px;
  pointer-events: none;
  transition:
    transform 0.08s linear,
    opacity 0.08s linear;
}

.vn-dock__main {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 4.5rem;
  height: 4.5rem;
  border: 0;
  border-radius: 9999px;
  background: #dc2626;
  color: #ffffff;
  transition: box-shadow 0.08s linear;
}

.vn-dock__main:disabled {
  opacity: 0.45;
}

.vn-dock__main--resume {
  background: #111827;
}

@keyframes vn-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
