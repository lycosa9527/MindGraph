<script setup lang="ts">
/**
 * Floating voice-notes recorder FAB — Kitty-style, draggable.
 * Left-click cycles idle → recording → pause → recording…
 * Right-click: Start / Pause / Stop / View transcript / Jump / Exit.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { useDraggable, useWindowSize } from '@vueuse/core'
import { storeToRefs } from 'pinia'

import { Mic } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useVoiceNotesStore } from '@/stores/voiceNotes'

const FAB_SIZE = 56
const FAB_PAD = 16

const { t } = useLanguage()
const voiceNotes = useVoiceNotesStore()
const { enabled, recording, paused, connecting, bootstrapping, stopping, inputLevel } =
  storeToRefs(voiceNotes)

const fabRef = ref<HTMLElement | null>(null)
const menuOpen = ref(false)
const menuX = ref(0)
const menuY = ref(0)
const menuOpenUp = ref(false)
const menuOpenLeft = ref(false)
const suppressClick = ref(false)
const hasDragged = ref(false)

/** Approx menu size before measure — 6 items + padding. */
const MENU_EST_H = 280
const MENU_EST_W = 190
const MENU_PAD = 8

/** Relative bar gains — center louder for a classic volume wave. */
const WAVE_BAR_WEIGHTS = [0.45, 0.75, 1, 0.75, 0.45] as const

const { width: winW, height: winH } = useWindowSize()

const defaultPos = computed(() => ({
  x: Math.max(FAB_PAD, winW.value - FAB_SIZE - FAB_PAD),
  y: Math.max(FAB_PAD, winH.value - FAB_SIZE - FAB_PAD),
}))

const { x, y, isDragging } = useDraggable(fabRef, {
  initialValue: defaultPos,
  onStart() {
    suppressClick.value = false
    menuOpen.value = false
  },
  onMove(pos) {
    suppressClick.value = true
    hasDragged.value = true
    pos.x = Math.max(FAB_PAD, Math.min(winW.value - FAB_SIZE - FAB_PAD, pos.x))
    pos.y = Math.max(FAB_PAD, Math.min(winH.value - FAB_SIZE - FAB_PAD, pos.y))
  },
})

const fabStyle = computed(() => {
  const level =
    recording.value && !paused.value ? Math.min(1, Math.max(0, inputLevel.value)) : 0
  const base =
    !hasDragged.value
      ? {
          position: 'fixed' as const,
          right: `${FAB_PAD}px`,
          bottom: `${FAB_PAD}px`,
          left: 'auto',
          top: 'auto',
          width: `${FAB_SIZE}px`,
          height: `${FAB_SIZE}px`,
        }
      : {
          position: 'fixed' as const,
          left: `${x.value}px`,
          top: `${y.value}px`,
          right: 'auto',
          bottom: 'auto',
          width: `${FAB_SIZE}px`,
          height: `${FAB_SIZE}px`,
        }
  return {
    ...base,
    '--vn-level': String(level),
  }
})

const showVolumeWave = computed(() => recording.value && !paused.value)

const waveBarHeights = computed(() => {
  const level = Math.min(1, Math.max(0, inputLevel.value))
  // Soft floor so quiet recording still reads as live.
  const energy = 0.12 + level * 0.88
  return WAVE_BAR_WEIGHTS.map((weight) => {
    const pct = 16 + energy * weight * 76
    return `${Math.round(pct)}%`
  })
})

const statusClass = computed(() => {
  if (recording.value && !paused.value) return 'voice-notes-fab--recording'
  if (paused.value) return 'voice-notes-fab--paused'
  if (connecting.value || bootstrapping.value) return 'voice-notes-fab--connecting'
  return ''
})

const canStart = computed(
  () => !recording.value && !paused.value && !connecting.value && !stopping.value
)
const canPause = computed(() => recording.value && !paused.value && !stopping.value)
const canStop = computed(() => (recording.value || paused.value) && !stopping.value)

const fabTitle = computed(() => {
  if (paused.value) return t('auth.voiceNotes.resume')
  if (recording.value) return t('auth.voiceNotes.pause')
  return t('auth.voiceNotes.start')
})

const menuStyle = computed(() => {
  if (menuOpenUp.value && menuOpenLeft.value) {
    return {
      left: 'auto',
      top: 'auto',
      right: `${Math.max(MENU_PAD, winW.value - menuX.value)}px`,
      bottom: `${Math.max(MENU_PAD, winH.value - menuY.value)}px`,
    }
  }
  if (menuOpenUp.value) {
    return {
      left: `${Math.min(menuX.value, winW.value - MENU_EST_W - MENU_PAD)}px`,
      top: 'auto',
      right: 'auto',
      bottom: `${Math.max(MENU_PAD, winH.value - menuY.value)}px`,
    }
  }
  if (menuOpenLeft.value) {
    return {
      left: 'auto',
      top: `${Math.min(menuY.value, winH.value - MENU_EST_H - MENU_PAD)}px`,
      right: `${Math.max(MENU_PAD, winW.value - menuX.value)}px`,
      bottom: 'auto',
    }
  }
  return {
    left: `${menuX.value}px`,
    top: `${menuY.value}px`,
    right: 'auto',
    bottom: 'auto',
  }
})

function syncDefaultDragOrigin(): void {
  x.value = defaultPos.value.x
  y.value = defaultPos.value.y
}

/** Idle → start; recording → pause; paused → resume. */
function cycleRecordState(): void {
  if (connecting.value || stopping.value) return
  if (!recording.value && !paused.value) {
    void voiceNotes.startRecording()
    return
  }
  if (recording.value && !paused.value) {
    voiceNotes.pauseRecording()
    return
  }
  if (paused.value) {
    voiceNotes.resumeRecording()
  }
}

function onFabClick(): void {
  if (suppressClick.value || isDragging.value) {
    suppressClick.value = false
    return
  }
  menuOpen.value = false
  cycleRecordState()
}

function onFabContextMenu(event: MouseEvent): void {
  event.preventDefault()
  event.stopPropagation()
  if (isDragging.value) return
  menuX.value = event.clientX
  menuY.value = event.clientY
  // Open upward / left when near viewport edges so the menu stays on screen.
  menuOpenUp.value = winH.value - event.clientY < MENU_EST_H
  menuOpenLeft.value = winW.value - event.clientX < MENU_EST_W
  menuOpen.value = true
}

function closeMenu(): void {
  menuOpen.value = false
}

function onStart(): void {
  void voiceNotes.startRecording()
  closeMenu()
}

function onPause(): void {
  voiceNotes.pauseRecording()
  closeMenu()
}

function onStop(): void {
  void voiceNotes.stopRecording()
  closeMenu()
}

function onViewTranscript(): void {
  voiceNotes.openModal()
  closeMenu()
}

function onJump(): void {
  void voiceNotes.jumpToMindmap()
  closeMenu()
}

function onExit(): void {
  void voiceNotes.exit()
  closeMenu()
}

function onDocClick(): void {
  if (menuOpen.value) closeMenu()
}

watch(enabled, (isOn) => {
  if (isOn) {
    hasDragged.value = false
    syncDefaultDragOrigin()
  } else {
    menuOpen.value = false
  }
})

onMounted(() => {
  syncDefaultDragOrigin()
  document.addEventListener('click', onDocClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
})
</script>

<template>
  <Teleport to="body">
    <button
      v-show="enabled"
      ref="fabRef"
      type="button"
      class="voice-notes-fab"
      :class="[statusClass, { 'voice-notes-fab--dragging': isDragging }]"
      :style="fabStyle"
      :aria-label="fabTitle"
      :title="fabTitle"
      @click.stop="onFabClick"
      @contextmenu="onFabContextMenu"
    >
      <span
        v-if="showVolumeWave"
        class="voice-notes-fab__wave"
        aria-hidden="true"
      >
        <span
          v-for="(height, index) in waveBarHeights"
          :key="index"
          class="voice-notes-fab__bar"
          :style="{ height }"
        />
      </span>
      <Mic
        v-else
        class="w-5 h-5"
      />
    </button>

    <div
      v-if="enabled && menuOpen"
      class="voice-notes-ctx"
      :class="{
        'voice-notes-ctx--up': menuOpenUp,
        'voice-notes-ctx--left': menuOpenLeft,
      }"
      :style="menuStyle"
      role="menu"
      @click.stop
    >
      <button
        type="button"
        class="voice-notes-ctx__item"
        role="menuitem"
        :disabled="!canStart"
        @click="onStart"
      >
        {{ t('auth.voiceNotes.start') }}
      </button>
      <button
        type="button"
        class="voice-notes-ctx__item"
        role="menuitem"
        :disabled="!canPause"
        @click="onPause"
      >
        {{ t('auth.voiceNotes.pause') }}
      </button>
      <button
        type="button"
        class="voice-notes-ctx__item"
        role="menuitem"
        :disabled="!canStop"
        @click="onStop"
      >
        {{ t('auth.voiceNotes.stop') }}
      </button>
      <button
        type="button"
        class="voice-notes-ctx__item"
        role="menuitem"
        @click="onViewTranscript"
      >
        {{ t('auth.voiceNotes.viewTranscript') }}
      </button>
      <button
        type="button"
        class="voice-notes-ctx__item"
        role="menuitem"
        :disabled="bootstrapping"
        @click="onJump"
      >
        {{ t('auth.voiceNotes.jumpToMindmap') }}
      </button>
      <button
        type="button"
        class="voice-notes-ctx__item voice-notes-ctx__item--danger"
        role="menuitem"
        @click="onExit"
      >
        {{ t('auth.voiceNotes.exit') }}
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.voice-notes-fab {
  position: relative;
  z-index: 10050;
  border-radius: 9999px;
  border: 2px solid #d6d3d1;
  background: #ffffff;
  color: #1c1917;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.16);
  cursor: grab;
  touch-action: none;
  user-select: none;
  overflow: visible;
  transition:
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.voice-notes-fab:hover {
  background: #f5f5f4;
}

.voice-notes-fab--dragging {
  cursor: grabbing;
  box-shadow: 0 12px 28px rgba(28, 25, 23, 0.22);
  transition: none;
}

.voice-notes-fab--recording {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #b91c1c;
}

.voice-notes-fab--recording::before {
  content: '';
  position: absolute;
  inset: -5px;
  border-radius: 9999px;
  border: 2px solid rgba(185, 28, 28, 0.28);
  pointer-events: none;
  transform: scale(calc(1 + var(--vn-level, 0) * 0.42));
  opacity: calc(0.25 + var(--vn-level, 0) * 0.75);
  transition:
    transform 0.08s linear,
    opacity 0.08s linear;
}

.voice-notes-fab__wave {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2.5px;
  height: 22px;
  width: 22px;
}

.voice-notes-fab__bar {
  display: block;
  width: 2.5px;
  min-height: 14%;
  border-radius: 9999px;
  background: currentColor;
  transition: height 0.08s linear;
}

.voice-notes-fab--paused {
  background: #fffbeb;
  border-color: #fcd34d;
  color: #b45309;
}

.voice-notes-fab--connecting {
  opacity: 0.75;
}

.voice-notes-ctx {
  position: fixed;
  z-index: 10060;
  min-width: 11rem;
  padding: 0.35rem;
  border-radius: 0.5rem;
  border: 1px solid #e7e5e4;
  background: #fafaf9;
  box-shadow: 0 12px 32px rgba(28, 25, 23, 0.14);
}

.voice-notes-ctx:not(.voice-notes-ctx--up):not(.voice-notes-ctx--left) {
  transform: translate(4px, 4px);
}

.voice-notes-ctx--up:not(.voice-notes-ctx--left) {
  transform: translate(4px, -4px);
}

.voice-notes-ctx--left:not(.voice-notes-ctx--up) {
  transform: translate(-4px, 4px);
}

.voice-notes-ctx--up.voice-notes-ctx--left {
  transform: translate(-4px, -4px);
}

.voice-notes-ctx__item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 0.45rem 0.65rem;
  border: 0;
  border-radius: 0.35rem;
  background: transparent;
  color: #1c1917;
  font-size: 0.875rem;
  cursor: pointer;
}

.voice-notes-ctx__item:hover:not(:disabled) {
  background: #f5f5f4;
}

.voice-notes-ctx__item:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.voice-notes-ctx__item--danger {
  color: #b91c1c;
}
</style>
