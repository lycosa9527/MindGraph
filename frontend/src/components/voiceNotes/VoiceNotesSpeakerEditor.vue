<script setup lang="ts">
/**
 * Rename Tencent diarization slots. Menu merges a mistaken talker into another;
 * delete restores the default 说话人1 / 2 / 3 label (extra slots fold back).
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { onClickOutside, useEventListener } from '@vueuse/core'

import { EllipsisVertical, Trash2 } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useVoiceNotesStore } from '@/stores/voiceNotes'
import {
  placePopoverNearTrigger,
  popoverPlacementStyle,
  visualViewportClip,
} from '@/utils/voiceNotesPopoverFit'
import {
  VOICE_NOTES_MIN_SPEAKER_SLOTS,
  speakerAvatarGlyph,
  speakerDisplayName,
  speakerLabelSuffix,
} from '@/utils/voiceNotesTranscript'

const props = withDefaults(
  defineProps<{
    variant?: 'dock' | 'pill'
  }>(),
  { variant: 'dock' }
)

const { t } = useLanguage()
const voiceNotes = useVoiceNotesStore()
const rootRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const mergeTriggerRef = ref<HTMLElement | null>(null)
const open = ref(false)
const mergeForId = ref<number | null>(null)
const hiddenPlace = { position: 'fixed', visibility: 'hidden', top: '0', left: '0' }
const panelStyle = ref<Record<string, string>>({ ...hiddenPlace })
const menuStyle = ref<Record<string, string>>({ ...hiddenPlace })

onClickOutside(
  rootRef,
  () => {
    mergeForId.value = null
  },
  { ignore: [panelRef, menuRef] }
)

function preferredSide(): 'above' | 'below' {
  return props.variant === 'dock' ? 'above' : 'below'
}

async function layoutFloating(
  trigger: HTMLElement | null,
  popover: HTMLElement | null,
  assign: (style: Record<string, string>) => void
): Promise<void> {
  await nextTick()
  if (!trigger || !popover) return
  const placed = placePopoverNearTrigger(
    trigger.getBoundingClientRect(),
    { width: popover.offsetWidth, height: popover.scrollHeight },
    preferredSide(),
    visualViewportClip()
  )
  assign({ ...popoverPlacementStyle(placed), visibility: 'visible' })
}

function layoutOpenPopovers(): void {
  if (open.value) {
    void layoutFloating(triggerRef.value, panelRef.value, (style) => {
      panelStyle.value = style
    })
  }
  if (mergeForId.value !== null) {
    void layoutFloating(mergeTriggerRef.value, menuRef.value, (style) => {
      menuStyle.value = style
    })
  }
}

function closeFloating(): void {
  open.value = false
  mergeForId.value = null
}

watch([open, mergeForId, () => voiceNotes.speakerIds.length], () => {
  if (open.value || mergeForId.value !== null) layoutOpenPopovers()
})

watch(
  () => voiceNotes.modalOpen,
  (isOpen) => {
    if (!isOpen) closeFloating()
  }
)

onBeforeUnmount(closeFloating)

useEventListener(window, 'resize', layoutOpenPopovers)
useEventListener(window, 'scroll', layoutOpenPopovers, true)
const visualView = typeof window !== 'undefined' ? window.visualViewport : null
if (visualView) {
  useEventListener(visualView, 'resize', layoutOpenPopovers)
}

const placeholderSuffix = computed(() =>
  speakerLabelSuffix(String(t('auth.voiceNotes.speakerLabel', { n: 1 })))
)

function placeholderFor(speakerId: number): string {
  const raw = String(t('auth.voiceNotes.speakerLabel', { n: speakerId + 1 }))
  const suffix = placeholderSuffix.value
  return suffix && raw.endsWith(suffix)
    ? raw.slice(0, -suffix.length)
    : raw.replace(/[：:]\s*$/, '')
}

function displayName(speakerId: number): string {
  return speakerDisplayName(voiceNotes.labelForSpeakerId(speakerId)) || placeholderFor(speakerId)
}

function mergeTargets(speakerId: number): number[] {
  return voiceNotes.speakerIds.filter((id) => id !== speakerId)
}

function onRename(speakerId: number, event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) return
  voiceNotes.renameSpeaker(speakerId, target.value)
}

function toggleOpen(): void {
  if (voiceNotes.ingesting) return
  open.value = !open.value
  mergeForId.value = null
  if (open.value) layoutOpenPopovers()
}

function toggleMergeMenu(speakerId: number, event: MouseEvent): void {
  const target = event.currentTarget
  mergeTriggerRef.value = target instanceof HTMLElement ? target : null
  mergeForId.value = mergeForId.value === speakerId ? null : speakerId
  if (mergeForId.value !== null) layoutOpenPopovers()
}

function onMerge(fromId: number, intoId: number): void {
  voiceNotes.mergeSpeakers(fromId, intoId)
  mergeForId.value = null
}

function confirmOpenMerge(intoId: number): void {
  if (mergeForId.value === null) return
  onMerge(mergeForId.value, intoId)
}

function openMergeTargets(): number[] {
  return mergeForId.value === null ? [] : mergeTargets(mergeForId.value)
}

function onReset(speakerId: number): void {
  voiceNotes.resetSpeaker(speakerId)
  mergeForId.value = null
}

function canReset(speakerId: number): boolean {
  return speakerId >= VOICE_NOTES_MIN_SPEAKER_SLOTS || speakerId in voiceNotes.speakerNames
}
</script>

<template>
  <div
    ref="rootRef"
    class="vn-speaker-edit"
    :class="`vn-speaker-edit--${variant}`"
  >
    <button
      ref="triggerRef"
      type="button"
      :class="variant === 'pill' ? 'vn-pill vn-pill--ghost' : 'vn-swiss-opt'"
      :aria-expanded="open"
      :aria-controls="'vn-speaker-edit-panel'"
      :disabled="voiceNotes.ingesting"
      @click="toggleOpen"
    >
      {{ t('auth.voiceNotes.separateTalkers') }}
    </button>
    <Teleport to="body">
      <div
        v-if="open"
        id="vn-speaker-edit-panel"
        ref="panelRef"
        class="vn-speaker-edit__panel"
        role="group"
        :aria-label="t('auth.voiceNotes.separateTalkers')"
        :style="panelStyle"
      >
        <div
          v-for="speakerId in voiceNotes.speakerIds"
          :key="speakerId"
          class="vn-speaker-edit__row"
        >
          <span class="vn-speaker-edit__index">{{
            speakerAvatarGlyph(voiceNotes.speakerNames[speakerId] ?? '', speakerId + 1)
          }}</span>
          <input
            class="vn-speaker-edit__input"
            type="text"
            maxlength="32"
            :value="voiceNotes.speakerNames[speakerId] ?? ''"
            :placeholder="placeholderFor(speakerId)"
            @input="onRename(speakerId, $event)"
          />
          <div class="vn-speaker-edit__actions">
            <button
              type="button"
              class="vn-speaker-edit__icon"
              :aria-label="t('auth.voiceNotes.mergeTalker')"
              :aria-expanded="mergeForId === speakerId"
              :disabled="mergeTargets(speakerId).length === 0"
              @click="toggleMergeMenu(speakerId, $event)"
            >
              <EllipsisVertical
                :size="14"
                :stroke-width="2.2"
              />
            </button>
            <button
              type="button"
              class="vn-speaker-edit__icon vn-speaker-edit__icon--danger"
              :aria-label="t('auth.voiceNotes.resetTalker')"
              :disabled="!canReset(speakerId)"
              @click="onReset(speakerId)"
            >
              <Trash2
                :size="14"
                :stroke-width="2.2"
              />
            </button>
          </div>
        </div>
      </div>
    </Teleport>
    <Teleport to="body">
      <div
        v-if="mergeForId !== null"
        ref="menuRef"
        class="vn-speaker-edit__menu"
        role="menu"
        :style="menuStyle"
      >
        <button
          v-for="targetId in openMergeTargets()"
          :key="targetId"
          type="button"
          class="vn-speaker-edit__menu-item"
          role="menuitem"
          @click="confirmOpenMerge(targetId)"
        >
          {{ t('auth.voiceNotes.mergeTalkerInto', { name: displayName(targetId) }) }}
        </button>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.vn-speaker-edit {
  position: relative;
}

.vn-speaker-edit__panel {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  box-sizing: border-box;
  width: 16.5rem;
  padding: 0.65rem 0.7rem;
  overflow-x: hidden;
  overflow-y: auto;
  border: 1px solid #e7e5e4;
  border-radius: 0.75rem;
  background: #ffffff;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
}

.vn-speaker-edit__row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.vn-speaker-edit__index {
  display: inline-flex;
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

.vn-speaker-edit__input {
  flex: 1;
  min-width: 0;
  height: 1.85rem;
  padding: 0 0.5rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.45rem;
  background: #fafaf9;
  color: #1c1917;
  font: inherit;
  font-size: 0.8125rem;
  outline: none;
}

.vn-speaker-edit__input:focus {
  border-color: #1c1917;
  background: #ffffff;
}

.vn-speaker-edit__actions {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.15rem;
  flex-shrink: 0;
}

.vn-speaker-edit__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.55rem;
  height: 1.55rem;
  padding: 0;
  border: 0;
  border-radius: 0.4rem;
  background: transparent;
  color: #57534e;
  cursor: pointer;
}

.vn-speaker-edit__icon:hover:not(:disabled) {
  background: #f5f5f4;
  color: #1c1917;
}

.vn-speaker-edit__icon:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.vn-speaker-edit__icon--danger:hover:not(:disabled) {
  background: #fef2f2;
  color: #b91c1c;
}

.vn-speaker-edit__menu {
  box-sizing: border-box;
  min-width: 8.5rem;
  max-width: 16rem;
  padding: 0.25rem;
  overflow-x: hidden;
  overflow-y: auto;
  border: 1px solid #e7e5e4;
  border-radius: 0.55rem;
  background: #ffffff;
  box-shadow: 0 8px 16px -6px rgba(0, 0, 0, 0.12);
}

.vn-speaker-edit__menu-item {
  display: block;
  width: 100%;
  padding: 0.35rem 0.5rem;
  border: 0;
  border-radius: 0.35rem;
  background: transparent;
  color: #1c1917;
  font: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.vn-speaker-edit__menu-item:hover {
  background: #f5f5f4;
}

.vn-swiss-opt {
  display: inline-flex;
  align-items: center;
  justify-content: center;
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
}

.vn-swiss-opt:disabled {
  opacity: 0.35;
}

.vn-swiss-opt:active:not(:disabled) {
  background: #f5f5f4;
}

.vn-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  min-height: 2.15rem;
  padding: 0 1rem;
  border-radius: 9999px;
  border: 1px solid #1c1917;
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  background: transparent;
  color: #1c1917;
}

.vn-pill:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.vn-pill--ghost:hover:not(:disabled) {
  background: #f5f5f4;
}
</style>
