<script setup lang="ts">
/**
 * ZoomControls - Bottom right zoom and view controls
 * Improved with Element Plus components and better styling
 */
import { computed, ref, watch } from 'vue'

import {
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElOption,
  ElSelect,
} from 'element-plus'

import { Hand, Maximize2, Minus, Play, Plus, Square, Users } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import { ZOOM } from '@/config/uiConfig'

const { t } = useLanguage()

const ZOOM_OPTIONS = [
  { label: '50%', value: 50 },
  { label: '75%', value: 75 },
  { label: '100%', value: 100 },
  { label: '125%', value: 125 },
] as const

const props = withDefaults(
  defineProps<{
    /** Canvas zoom (0.1-4) - when provided, display syncs with canvas */
    zoom?: number | null
    /** When true, presentation tools rail is open (Play shows active) */
    presentationRailOpen?: boolean
    /** Active workshop session code; presence shows the 'turn off' menu item */
    workshopCode?: string | null
    /** When true the user is a collab guest — hide the host-only collab button */
    isCollabGuest?: boolean
  }>(),
  { zoom: null, presentationRailOpen: false, workshopCode: null, isCollabGuest: false }
)

const zoomLevel = ref(100)
const isHandToolActive = ref(false)

const displayZoom = computed(() =>
  props.zoom != null ? Math.round(props.zoom * 100) : zoomLevel.value
)

const zoomOptions = computed(() => {
  const current = displayZoom.value
  const minPct = Math.round(ZOOM.MIN * 100)
  const maxPct = Math.round(ZOOM.MAX * 100)
  const hasExact = ZOOM_OPTIONS.some((opt) => opt.value === current)
  const options: Array<{ label: string; value: number }> = [...ZOOM_OPTIONS]
  if (!hasExact && current >= minPct && current <= maxPct) {
    options.push({ label: `${current}%`, value: current })
    options.sort((a, b) => a.value - b.value)
  }
  return options
})

const zoomSelectValue = computed({
  get: () => displayZoom.value,
  set: (value: number) => {
    zoomLevel.value = value
    if (value === 100) {
      emit('fitToScreen')
    } else {
      emit('zoomChange', value)
    }
  },
})

watch(
  () => props.zoom,
  (z) => {
    if (z != null) {
      zoomLevel.value = Math.round(z * 100)
    }
  },
  { immediate: true }
)

function handleZoomIn() {
  emit('zoomIn')
}

function handleZoomOut() {
  emit('zoomOut')
}

function handleZoomReset() {
  emit('fitToScreen')
}

function toggleHandTool() {
  isHandToolActive.value = !isHandToolActive.value
  emit('handToolToggle', isHandToolActive.value)
}

function handlePresentation() {
  emit('startPresentation')
}

const emit = defineEmits<{
  (e: 'zoomChange', level: number): void
  (e: 'zoomIn'): void
  (e: 'zoomOut'): void
  (e: 'fitToScreen'): void
  (e: 'handToolToggle', active: boolean): void
  (e: 'startPresentation'): void
  (e: 'openCollab', mode: 'organization' | 'network' | 'stop'): void
}>()

defineExpose({
  zoomLevel,
  isHandToolActive,
})
</script>

<template>
  <div class="zoom-controls z-20">
    <div class="rounded-xl p-1.5 flex items-center gap-0.5">
      <!-- Hand tool -->
      <ElTooltip
        :content="t('canvas.zoomControls.hand')"
        placement="top"
      >
        <ElButton
          text
          size="small"
          :class="['zoom-btn', isHandToolActive ? 'active' : '']"
          @click="toggleHandTool"
        >
          <Hand class="w-4 h-4" />
        </ElButton>
      </ElTooltip>

      <div class="divider" />

      <!-- Zoom out -->
      <ElTooltip
        :content="t('editor.zoomOut')"
        placement="top"
      >
        <ElButton
          text
          size="small"
          class="zoom-btn"
          @click="handleZoomOut"
        >
          <Minus class="w-4 h-4" />
        </ElButton>
      </ElTooltip>

      <!-- Zoom level dropdown -->
      <ElSelect
        v-model="zoomSelectValue"
        size="small"
        class="zoom-select"
        :teleported="false"
      >
        <ElOption
          v-for="opt in zoomOptions"
          :key="`zoom-${opt.value}`"
          :label="opt.label"
          :value="opt.value"
        />
      </ElSelect>

      <!-- Zoom in -->
      <ElTooltip
        :content="t('editor.zoomIn')"
        placement="top"
      >
        <ElButton
          text
          size="small"
          class="zoom-btn"
          @click="handleZoomIn"
        >
          <Plus class="w-4 h-4" />
        </ElButton>
      </ElTooltip>

      <div class="divider" />

      <!-- Fit to screen -->
      <ElTooltip
        :content="t('canvas.zoomControls.fitCanvas')"
        placement="top"
      >
        <ElButton
          text
          size="small"
          class="zoom-btn"
          @click="handleZoomReset"
        >
          <Maximize2 class="w-4 h-4" />
        </ElButton>
      </ElTooltip>

      <div class="divider" />

      <!-- Toggle presentation tools rail (right) -->
      <ElTooltip
        :content="
          props.presentationRailOpen
            ? t('canvas.zoomControls.hidePresentationTools')
            : t('canvas.zoomControls.showPresentationTools')
        "
        placement="top"
      >
        <ElButton
          text
          size="small"
          :class="['zoom-btn', 'presentation', { active: props.presentationRailOpen }]"
          @click="handlePresentation"
        >
          <Square
            v-if="props.presentationRailOpen"
            class="w-4 h-4"
          />
          <Play
            v-else
            class="w-4 h-4"
          />
        </ElButton>
      </ElTooltip>

      <template v-if="!props.isCollabGuest">
        <div class="divider" />

        <!-- Online collaboration trigger (host only) -->
        <ElDropdown
          trigger="click"
          popper-class="canvas-collab-dropdown-popper"
          @command="(cmd: string) => emit('openCollab', cmd as 'organization' | 'network' | 'stop')"
        >
          <!-- Wrapper carries the traveling-ring animation when a session is live -->
          <div
            :class="['collab-btn-wrap', { 'collab-active': props.workshopCode }]"
            :title="t('canvas.zoomControls.collaborate')"
          >
            <ElButton
              text
              size="small"
              class="zoom-btn collab"
              :aria-label="t('canvas.zoomControls.collaborate')"
            >
              <Users class="w-4 h-4" />
            </ElButton>
          </div>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem command="organization">
                {{ t('canvas.zoomControls.collabWithinOrg') }}
              </ElDropdownItem>
              <ElDropdownItem command="network">
                {{ t('canvas.zoomControls.collabCrossOrg') }}
              </ElDropdownItem>
              <ElDropdownItem
                v-if="props.workshopCode"
                divided
                command="stop"
              >
                {{ t('canvas.zoomControls.collabTurnOff') }}
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* Divider between button groups */
.divider {
  height: 20px;
  width: 1px;
  background-color: #e5e7eb;
  margin: 0 4px;
}

/* Zoom level dropdown */
.zoom-select {
  min-width: 72px;
  font-size: 12px;
}

:deep(.zoom-select .el-input__wrapper) {
  padding: 4px 8px;
  box-shadow: none;
  background-color: transparent;
}

:deep(.zoom-select .el-input__wrapper:hover) {
  background-color: #e5e7eb;
}

:deep(.zoom-select.is-focus .el-input__wrapper) {
  background-color: #e5e7eb;
}

/* Button styling */
:deep(.zoom-btn) {
  padding: 6px !important;
  margin: 0 !important;
  min-height: auto !important;
  height: auto !important;
  border-radius: 6px !important;
  border: none !important;
  color: #6b7280 !important;
  transition: all 0.15s ease !important;
}

:deep(.zoom-btn:hover) {
  background-color: #e5e7eb !important;
  color: #374151 !important;
}

:deep(.zoom-btn:active) {
  background-color: #d1d5db !important;
}

/* Active hand tool state */
:deep(.zoom-btn.active) {
  background-color: #dbeafe !important;
  color: #2563eb !important;
}

:deep(.zoom-btn.active:hover) {
  background-color: #bfdbfe !important;
}

/* Presentation button - subtle accent */
:deep(.zoom-btn.presentation) {
  color: #059669 !important;
}

:deep(.zoom-btn.presentation:hover) {
  background-color: #d1fae5 !important;
  color: #047857 !important;
}

:deep(.zoom-btn.presentation.active) {
  background-color: #d1fae5 !important;
  color: #047857 !important;
}

/* Collab buddy button - indigo accent */
:deep(.zoom-btn.collab) {
  color: #4f46e5 !important;
}

:deep(.zoom-btn.collab:hover) {
  background-color: #ede9fe !important;
  color: #4338ca !important;
}

/* Dark mode */
:deep(.dark) .divider {
  background-color: #4b5563;
}

:deep(.dark .zoom-select .el-input__wrapper) {
  background-color: transparent;
}

:deep(.dark .zoom-select .el-input__wrapper:hover),
:deep(.dark .zoom-select.is-focus .el-input__wrapper) {
  background-color: #4b5563;
}

:deep(.dark .zoom-btn) {
  color: #9ca3af !important;
}

:deep(.dark .zoom-btn:hover) {
  background-color: #4b5563 !important;
  color: #f3f4f6 !important;
}

:deep(.dark .zoom-btn:active) {
  background-color: #374151 !important;
}

:deep(.dark .zoom-btn.active) {
  background-color: #1e3a5f !important;
  color: #60a5fa !important;
}

:deep(.dark .zoom-btn.presentation) {
  color: #34d399 !important;
}

:deep(.dark .zoom-btn.presentation:hover) {
  background-color: #064e3b !important;
  color: #6ee7b7 !important;
}

:deep(.dark .zoom-btn.presentation.active) {
  background-color: #064e3b !important;
  color: #6ee7b7 !important;
}

:deep(.dark .zoom-btn.collab) {
  color: #818cf8 !important;
}

:deep(.dark .zoom-btn.collab:hover) {
  background-color: #1e1b4b !important;
  color: #a5b4fc !important;
}

/* ── Collab active: traveling conic ring ─────────────────────────────────────── */

.collab-btn-wrap {
  position: relative;
  border-radius: 8px;
  display: inline-flex;
}

/* Traveling ring only while a session is live */
.collab-btn-wrap.collab-active::before {
  content: '';
  position: absolute;
  /* Extend 2 px outside the button on every side */
  inset: -2px;
  border-radius: 9px;
  padding: 2px;
  --collab-angle: 0deg;
  background: conic-gradient(
    from var(--collab-angle) at 50% 50%,
    #059669 0deg,
    #10b981 60deg,
    #34d399 120deg,
    #6ee7b7 180deg,
    #34d399 240deg,
    #10b981 300deg,
    #059669 360deg
  );
  /* Mask: keep only the padding band (the ring), hide the centre */
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: collab-ring-travel 2s linear infinite;
  pointer-events: none;
}

@keyframes collab-ring-travel {
  to {
    --collab-angle: 360deg;
  }
}
</style>

<style>
/* ── Swiss design for the canvas collab dropdown (teleported, must be global) ── */
.canvas-collab-dropdown-popper.el-popper {
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden;
}

.canvas-collab-dropdown-popper .el-dropdown-menu {
  padding: 0;
  border: none;
  background: transparent;
}

.canvas-collab-dropdown-popper .el-dropdown-menu__item {
  display: flex;
  align-items: center;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  border-radius: 6px;
  line-height: 1.4;
  letter-spacing: 0.01em;
  transition:
    background 0.12s,
    color 0.12s;
}

.canvas-collab-dropdown-popper .el-dropdown-menu__item:hover,
.canvas-collab-dropdown-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4;
  color: #1c1917;
}

.canvas-collab-dropdown-popper .el-dropdown-menu__item:active {
  background: #e7e5e4;
}

/* Stop session item — subtle red tint */
.canvas-collab-dropdown-popper .el-dropdown-menu__item.is-divided {
  color: #dc2626;
  border-top: 1px solid #f3f4f6;
  margin-top: 2px;
  padding-top: 10px;
}

.canvas-collab-dropdown-popper .el-dropdown-menu__item.is-divided:hover {
  background: #fef2f2;
  color: #b91c1c;
}
</style>
