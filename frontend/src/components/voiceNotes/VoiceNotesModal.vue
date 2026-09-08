<script setup lang="ts">
/**
 * Voice notes transcript modal — Swiss stone shell, pill actions.
 * Closing does not stop an active recording.
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { storeToRefs } from 'pinia'

import { ArrowUpRight, Copy, Mic, Pause, Square } from '@lucide/vue'

import AiGenerateGlassHero from '@/components/canvas/AiGenerateGlassHero.vue'
import '@/components/canvas/aiGenerateGlass.css'
import VoiceNotesSpeakerEditor from '@/components/voiceNotes/VoiceNotesSpeakerEditor.vue'
import VoiceNotesTranscriptPane from '@/components/voiceNotes/VoiceNotesTranscriptPane.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { isMobileAppPath } from '@/composables/voiceNotes/mobileVoiceNotesFinish'
import { useVoiceNotesSessionChrome } from '@/composables/voiceNotes/useVoiceNotesSessionChrome'
import { useVoiceNotesStore } from '@/stores/voiceNotes'

const { t } = useLanguage()
const route = useRoute()
const notify = useNotifications()
const voiceNotes = useVoiceNotesStore()
const isMobileShell = computed(() => route.meta.layout === 'mobile' || isMobileAppPath(route.path))
const { modalOpen, elapsedMs } = storeToRefs(voiceNotes)
const { statusLabel, saveKind, statusClickable, onStatusClick, actions } =
  useVoiceNotesSessionChrome()

const elapsedLabel = computed(() => {
  const totalSec = Math.floor(elapsedMs.value / 1000)
  const mm = String(Math.floor(totalSec / 60)).padStart(2, '0')
  const ss = String(totalSec % 60).padStart(2, '0')
  return `${mm}:${ss}`
})

function onClose(): void {
  voiceNotes.closeModal()
}

function onStart(): void {
  void voiceNotes.startRecording()
}

function onPause(): void {
  voiceNotes.pauseRecording()
}

function onResume(): void {
  voiceNotes.resumeRecording()
}

function onStop(): void {
  void voiceNotes.stopRecording()
}

function onJump(): void {
  void voiceNotes.jumpToMindmap()
}

async function onCopy(): Promise<void> {
  const text = voiceNotes.transcriptText.trim()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    notify.success(t('auth.voiceNotes.copied'))
  } catch {
    notify.warning(t('auth.voiceNotes.genericError'))
  }
}
</script>

<template>
  <el-dialog
    :model-value="modalOpen && !isMobileShell"
    width="min(560px, 92vw)"
    top="12vh"
    append-to-body
    destroy-on-close
    class="voice-notes-swiss mm-canvas-upper-dialog ai-gen-shell ai-gen-shell--voice"
    :show-close="false"
    @close="onClose"
  >
    <template #header>
      <AiGenerateGlassHero
        variant="voice"
        @close="onClose"
      />
      <div class="vn-swiss__note vn-swiss__note--glass">
        <span
          class="vn-swiss__status"
          :class="{
            'vn-swiss__status--dirty': saveKind === 'unsaved',
            'vn-swiss__status--saving': saveKind === 'saving',
            'vn-swiss__status--click': statusClickable,
          }"
          @click="onStatusClick"
          >{{ statusLabel }}</span
        >
        <span class="vn-swiss__elapsed">{{ elapsedLabel }}</span>
      </div>
    </template>

    <div class="vn-swiss__stack">
      <div class="vn-swiss__kicker">
        <span class="vn-swiss__kicker-label">{{ t('auth.voiceNotes.viewTranscript') }}</span>
        <VoiceNotesSpeakerEditor variant="pill" />
      </div>

      <div class="vn-swiss__body">
        <VoiceNotesTranscriptPane />
      </div>
    </div>

    <template #footer>
      <div class="vn-swiss__footer">
        <div class="vn-swiss__footer-left">
          <button
            type="button"
            class="vn-pill vn-pill--ghost"
            :disabled="!actions.canCopy"
            @click="onCopy"
          >
            <Copy
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
            {{ t('auth.voiceNotes.copy') }}
          </button>
          <button
            type="button"
            class="vn-pill vn-pill--ghost"
            :disabled="!actions.canJump"
            @click="onJump"
          >
            <span>{{ t('auth.voiceNotes.jumpToMindmap') }}</span>
            <ArrowUpRight
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
          </button>
        </div>

        <div class="vn-swiss__footer-right">
          <button
            v-if="actions.canStart"
            type="button"
            class="vn-pill vn-pill--solid"
            @click="onStart"
          >
            <Mic
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
            {{ t('auth.voiceNotes.start') }}
          </button>
          <button
            v-if="actions.canPause"
            type="button"
            class="vn-pill vn-pill--ghost"
            @click="onPause"
          >
            <Pause
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
            {{ t('auth.voiceNotes.pause') }}
          </button>
          <button
            v-if="actions.canResume"
            type="button"
            class="vn-pill vn-pill--solid"
            @click="onResume"
          >
            <Mic
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
            {{ t('auth.voiceNotes.resume') }}
          </button>
          <button
            v-if="actions.canStop"
            type="button"
            class="vn-pill vn-pill--danger"
            @click="onStop"
          >
            <Square
              class="vn-pill__icon"
              :size="12"
              :stroke-width="2.5"
            />
            {{ t('auth.voiceNotes.stop') }}
          </button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style>
.voice-notes-swiss.el-dialog {
  --vn-ink: #1c1917;
  --vn-body: #44403c;
  --vn-muted: #78716c;
  --vn-subtle: #a8a29e;
  --vn-border: #e7e5e4;
  --vn-border-strong: #d6d3d1;
  --vn-surface: #ffffff;
  --vn-inset: #fafaf9;
  --vn-hover: #f5f5f4;
  --vn-danger: #b91c1c;

  --el-dialog-padding-primary: 0px;
  border-radius: 22px;
  overflow: hidden;
  border: 1px solid var(--vn-border);
  box-shadow:
    0 10px 15px -3px rgba(0, 0, 0, 0.08),
    0 4px 6px -4px rgba(0, 0, 0, 0.06);
}

.voice-notes-swiss .el-dialog__header {
  margin: 0;
  padding: 0;
}

.voice-notes-swiss .el-dialog__headerbtn {
  top: 1rem;
  right: 1rem;
}

.voice-notes-swiss .el-dialog__headerbtn .el-dialog__close {
  color: var(--vn-muted);
}

.voice-notes-swiss .el-dialog__headerbtn:hover .el-dialog__close {
  color: var(--vn-ink);
}

.voice-notes-swiss .el-dialog__body {
  padding: 0.25rem 1.25rem 1rem;
}

.voice-notes-swiss .el-dialog__footer {
  padding: 0.75rem 1.25rem 1.15rem;
  border-top: 1px solid var(--vn-border);
}
</style>

<style scoped>
.vn-swiss__header {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding-right: 1.75rem;
  min-width: 0;
}

.vn-swiss__glyph {
  color: var(--vn-muted, #78716c);
  font-size: 0.85rem;
  line-height: 1;
}

.vn-swiss__title {
  font-size: 1rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--vn-ink, #1c1917);
  white-space: nowrap;
}

.vn-swiss__divider {
  flex: 1;
  height: 1px;
  background: var(--vn-border, #e7e5e4);
  min-width: 0.75rem;
}

.vn-swiss__note--glass {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.55rem;
  padding: 0 18px 10px;
  font-size: 0.75rem;
  color: var(--vn-muted, #78716c);
}

.vn-swiss__status {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  letter-spacing: 0.02em;
  font-weight: 600;
}

.vn-swiss__status--dirty {
  color: #d97706;
}

.vn-swiss__status--saving {
  color: #2563eb;
}

.vn-swiss__status--click {
  cursor: pointer;
}

.vn-swiss__elapsed {
  font-variant-numeric: tabular-nums;
  color: var(--vn-ink, #1c1917);
  font-weight: 650;
}

.vn-swiss__stack {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.vn-swiss__kicker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  font-size: 0.7rem;
  font-weight: 650;
  color: var(--vn-muted, #78716c);
  position: relative;
  z-index: 2;
}

.vn-swiss__kicker-label {
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.vn-swiss__kicker::before {
  content: '';
  width: 0.35rem;
  height: 0.35rem;
  border-radius: 9999px;
  background: var(--vn-ink, #1c1917);
}

.vn-swiss__body {
  display: flex;
  flex-direction: column;
  height: min(48vh, 26rem);
  min-height: 10rem;
  overflow: hidden;
  padding: 0;
  border: 1px solid var(--vn-border, #e7e5e4);
  border-radius: 10px;
  background: var(--vn-inset, #fafaf9);
  color: var(--vn-ink, #1c1917);
}

.vn-swiss__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.vn-swiss__footer-left,
.vn-swiss__footer-right {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.vn-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  min-height: 2.15rem;
  padding: 0 1rem;
  border-radius: 9999px;
  border: 1px solid var(--vn-ink, #1c1917);
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease,
    opacity 0.15s ease;
}

.vn-pill:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.vn-pill__icon {
  flex-shrink: 0;
}

.vn-pill--ghost {
  background: transparent;
  color: var(--vn-ink, #1c1917);
}

.vn-pill--ghost:hover:not(:disabled) {
  background: var(--vn-hover, #f5f5f4);
}

.vn-pill--solid {
  background: var(--vn-ink, #1c1917);
  color: var(--vn-surface, #ffffff);
}

.vn-pill--solid:hover:not(:disabled) {
  background: #292524;
  border-color: #292524;
}

.vn-pill--danger {
  background: transparent;
  color: var(--vn-danger, #b91c1c);
  border-color: var(--vn-danger, #b91c1c);
}

.vn-pill--danger:hover:not(:disabled) {
  background: #fef2f2;
}
</style>
