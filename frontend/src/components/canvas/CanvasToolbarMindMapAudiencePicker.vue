<script setup lang="ts">
/**
 * Mind-map toolbar「专业内容」picker — extracted from CanvasToolbarMindMap.
 */
import { type Component, computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { ElPopover } from 'element-plus'

import {
  Award,
  BookOpen,
  Briefcase,
  Check,
  ChevronDown,
  GraduationCap,
  Landmark,
  School,
  Sparkles,
  X,
} from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  AI_CONTENT_LEVEL_COLORS,
  AI_CONTENT_LEVEL_IDS,
  type AiContentLevelId,
  DEFAULT_AI_CONTENT_LEVEL,
} from '@/config/aiContentLevels'
import { useAiContentLevelStore, useDiagramStore, useSavedDiagramsStore } from '@/stores'

const AI_CONTENT_LEVEL_ICONS: Record<AiContentLevelId, Component> = {
  general: Sparkles,
  primary: School,
  junior: BookOpen,
  senior: GraduationCap,
  university: Landmark,
  adult: Briefcase,
  expert: Award,
}

const props = withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const savedDiagramsStore = useSavedDiagramsStore()
const aiContentLevelStore = useAiContentLevelStore()
const {
  level: proContentLevel,
  userSet: proContentUserSet,
  showFirstRunGuide,
} = storeToRefs(aiContentLevelStore)

const proContentPanelOpen = ref(false)
const proContentGuideReady = ref(false)
const proContentAnchor = ref<HTMLElement | null>(null)
const proContentAnchorRect = ref<DOMRect | null>(null)

const proContentLevelOptions = computed(() =>
  AI_CONTENT_LEVEL_IDS.map((id) => ({
    id,
    title: t(`canvas.toolbar.professionalContent.level.${id}.title`),
    description: t(`canvas.toolbar.professionalContent.level.${id}.description`),
    color: AI_CONTENT_LEVEL_COLORS[id],
    icon: AI_CONTENT_LEVEL_ICONS[id],
  }))
)

const proContentActiveOption = computed(
  () =>
    proContentLevelOptions.value.find((option) => option.id === proContentLevel.value) ??
    proContentLevelOptions.value[0]
)

const showProContentHintLabel = computed(() => !props.compact && !proContentUserSet.value)

const proContentButtonTitle = computed(
  () => `${t('canvas.toolbar.professionalContent.label')} · ${proContentActiveOption.value.title}`
)

const showProContentGuide = computed(
  () =>
    showFirstRunGuide.value &&
    proContentGuideReady.value &&
    !diagramStore.collabSessionActive &&
    !proContentPanelOpen.value
)

const proContentGuideStyle = computed(() => {
  const rect = proContentAnchorRect.value
  if (!rect) {
    return {
      top: '56px',
      left: '50%',
      transform: 'translateX(-50%)',
    }
  }
  const viewportWidth = typeof window === 'undefined' ? 304 : window.innerWidth
  const guideWidth = Math.min(280, viewportWidth - 24)
  const halfWidth = guideWidth / 2
  const anchorCenter = rect.left + rect.width / 2
  const clampedCenter = Math.max(
    halfWidth + 12,
    Math.min(viewportWidth - halfWidth - 12, anchorCenter)
  )
  return {
    top: `${rect.bottom + 10}px`,
    left: `${clampedCenter}px`,
    transform: 'translateX(-50%)',
  }
})

let proContentGuideTimer: number | undefined
let proContentGuideRaf = 0

function updateProContentAnchorRect(): void {
  proContentAnchorRect.value = proContentAnchor.value?.getBoundingClientRect() ?? null
}

function scheduleProContentAnchorUpdate(): void {
  cancelAnimationFrame(proContentGuideRaf)
  proContentGuideRaf = requestAnimationFrame(updateProContentAnchorRect)
}

function bindProContentGuideListeners(): void {
  window.addEventListener('resize', scheduleProContentAnchorUpdate)
  window.addEventListener('scroll', scheduleProContentAnchorUpdate, true)
}

function unbindProContentGuideListeners(): void {
  window.removeEventListener('resize', scheduleProContentAnchorUpdate)
  window.removeEventListener('scroll', scheduleProContentAnchorUpdate, true)
  cancelAnimationFrame(proContentGuideRaf)
}

function dismissProContentGuide(): void {
  aiContentLevelStore.dismissGuide()
  proContentGuideReady.value = false
}

function openProContentFromGuide(): void {
  updateProContentAnchorRect()
  dismissProContentGuide()
  void nextTick(() => {
    proContentPanelOpen.value = true
  })
}

watch(showProContentGuide, (visible) => {
  if (visible) {
    bindProContentGuideListeners()
    scheduleProContentAnchorUpdate()
    return
  }
  unbindProContentGuideListeners()
})

watch(proContentPanelOpen, (open) => {
  if (open && showFirstRunGuide.value) {
    aiContentLevelStore.dismissGuide()
  }
})

onMounted(() => {
  if (!showFirstRunGuide.value || diagramStore.collabSessionActive) return
  proContentGuideTimer = window.setTimeout(() => {
    updateProContentAnchorRect()
    if (proContentAnchor.value) {
      proContentGuideReady.value = true
    }
  }, 700)
})

onBeforeUnmount(() => {
  if (proContentGuideTimer !== undefined) window.clearTimeout(proContentGuideTimer)
  unbindProContentGuideListeners()
})

function proContentDiagramKey(): string {
  return aiContentLevelStore.diagramKey(savedDiagramsStore.activeDiagramId)
}

function proContentLevelTitle(id: AiContentLevelId): string {
  return t(`canvas.toolbar.professionalContent.level.${id}.title`)
}

async function handleProContentPick(id: AiContentLevelId): Promise<void> {
  if (id === proContentLevel.value && aiContentLevelStore.userSet) {
    proContentPanelOpen.value = false
    return
  }

  const diagramKey = proContentDiagramKey()
  const generatedAt = aiContentLevelStore.getGeneratedLevel(diagramKey)
  const saved = await aiContentLevelStore.setLevel(id)
  proContentPanelOpen.value = false
  if (!saved) {
    return
  }

  if (generatedAt && generatedAt !== id) {
    notify.info(
      t('canvas.toolbar.professionalContent.notify.afterGenerated', {
        current: proContentLevelTitle(generatedAt),
        next: proContentLevelTitle(id),
      })
    )
    return
  }

  if (id === DEFAULT_AI_CONTENT_LEVEL) {
    notify.info(t('canvas.toolbar.professionalContent.notify.preferenceGeneral'))
    return
  }

  notify.info(
    t('canvas.toolbar.professionalContent.notify.preference', {
      level: proContentLevelTitle(id),
    })
  )
}

function handleProContentKeydown(event: KeyboardEvent, id: AiContentLevelId): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    proContentPanelOpen.value = false
    proContentAnchor.value?.focus()
    return
  }
  const currentIndex = AI_CONTENT_LEVEL_IDS.indexOf(id)
  let nextIndex: number | null = null
  if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
    nextIndex = (currentIndex + 1) % AI_CONTENT_LEVEL_IDS.length
  } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
    nextIndex = (currentIndex - 1 + AI_CONTENT_LEVEL_IDS.length) % AI_CONTENT_LEVEL_IDS.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = AI_CONTENT_LEVEL_IDS.length - 1
  }
  if (nextIndex === null) return
  event.preventDefault()
  const listbox = (event.currentTarget as HTMLElement).closest('[role="listbox"]')
  listbox?.querySelectorAll<HTMLElement>('[role="option"]')[nextIndex]?.focus()
}
</script>

<template>
  <ElPopover
    v-if="!diagramStore.collabSessionActive"
    v-model:visible="proContentPanelOpen"
    placement="bottom-start"
    :width="280"
    trigger="click"
    popper-class="mm-toolbar-popper mm-toolbar-popper--pro-content"
  >
    <template #reference>
      <button
        ref="proContentAnchor"
        type="button"
        class="mm-btn mm-btn--pro-content"
        :class="{
          'mm-btn--icon': props.compact,
          'mm-btn--pro-content-compact': !showProContentHintLabel && !props.compact,
          'mm-btn--pro-content-guide': showProContentGuide,
          'is-open': proContentPanelOpen,
        }"
        :title="proContentButtonTitle"
        :aria-label="proContentButtonTitle"
        :aria-expanded="proContentPanelOpen"
      >
        <span
          class="mm-pro-icon"
          :style="{
            color: proContentActiveOption.color,
            backgroundColor: `color-mix(in srgb, ${proContentActiveOption.color} 16%, transparent)`,
          }"
          aria-hidden="true"
        >
          <component
            :is="proContentActiveOption.icon"
            class="mm-pro-icon__svg"
          />
        </span>
        <span
          v-if="showProContentHintLabel"
          class="mm-btn__label"
          >{{ t('canvas.toolbar.professionalContent.label') }}</span
        >
        <span
          v-if="!props.compact"
          class="mm-pro-level-tag"
          :style="{ color: proContentActiveOption.color }"
          >{{ proContentActiveOption.title }}</span
        >
        <ChevronDown
          class="mm-btn__chevron"
          :class="{ 'mm-btn__chevron--open': proContentPanelOpen }"
        />
      </button>
    </template>

    <div
      class="mm-pro-panel"
      role="listbox"
      :aria-label="t('canvas.toolbar.professionalContent.panelTitle')"
    >
      <div class="mm-pro-panel__eyebrow">
        {{ t('canvas.toolbar.professionalContent.panelTitle') }}
      </div>
      <div class="mm-pro-panel__list">
        <button
          v-for="option in proContentLevelOptions"
          :key="option.id"
          type="button"
          class="mm-pro-level"
          :class="{ 'is-active': option.id === proContentLevel }"
          role="option"
          :aria-selected="option.id === proContentLevel"
          :tabindex="option.id === proContentLevel ? 0 : -1"
          @click="handleProContentPick(option.id)"
          @keydown="handleProContentKeydown($event, option.id)"
        >
          <span
            class="mm-pro-icon"
            :style="{
              color: option.color,
              backgroundColor: `color-mix(in srgb, ${option.color} 16%, transparent)`,
            }"
            aria-hidden="true"
          >
            <component
              :is="option.icon"
              class="mm-pro-icon__svg"
            />
          </span>
          <span class="mm-pro-level__title">{{ option.title }}</span>
          <span class="mm-pro-level__hint">{{ option.description }}</span>
          <Check
            v-if="option.id === proContentLevel"
            class="mm-pro-level__check"
            aria-hidden="true"
          />
        </button>
      </div>
    </div>
  </ElPopover>

  <Teleport to="body">
    <Transition name="mm-pro-guide">
      <div
        v-if="showProContentGuide"
        class="mm-pro-guide"
        role="dialog"
        :aria-label="t('canvas.toolbar.professionalContent.guideTitle')"
        :style="proContentGuideStyle"
      >
        <div
          class="mm-pro-guide__arrow"
          aria-hidden="true"
        />
        <div class="mm-pro-guide__card">
          <button
            type="button"
            class="mm-pro-guide__close"
            :aria-label="t('canvas.toolbar.professionalContent.guideDismiss')"
            @click="dismissProContentGuide"
          >
            <X
              class="h-3.5 w-3.5"
              :stroke-width="2.5"
            />
          </button>
          <p class="mm-pro-guide__title">
            {{ t('canvas.toolbar.professionalContent.guideTitle') }}
          </p>
          <p class="mm-pro-guide__body">
            {{ t('canvas.toolbar.professionalContent.guideBody') }}
          </p>
          <div class="mm-pro-guide__actions">
            <button
              type="button"
              class="mm-pro-guide__dismiss"
              @click="dismissProContentGuide"
            >
              {{ t('canvas.toolbar.professionalContent.guideDismiss') }}
            </button>
            <button
              type="button"
              class="mm-pro-guide__action"
              @click="openProContentFromGuide"
            >
              {{ t('canvas.toolbar.professionalContent.guideAction') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped src="./canvasToolbarMindMapAudiencePicker.css"></style>
<style src="./canvasToolbarMindMapPopper.css"></style>
