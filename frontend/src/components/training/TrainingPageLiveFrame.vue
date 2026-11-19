<script setup lang="ts">
/**
 * One slide: the sidebar, the account chip, and the page beside them.
 * Gallery cards, sidebar links, and canvas Back stay on this slide.
 */
import { computed, onUnmounted, provide, ref, useTemplateRef, watch } from 'vue'

import { ElButton } from 'element-plus'

import { PanelLeftOpen } from '@lucide/vue'

import AppSidebar from '@/components/sidebar/AppSidebar.vue'
import TrainingCanvasPreview from '@/components/training/TrainingCanvasPreview.vue'
import TrainingCanvasVoiceBadge from '@/components/training/TrainingCanvasVoiceBadge.vue'
import TrainingSlideAudio from '@/components/training/TrainingSlideAudio.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { builderSlideSidebarClosed } from '@/composables/training/builderSlideChrome'
import {
  type TrainingDeckTarget,
  applyDeckPage,
  armTrainingDeckNavigation,
  provideTrainingDeckNav,
  pushTrainingDeckSink,
} from '@/composables/training/trainingDeckNav'
import {
  TRAINING_DIALOG_HOST,
  provideTrainingInlineHost,
  setTrainingDialogHost,
} from '@/composables/training/trainingInlineHost'
import {
  TRAINING_LOCK_SCOPE,
  applyTrainingUiLock,
  pushTrainingLockScope,
} from '@/composables/training/trainingUiLock'
import { trainingLivePage } from '@/config/trainingPageLive'
import type { TrainingPageKey } from '@/config/trainingPages'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import type { TrainingCourseStep } from '@/types/training'
import { apiRequest } from '@/utils/apiClient'

provideTrainingInlineHost()
const frameEl = ref<HTMLElement | null>(null)
provide(TRAINING_DIALOG_HOST, frameEl)

const props = withDefaults(
  defineProps<{
    pageKey?: string | null
    diagramType?: string | null
    interactive?: boolean
    authoring?: boolean
    /** Null keeps playback audible and the builder quiet until the editor asks. */
    playAudio?: boolean | null
    step?: TrainingCourseStep | null
    courseId?: string | null
    /** Use the builder slide's sidebar instead of starting open. */
    useBuilderChrome?: boolean
  }>(),
  { authoring: false, step: null, playAudio: null, courseId: null, useBuilderChrome: false }
)

const shouldPlayAudio = computed(() =>
  props.playAudio === null ? !props.authoring : props.playAudio
)
const voicePlaying = ref(false)
const audioRef = useTemplateRef<{ toggleVoice: () => Promise<void> }>('audioRef')

const builder = useTrainingBuilderStore()

async function onVoiceToggle(): Promise<void> {
  const courseId = (props.courseId || builder.courseId || '').trim()
  const index = props.step?.position
  if (!courseId || typeof index !== 'number') return
  await apiRequest('/api/learning-space/glasses/voice/cue', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ course_id: courseId, index }),
  })
}
const { t } = useLanguage()
/** Playback pages start open. The builder and its preview share one closed flag. */
const localSidebarClosed = ref(props.authoring)
const sharesBuilderChrome = computed(() => props.authoring || props.useBuilderChrome)
const sidebarClosed = computed({
  get: () =>
    sharesBuilderChrome.value ? builderSlideSidebarClosed.value : localSidebarClosed.value,
  set: (closed: boolean) => {
    if (sharesBuilderChrome.value) builderSlideSidebarClosed.value = closed
    else localSidebarClosed.value = closed
  },
})

function toggleSlideSidebar(): void {
  sidebarClosed.value = !sidebarClosed.value
}

const scopeId = `deck-${Math.random().toString(36).slice(2, 10)}`
provide(TRAINING_LOCK_SCOPE, scopeId)
const releaseScope = pushTrainingLockScope(scopeId)

const entry = ref<TrainingPageKey>('mindgraph')
const override = ref<TrainingDeckTarget | null>(null)

const livePage = computed(() => trainingLivePage(shownPage.value))
const isCanvas = computed(() => shownPage.value === 'canvas')
const showVoiceBadge = computed(() => {
  if (!props.authoring || !props.step) return false
  const file = (props.step.voice_url || '').trim()
  const line = (props.step.glasses_line || '').trim()
  return Boolean(file || line)
})

const shownPage = computed(() => {
  if (props.authoring && props.step?.page_key) return props.step.page_key
  return override.value?.pageKey || props.pageKey || props.step?.page_key || null
})

const shownDiagram = computed(() => {
  if (props.authoring && props.step) return props.step.diagram_type
  if (override.value) return override.value.diagramType
  return props.diagramType ?? props.step?.diagram_type
})

watch(
  () => [props.pageKey, props.diagramType, props.step?.id] as const,
  () => {
    override.value = null
  }
)

watch(
  () => [props.step?.ui_lock, props.step?.modal_key, props.step?.id] as const,
  ([lock, modal]) => {
    if (props.authoring) return
    applyTrainingUiLock(lock || modal || null)
  },
  { immediate: true }
)

function currentPage(): TrainingPageKey {
  return (shownPage.value as TrainingPageKey) || 'mindgraph'
}

function openPage(pageKey: TrainingPageKey, diagramType?: string | null): void {
  const from = currentPage()
  if (pageKey === 'canvas' && from !== 'canvas') entry.value = from
  const diagram = diagramType ?? null
  if (props.authoring && props.step) {
    applyDeckPage(props.step, pageKey, diagram)
    return
  }
  override.value = { pageKey, diagramType: pageKey === 'canvas' ? diagram : null }
}

function backFromCanvas(): void {
  const back = entry.value === 'canvas' ? 'mindgraph' : entry.value
  openPage(back, null)
}

provideTrainingDeckNav({
  openPage,
  openDiagram: (diagramType: string) => openPage('canvas', diagramType),
  backFromCanvas,
})

const releaseSink = pushTrainingDeckSink((target) => {
  openPage(target.pageKey, target.diagramType)
})

watch(
  () => props.step?.voice_url,
  () => {
    voicePlaying.value = false
  }
)

watch(frameEl, (el) => {
  setTrainingDialogHost(scopeId, el)
})

onUnmounted(() => {
  setTrainingDialogHost(scopeId, null)
  releaseSink()
  releaseScope()
  if (!props.authoring) applyTrainingUiLock(null)
})
</script>

<template>
  <div
    ref="frameEl"
    class="live-frame"
    :class="{ 'live-frame--interactive': interactive }"
    @click.capture="armTrainingDeckNavigation"
  >
    <div class="live-shell">
      <AppSidebar
        class="live-shell__side"
        :collapsed="sidebarClosed"
        @toggle-collapsed="toggleSlideSidebar"
      />
      <div class="live-shell__main">
        <TrainingCanvasVoiceBadge
          v-if="showVoiceBadge"
          :playing="voicePlaying"
          :aside="sidebarClosed"
          @toggle="onVoiceToggle"
        />
        <ElButton
          v-if="sidebarClosed"
          text
          circle
          class="live-shell__expand"
          :title="t('sidebar.expandSidebar')"
          :aria-label="t('sidebar.expandSidebar')"
          @click="sidebarClosed = false"
        >
          <PanelLeftOpen
            class="h-[18px] w-[18px]"
            aria-hidden="true"
          />
        </ElButton>
        <TrainingCanvasPreview
          v-if="isCanvas"
          :diagram-type="shownDiagram"
          :interactive="interactive"
          :publish-bridge="authoring"
          :follow-walk="!authoring"
          :step="step"
        />
        <div
          v-else
          class="live-frame__world live-frame__world--full"
        >
          <Suspense v-if="livePage">
            <component :is="livePage" />
            <template #fallback>
              <div class="live-frame__loading">
                <I18nText k="common.loading" />
              </div>
            </template>
          </Suspense>
        </div>
      </div>
    </div>
    <TrainingSlideAudio
      v-if="step && (shouldPlayAudio || showVoiceBadge)"
      ref="audioRef"
      :step="step"
      :autoplay="shouldPlayAudio"
      @playing="voicePlaying = $event"
    />
  </div>
</template>

<style scoped>
.live-frame {
  position: relative;
  height: 100%;
  min-height: 8rem;
  overflow: hidden;
  transform: translateZ(0);
  background: #f8fafc;
  pointer-events: none;
  user-select: none;
}
.live-frame--interactive {
  pointer-events: auto;
  user-select: auto;
}
.live-shell {
  display: flex;
  height: 100%;
  min-height: 100%;
}
.live-shell__main {
  position: relative;
  min-width: 0;
  min-height: 0;
  flex: 1;
}
.live-shell__expand {
  position: absolute;
  top: 0.45rem;
  left: 0.45rem;
  z-index: 5;
}
.live-frame__world--full {
  position: absolute;
  inset: 0;
  overflow: auto;
  pointer-events: auto;
  user-select: auto;
}
.live-frame__world--full > :deep(*) {
  height: auto;
  min-height: 100%;
}
.live-frame :deep(.el-overlay),
.live-frame :deep(.el-overlay-dialog) {
  position: absolute;
  overflow: auto;
}
.live-frame__loading {
  display: grid;
  height: 100%;
  place-items: center;
  color: #78716c;
  font-size: 0.85rem;
}
</style>
