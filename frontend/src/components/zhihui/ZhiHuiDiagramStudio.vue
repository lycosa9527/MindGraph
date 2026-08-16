<script setup lang="ts">
/**
 * Superadmin 图示生图 demo — classroom slide_deck jobs + deck chrome.
 */
import { computed, ref, watch } from 'vue'

import { zhihuiDiagramStatusToast } from '@/components/zhihui/zhihuiDiagramProgress'
import { useLanguage, useNotifications } from '@/composables'
import {
  enqueueMindClassroomJob,
  fetchMindClassroomJobByDiagram,
  isClassroomJobActive,
  pollMindClassroomJob,
  type MindClassroomJobDetail,
} from '@/composables/mindMap/mindClassroomJobApi'
import { classroomSlidesToGenerations } from '@/composables/zhihui/classroomDiagramJob'
import { useAiContentLevelStore, useMindClassroomStore } from '@/stores'
import { stabilizeZhihuiGenerations, type ZhihuiGenerationItem } from '@/stores/zhihuiHistory'
import { apiPost } from '@/utils/apiClient'

import ZhiHuiDiagramCanvasPane from './ZhiHuiDiagramCanvasPane.vue'
import ZhiHuiDiagramDeck from './ZhiHuiDiagramDeck.vue'
import { resolveZhihuiSlideFocusHints } from './zhihuiFocus'

const props = defineProps<{
  diagramId: string | null
}>()

const emit = defineEmits<{
  generated: []
  'update:busy': [busy: boolean]
}>()

const { t, currentLanguage } = useLanguage()
const notify = useNotifications()
const aiLevelStore = useAiContentLevelStore()
const classroomStore = useMindClassroomStore()

const slides = ref<ZhihuiGenerationItem[]>([])
const slideIndex = ref(0)
const status = ref<string | null>(null)
const progress = ref<Record<string, unknown> | null>(null)
const errorMessage = ref<string | null>(null)
const activeJobId = ref<string | null>(null)
const legacyZhihui = ref(false)
const conversationDiagramId = ref<string | null>(null)
const lessonPlan = ref<Record<string, unknown> | null>(null)
const starting = ref(false)
const userPinnedSlide = ref(false)
const focusEpoch = ref(0)
const announceMilestones = ref(false)
const lastAnnouncedStatus = ref<string | null>(null)
let pollGeneration = 0

const busy = computed(
  () => starting.value || isClassroomJobActive(status.value)
)

/** Prefer conversation diagram on restore; fall back to header dropdown. */
const canvasDiagramId = computed(
  () => conversationDiagramId.value || props.diagramId
)

/** First PPT is always the whole-case topic → fit full mind map. */
const topicOverview = computed(() => slideIndex.value === 0)

const focusNodeIds = computed(() => {
  const slide = slides.value[slideIndex.value]
  return resolveZhihuiSlideFocusHints({
    slideIndex: slideIndex.value,
    focusNodeIds: slide?.focus_node_ids,
    lessonPlan: lessonPlan.value,
    slideTitle: slide?.slide_title || slide?.prompt || null,
  })
})

watch(busy, (value) => emit('update:busy', value), { immediate: true })

function announceStatusChange(
  nextStatus: string | null | undefined,
  detailError: string | null | undefined
): void {
  if (!announceMilestones.value) return
  const announcement = zhihuiDiagramStatusToast(lastAnnouncedStatus.value, nextStatus)
  lastAnnouncedStatus.value = nextStatus ? String(nextStatus) : null
  if (!announcement) return
  const message =
    announcement.useErrorMessage && detailError
      ? detailError
      : String(t(announcement.messageKey))
  if (announcement.level === 'success') notify.success(message)
  else if (announcement.level === 'warning') notify.warning(message)
  else if (announcement.level === 'error') notify.error(message)
  else notify.info(message)
}

function applyJob(
  detail: MindClassroomJobDetail,
  options: { followLatest: boolean; resetSlide?: boolean }
): void {
  const previousStatus = status.value
  status.value = String(detail.status || '')
  progress.value = detail.progress ?? null
  errorMessage.value = detail.error_message ?? null
  conversationDiagramId.value = detail.diagram_id ?? conversationDiagramId.value
  lessonPlan.value =
    detail.lesson_plan_json && typeof detail.lesson_plan_json === 'object'
      ? detail.lesson_plan_json
      : lessonPlan.value
  legacyZhihui.value = Boolean(detail.legacy_zhihui)
  const mapped = classroomSlidesToGenerations(detail)
  const nextSlides = stabilizeZhihuiGenerations(slides.value, mapped) ?? []
  const prevLen = slides.value.length
  slides.value = nextSlides
  if (options.resetSlide) {
    slideIndex.value = 0
  } else if (options.followLatest && isClassroomJobActive(detail.status) && !userPinnedSlide.value) {
    if (nextSlides.length > 0 && nextSlides.length !== prevLen) {
      slideIndex.value = nextSlides.length - 1
    }
  } else if (slideIndex.value >= nextSlides.length) {
    slideIndex.value = Math.max(0, nextSlides.length - 1)
  }
  if (announceMilestones.value && String(previousStatus || '') !== String(detail.status || '')) {
    announceStatusChange(detail.status, detail.error_message)
  }
}

function onSlideIndexUpdate(index: number): void {
  userPinnedSlide.value = true
  slideIndex.value = index
}

async function watchJob(jobId: string): Promise<void> {
  const generation = pollGeneration
  try {
    await pollMindClassroomJob(jobId, {
      shouldStop: () => generation !== pollGeneration,
      onUpdate: (detail) => {
        applyJob(detail, { followLatest: true })
      },
    })
    emit('generated')
  } catch (err) {
    if (generation !== pollGeneration) return
    const message = err instanceof Error ? err.message : String(err)
    if (message !== 'cancelled') {
      errorMessage.value = message
      status.value = 'failed'
    }
  }
}

async function startSlideJob(reuse: boolean): Promise<void> {
  if (!props.diagramId) {
    notify.warning(String(t('zhihui.diagram.selectMindmapFirst')))
    return
  }
  if (busy.value) return
  starting.value = true
  pollGeneration += 1
  try {
    const lang =
      currentLanguage.value === 'zh' || currentLanguage.value.startsWith('zh') ? 'zh' : 'en'
    const created = await enqueueMindClassroomJob({
      mode: 'slide_deck',
      diagram_id: props.diagramId,
      language: lang,
      audience_level: aiLevelStore.level,
      audience_title: t(`canvas.toolbar.professionalContent.level.${aiLevelStore.level}.title`),
      tone: classroomStore.tone,
      reuse,
    })
    activeJobId.value = created.job_id
    conversationDiagramId.value = props.diagramId
    lessonPlan.value = null
    status.value = created.status || 'queued'
    if (!reuse) {
      slides.value = []
      slideIndex.value = 0
    }
    userPinnedSlide.value = false
    errorMessage.value = null
    announceMilestones.value = true
    lastAnnouncedStatus.value = String(status.value)
    focusEpoch.value += 1
    notify.success(String(t('zhihui.diagram.jobStarted')))
    void watchJob(created.job_id)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(t('zhihui.generateFailed'))
    notify.error(message)
  } finally {
    starting.value = false
  }
}

async function resume(): Promise<void> {
  if (legacyZhihui.value && activeJobId.value) {
    starting.value = true
    try {
      const res = await apiPost(`/api/zhihui/conversations/${activeJobId.value}/resume`, {})
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      notify.success(String(t('zhihui.diagram.jobStarted')))
    } catch (err) {
      const message = err instanceof Error ? err.message : String(t('zhihui.generateFailed'))
      notify.error(message)
    } finally {
      starting.value = false
    }
    return
  }
  await startSlideJob(false)
}

async function generate(): Promise<void> {
  await startSlideJob(true)
}

async function hydrateFromDiagram(diagramId: string | null): Promise<void> {
  if (!diagramId) {
    pollGeneration += 1
    activeJobId.value = null
    conversationDiagramId.value = null
    lessonPlan.value = null
    status.value = null
    progress.value = null
    errorMessage.value = null
    slides.value = []
    slideIndex.value = 0
    userPinnedSlide.value = false
    legacyZhihui.value = false
    return
  }
  try {
    const detail = await fetchMindClassroomJobByDiagram(diagramId)
    activeJobId.value = detail.id
    applyJob(detail, { followLatest: isClassroomJobActive(detail.status), resetSlide: true })
    focusEpoch.value += 1
    if (isClassroomJobActive(detail.status) && !detail.legacy_zhihui) {
      announceMilestones.value = true
      lastAnnouncedStatus.value = String(detail.status)
      void watchJob(detail.id)
    }
  } catch {
    /* no prior deck */
  }
}

watch(
  () => props.diagramId,
  (id) => {
    void hydrateFromDiagram(id)
  },
  { immediate: true }
)

const hasSlides = computed(() => slides.value.length > 0)

defineExpose({ generate, busy, hasSlides })
</script>

<template>
  <div class="zhihui-diagram-studio flex min-h-0 flex-1 gap-3 p-3">
    <div class="min-h-0 w-[30%] shrink-0">
      <ZhiHuiDiagramCanvasPane
        :diagram-id="canvasDiagramId"
        :topic-overview="topicOverview"
        :focus-node-ids="focusNodeIds"
        :focus-epoch="focusEpoch"
      />
    </div>
    <div class="min-h-0 min-w-0 flex-1">
      <ZhiHuiDiagramDeck
        :slide-index="slideIndex"
        :slides="slides"
        :status="status"
        :progress="progress"
        :error-message="errorMessage"
        :starting="starting"
        @update:slide-index="onSlideIndexUpdate"
        @resume="resume"
      />
    </div>
  </div>
</template>
