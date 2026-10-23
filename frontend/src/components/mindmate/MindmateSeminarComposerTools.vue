<script setup lang="ts">
/**
 * Seminar composer chips, plus a menu for the school agent and plugins.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { ElPopover } from 'element-plus'

import {
  Bot,
  ChevronLeft,
  ChevronRight,
  Mic,
  Plus,
  Puzzle,
  ScrollText,
  Upload,
  Waypoints,
} from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'
import { seminarSpectator } from '@/composables/mindmate/mindmateSeminarChrome'
import { SEMINAR_BACKGROUND_FILE_ACCEPT } from '@/utils/mindmateSeminarFolder'

defineProps<{
  agentName: string
}>()

const emit = defineEmits<{
  (e: 'mindgraph'): void
  (e: 'voice'): void
  (e: 'summary'): void
  (e: 'agent'): void
  (e: 'upload', files: File[]): void
  (e: 'mindmateTag', active: boolean): void
  (e: 'mindgraphTag', active: boolean): void
}>()

const { t } = useLanguage()
const menuOpen = ref(false)
const flyout = ref<'agents' | 'plugins' | ''>('')
const fileInput = ref<HTMLInputElement | null>(null)
const trackEl = ref<HTMLElement | null>(null)
const canScrollLeft = ref(false)
const canScrollRight = ref(false)
let trackObserver: ResizeObserver | null = null

const plugins = [
  { id: 'mindgraph', labelKey: 'mindmate.composer.mindgraph', event: 'mindgraph' },
  { id: 'voice', labelKey: 'mindmate.composer.voice', event: 'voice' },
  { id: 'summary', labelKey: 'mindmate.composer.summary', event: 'summary' },
] as const

function closeMenu(): void {
  menuOpen.value = false
  flyout.value = ''
}

function pickAgent(): void {
  closeMenu()
  pinMindmate()
}

function pinMindmate(): void {
  emit('mindmateTag', true)
}

function pinMindgraph(): void {
  emit('mindgraphTag', true)
}

function pickPlugin(event: (typeof plugins)[number]['event']): void {
  closeMenu()
  if (event === 'mindgraph') {
    pinMindgraph()
    return
  }
  if (event === 'voice') {
    emit('voice')
    return
  }
  if (seminarSpectator.value) {
    return
  }
  emit('summary')
}

function openFilePicker(): void {
  closeMenu()
  fileInput.value?.click()
}

function onPickFiles(event: Event): void {
  const input = event.target as HTMLInputElement
  const picked = input.files ? Array.from(input.files) : []
  input.value = ''
  if (picked.length > 0) {
    emit('upload', picked)
  }
}

function measureTrack(): void {
  const track = trackEl.value
  if (!track) {
    canScrollLeft.value = false
    canScrollRight.value = false
    return
  }
  const maxScroll = track.scrollWidth - track.clientWidth
  canScrollLeft.value = track.scrollLeft > 2
  canScrollRight.value = maxScroll - track.scrollLeft > 2
}

function scrollTrack(direction: -1 | 1): void {
  const track = trackEl.value
  if (!track) {
    return
  }
  track.scrollBy({ left: direction * Math.max(120, track.clientWidth * 0.6), behavior: 'smooth' })
}

onMounted(() => {
  measureTrack()
  if (typeof ResizeObserver === 'undefined' || !trackEl.value) {
    return
  }
  trackObserver = new ResizeObserver(() => {
    measureTrack()
  })
  trackObserver.observe(trackEl.value)
})

onBeforeUnmount(() => {
  trackObserver?.disconnect()
  trackObserver = null
})
</script>

<template>
  <div
    class="mm-seminar-tools"
    role="toolbar"
  >
    <input
      ref="fileInput"
      class="mm-seminar-tools__file"
      type="file"
      multiple
      :accept="SEMINAR_BACKGROUND_FILE_ACCEPT"
      @change="onPickFiles"
    />
    <ElPopover
      v-model:visible="menuOpen"
      trigger="click"
      placement="top-start"
      :width="220"
      :show-arrow="false"
      popper-class="mm-seminar-plus-popper"
      @hide="flyout = ''"
    >
      <template #reference>
        <button
          type="button"
          class="mm-seminar-tools__plus"
          :aria-label="t('mindmate.composer.more')"
          :aria-expanded="menuOpen"
        >
          <Plus
            :size="16"
            aria-hidden="true"
          />
        </button>
      </template>
      <div
        class="mm-plus-menu"
        role="menu"
      >
        <button
          type="button"
          class="mm-plus-menu__row mm-plus-menu__row--button"
          role="menuitem"
          @click="openFilePicker"
        >
          <Upload
            :size="16"
            aria-hidden="true"
          />
          <span class="mm-plus-menu__label">
            <I18nText
              k="mindmate.folder.upload"
              dense
            />
          </span>
        </button>
        <div
          class="mm-plus-menu__row"
          @mouseenter="flyout = 'agents'"
          @click="flyout = 'agents'"
        >
          <Bot
            :size="16"
            aria-hidden="true"
          />
          <span class="mm-plus-menu__label">
            <I18nText
              k="mindmate.composer.agents"
              dense
            />
          </span>
          <ChevronRight
            :size="14"
            class="mm-plus-menu__chevron"
            aria-hidden="true"
          />
          <div
            v-if="flyout === 'agents'"
            class="mm-plus-menu__flyout"
            role="menu"
          >
            <button
              type="button"
              class="mm-plus-menu__choice"
              role="menuitem"
              @click.stop="pickAgent"
            >
              {{ agentName }}
            </button>
          </div>
        </div>
        <div
          class="mm-plus-menu__row"
          @mouseenter="flyout = 'plugins'"
          @click="flyout = 'plugins'"
        >
          <Puzzle
            :size="16"
            aria-hidden="true"
          />
          <span class="mm-plus-menu__label">
            <I18nText
              k="mindmate.composer.plugins"
              dense
            />
          </span>
          <ChevronRight
            :size="14"
            class="mm-plus-menu__chevron"
            aria-hidden="true"
          />
          <div
            v-if="flyout === 'plugins'"
            class="mm-plus-menu__flyout"
            role="menu"
          >
            <button
              v-for="plugin in plugins.filter((item) => item.id !== 'summary' || !seminarSpectator)"
              :key="plugin.id"
              type="button"
              class="mm-plus-menu__choice"
              role="menuitem"
              @click.stop="pickPlugin(plugin.event)"
            >
              <I18nText
                :k="plugin.labelKey"
                dense
              />
            </button>
          </div>
        </div>
      </div>
    </ElPopover>
    <button
      v-if="canScrollLeft"
      type="button"
      class="mm-seminar-tools__nudge"
      :aria-label="t('mindmate.composer.scrollMore')"
      @click="scrollTrack(-1)"
    >
      <ChevronLeft
        :size="16"
        aria-hidden="true"
      />
    </button>
    <div
      ref="trackEl"
      class="mm-seminar-tools__track"
      @scroll="measureTrack"
    >
      <button
        type="button"
        class="mm-seminar-tools__chip mm-seminar-tools__chip--mindmate"
        @click="pinMindmate"
      >
        <span>@{{ agentName }}</span>
      </button>
      <button
        type="button"
        class="mm-seminar-tools__chip"
        @click="pinMindgraph"
      >
        <Waypoints
          :size="14"
          aria-hidden="true"
        />
        <I18nText
          k="mindmate.composer.mindgraph"
          dense
        />
      </button>
      <button
        type="button"
        class="mm-seminar-tools__chip"
        @click="emit('voice')"
      >
        <Mic
          :size="14"
          aria-hidden="true"
        />
        <I18nText
          k="mindmate.composer.voice"
          dense
        />
      </button>
      <button
        v-if="!seminarSpectator"
        type="button"
        class="mm-seminar-tools__chip"
        @click="emit('summary')"
      >
        <ScrollText
          :size="14"
          aria-hidden="true"
        />
        <I18nText
          k="mindmate.composer.summary"
          dense
        />
      </button>
    </div>
    <button
      v-if="canScrollRight"
      type="button"
      class="mm-seminar-tools__nudge"
      :aria-label="t('mindmate.composer.scrollMore')"
      @click="scrollTrack(1)"
    >
      <ChevronRight
        :size="16"
        aria-hidden="true"
      />
    </button>
  </div>
</template>

<style scoped>
.mm-seminar-tools {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  width: 100%;
}

.mm-seminar-tools__file {
  display: none;
}

.mm-seminar-tools__track {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
  overflow-x: auto;
  scrollbar-width: none;
}

.mm-seminar-tools__track::-webkit-scrollbar {
  display: none;
}

.mm-seminar-tools__nudge {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 999px;
  background: #f5f5f4;
  color: #57534e;
  cursor: pointer;
}

.mm-seminar-tools__nudge:hover {
  background: #f5f3ff;
  color: #6d5efc;
}

.mm-seminar-tools__plus,
.mm-seminar-tools__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  height: 32px;
  border: 1px solid #e7e5e4;
  background: #fff;
  color: #44403c;
  cursor: pointer;
}

.mm-seminar-tools__plus {
  width: 32px;
  justify-content: center;
  border-radius: 999px;
  padding: 0;
}

.mm-seminar-tools__chip {
  padding: 0 10px;
  border-radius: 999px;
  font-size: 13px;
}

.mm-seminar-tools__plus:hover,
.mm-seminar-tools__chip:hover {
  background: #fafaf9;
  border-color: #d6d3d1;
}

.mm-seminar-tools__chip--mindmate {
  border-color: #ddd6fe;
  background: #f5f3ff;
  color: #6d28d9;
}

.mm-seminar-tools__chip--mindmate:hover {
  border-color: #c4b5fd;
  background: #ede9fe;
  color: #5b21b6;
}
</style>

<style>
.mm-seminar-plus-popper.el-popover.el-popper {
  padding: 6px;
  border-radius: 12px;
  border: 1px solid #eceae6;
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.12);
  overflow: visible;
}

.mm-plus-menu__row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 36px;
  padding: 0 8px 0 10px;
  border-radius: 8px;
  color: #1c1917;
  font-size: 14px;
  cursor: pointer;
}

.mm-plus-menu__row--button {
  width: 100%;
  border: none;
  background: transparent;
  font: inherit;
  text-align: left;
}

.mm-plus-menu__row:hover,
.mm-plus-menu__choice:hover {
  background: #f3f4f6;
}

.mm-plus-menu__label {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.mm-plus-menu__chevron {
  color: #a8a29e;
  flex-shrink: 0;
}

.mm-plus-menu__flyout {
  position: absolute;
  left: calc(100% + 8px);
  top: 0;
  min-width: 168px;
  padding: 6px;
  border-radius: 12px;
  border: 1px solid #eceae6;
  background: #fff;
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.12);
  z-index: 2;
}

.mm-plus-menu__choice {
  display: block;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #1c1917;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}
</style>
