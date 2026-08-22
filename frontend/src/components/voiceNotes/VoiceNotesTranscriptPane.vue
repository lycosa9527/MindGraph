<script setup lang="ts">
/**
 * Left-aligned transcript: one row per sentence. Editable after stop.
 */
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useVoiceNotesStore } from '@/stores/voiceNotes'
import {
  fitVoiceNotesTextarea,
  speakerAvatarGlyph,
  speakerDisplayName,
} from '@/utils/voiceNotesTranscript'

const { t } = useLanguage()
const voiceNotes = useVoiceNotesStore()
const paneRef = ref<HTMLElement | null>(null)
let resizeObserver: ResizeObserver | null = null

function editorsInPane(): HTMLTextAreaElement[] {
  const pane = paneRef.value
  if (!pane) return []
  return [...pane.querySelectorAll('textarea')].filter((el) =>
    el.classList.contains('vn-chat__bubble--edit')
  )
}

function fitEditors(): void {
  for (const editor of editorsInPane()) {
    fitVoiceNotesTextarea(editor)
  }
}

watch(
  () => [voiceNotes.turns.length, voiceNotes.transcriptText, voiceNotes.canEditTranscript] as const,
  async () => {
    await nextTick()
    const pane = paneRef.value
    if (!pane) return
    if (voiceNotes.canEditTranscript) {
      fitEditors()
      return
    }
    pane.scrollTop = pane.scrollHeight
  }
)

onMounted(() => {
  if (typeof ResizeObserver === 'undefined') return
  const pane = paneRef.value
  if (!pane) return
  resizeObserver = new ResizeObserver(() => {
    if (voiceNotes.canEditTranscript) fitEditors()
  })
  resizeObserver.observe(pane)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
})

function nameFor(speakerId: number): string {
  if (speakerId < 0) return ''
  return speakerDisplayName(voiceNotes.labelForSpeakerId(speakerId))
}

function avatarFor(speakerId: number): string {
  if (speakerId < 0) return '·'
  return speakerAvatarGlyph(voiceNotes.speakerNames[speakerId] ?? '', speakerId + 1)
}

function onEdit(index: number, event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLTextAreaElement)) return
  voiceNotes.applyEditedTurn(index, target.value)
  fitVoiceNotesTextarea(target)
}
</script>

<template>
  <div
    ref="paneRef"
    class="vn-chat"
    :aria-label="t('auth.voiceNotes.viewTranscript')"
    :aria-live="voiceNotes.canEditTranscript ? 'off' : 'polite'"
  >
    <p
      v-if="voiceNotes.turns.length === 0"
      class="vn-chat__empty"
    >
      {{ t('auth.voiceNotes.empty') }}
    </p>
    <article
      v-for="(turn, index) in voiceNotes.turns"
      :key="`${index}-${turn.sentenceId}-${turn.startTime}`"
      class="vn-chat__row"
      :class="{ 'vn-chat__row--live': turn.live }"
    >
      <div
        class="vn-chat__avatar"
        aria-hidden="true"
      >
        {{ avatarFor(turn.speakerId) }}
      </div>
      <div class="vn-chat__msg">
        <div
          v-if="nameFor(turn.speakerId)"
          class="vn-chat__name"
        >
          {{ nameFor(turn.speakerId) }}
        </div>
        <textarea
          v-if="voiceNotes.canEditTranscript && !turn.live"
          class="vn-chat__bubble vn-chat__bubble--edit"
          rows="1"
          :value="turn.text"
          spellcheck="true"
          @input="onEdit(index, $event)"
        />
        <p
          v-else
          class="vn-chat__bubble"
        >
          {{ turn.text }}
        </p>
      </div>
    </article>
  </div>
</template>

<style scoped>
.vn-chat {
  box-sizing: border-box;
  width: 100%;
  flex: 1;
  height: 100%;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 0.75rem 0.85rem;
}

.vn-chat__empty {
  margin: 0;
  color: #a8a29e;
  line-height: 1.55;
}

.vn-chat__row {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin: 0 0 0.7rem;
  width: 100%;
}

.vn-chat__row--live .vn-chat__bubble {
  color: #78716c;
}

.vn-chat__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.55rem;
  height: 1.55rem;
  flex-shrink: 0;
  border-radius: 9999px;
  background: #1c1917;
  color: #fafaf9;
  font-size: 0.7rem;
  font-weight: 700;
}

.vn-chat__msg {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  flex: 1;
}

.vn-chat__name {
  margin-bottom: 0.2rem;
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.02em;
  color: #78716c;
}

.vn-chat__bubble {
  display: block;
  box-sizing: border-box;
  margin: 0;
  max-width: 100%;
  padding: 0.45rem 0.7rem;
  border-radius: 0.85rem;
  background: #f5f5f4;
  color: #1c1917;
  font-size: 0.9375rem;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.vn-chat__bubble--edit {
  width: 100%;
  min-height: calc(1.55em + 0.9rem);
  border: 1px solid #d6d3d1;
  resize: none;
  overflow: hidden;
  field-sizing: content;
  font: inherit;
  font-size: 0.9375rem;
  line-height: 1.55;
  outline: none;
}

.vn-chat__bubble--edit:focus {
  border-color: #1c1917;
  background: #ffffff;
}
</style>
