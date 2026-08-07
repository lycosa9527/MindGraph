<script setup lang="ts">
/**
 * 图示生图 studio — 30/70 mindmap + PPT deck; job lifecycle via history store + event bus.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useEventBus, useLanguage, useNotifications } from '@/composables'
import {
  isZhihuiJobActive,
  type ZhihuiConversationItem,
  type ZhihuiGenerationItem,
  useZhihuiHistoryStore,
} from '@/stores/zhihuiHistory'
import { apiPost } from '@/utils/apiClient'

import ZhiHuiDiagramCanvasPane from './ZhiHuiDiagramCanvasPane.vue'
import ZhiHuiDiagramDeck from './ZhiHuiDiagramDeck.vue'

const props = defineProps<{
  diagramId: string | null
}>()

const emit = defineEmits<{
  generated: []
  'update:busy': [busy: boolean]
}>()

const { t, currentLanguage } = useLanguage()
const notify = useNotifications()
const historyStore = useZhihuiHistoryStore()
const { on } = useEventBus()

const slides = ref<ZhihuiGenerationItem[]>([])
const slideIndex = ref(0)
const status = ref<string | null>(null)
const progress = ref<Record<string, unknown> | null>(null)
const errorMessage = ref<string | null>(null)
const activeConversationId = ref<string | null>(null)
const starting = ref(false)
const userPinnedSlide = ref(false)

const busy = computed(
  () => starting.value || isZhihuiJobActive(status.value)
)

const focusNodeIds = computed(() => {
  const slide = slides.value[slideIndex.value]
  const ids = slide?.focus_node_ids
  return Array.isArray(ids) ? ids.map(String) : null
})

watch(busy, (value) => emit('update:busy', value), { immediate: true })

function applyDetail(
  detail: ZhihuiConversationItem,
  options: { followLatest: boolean }
): void {
  status.value = detail.status
  progress.value = detail.progress ?? null
  errorMessage.value = detail.error_message ?? null
  const nextSlides = detail.generations ?? []
  const prevLen = slides.value.length
  slides.value = nextSlides
  if (options.followLatest && isZhihuiJobActive(detail.status) && !userPinnedSlide.value) {
    if (nextSlides.length > 0 && nextSlides.length !== prevLen) {
      slideIndex.value = nextSlides.length - 1
    }
  } else if (slideIndex.value >= nextSlides.length) {
    slideIndex.value = Math.max(0, nextSlides.length - 1)
  }
}

function onSlideIndexUpdate(index: number): void {
  userPinnedSlide.value = true
  slideIndex.value = index
}

async function hydrateFromId(id: string | null): Promise<void> {
  if (!id) {
    activeConversationId.value = null
    status.value = null
    progress.value = null
    errorMessage.value = null
    slides.value = []
    slideIndex.value = 0
    userPinnedSlide.value = false
    historyStore.stopPolling()
    return
  }
  const detail = await historyStore.loadConversation(id)
  if (!detail || detail.mode !== 'diagram') {
    return
  }
  activeConversationId.value = id
  userPinnedSlide.value = false
  applyDetail(detail, { followLatest: true })
  if (isZhihuiJobActive(detail.status)) {
    historyStore.startPolling(id)
  } else {
    historyStore.stopPolling()
  }
}

watch(
  () => historyStore.currentId,
  (id) => {
    void hydrateFromId(id)
  },
  { immediate: true }
)

onMounted(() => {
  on('zhihui:conversation_updated', ({ conversationId }) => {
    if (conversationId !== activeConversationId.value) return
    const detail = historyStore.currentDetail
    if (!detail || detail.id !== conversationId) return
    applyDetail(detail, { followLatest: true })
  })
  on('zhihui:job_terminal', ({ conversationId, status: terminal }) => {
    if (conversationId !== activeConversationId.value) return
    status.value = terminal
    const detail = historyStore.currentDetail
    if (detail?.id === conversationId) {
      applyDetail(detail, { followLatest: false })
    }
    emit('generated')
  })
})

onBeforeUnmount(() => {
  // Store poller outlives the studio so mode switches keep tracking the job.
})

async function resume(): Promise<void> {
  const conversationId = activeConversationId.value
  if (!conversationId || busy.value) return
  starting.value = true
  try {
    const res = await apiPost(`/api/zhihui/conversations/${conversationId}/resume`, {})
    if (!res.ok) {
      const raw = await res.text()
      let message = raw || `HTTP ${res.status}`
      try {
        const body = JSON.parse(raw) as { detail?: string }
        if (body.detail) message = String(body.detail)
      } catch {
        // keep raw
      }
      throw new Error(message)
    }
    status.value = 'queued'
    errorMessage.value = null
    userPinnedSlide.value = false
    historyStore.upsertConversation({
      id: conversationId,
      mode: 'diagram',
      title: historyStore.currentDetail?.title || '',
      status: 'queued',
      diagram_id: props.diagramId,
    })
    historyStore.startPolling(conversationId)
    notify.success(String(t('zhihui.diagram.jobStarted')))
  } catch (err) {
    const message = err instanceof Error ? err.message : String(t('zhihui.generateFailed'))
    notify.error(message)
  } finally {
    starting.value = false
  }
}

async function generate(): Promise<void> {
  if (!props.diagramId) {
    notify.warning(String(t('zhihui.diagram.selectMindmapFirst')))
    return
  }
  if (busy.value) return
  starting.value = true
  try {
    const lang =
      currentLanguage.value === 'zh' || currentLanguage.value.startsWith('zh') ? 'zh' : 'en'
    const res = await apiPost('/api/zhihui/diagram-lesson', {
      diagram_id: props.diagramId,
      language: lang,
    })
    if (!res.ok) {
      const raw = await res.text()
      let message = raw || `HTTP ${res.status}`
      try {
        const body = JSON.parse(raw) as { detail?: string }
        if (body.detail) message = String(body.detail)
      } catch {
        // keep raw text
      }
      throw new Error(message)
    }
    const data = (await res.json()) as { conversation_id?: string; status?: string }
    const conversationId = data.conversation_id
    if (!conversationId) {
      throw new Error(String(t('zhihui.generateFailed')))
    }
    activeConversationId.value = conversationId
    status.value = data.status || 'queued'
    slides.value = []
    slideIndex.value = 0
    userPinnedSlide.value = false
    errorMessage.value = null
    historyStore.upsertConversation({
      id: conversationId,
      mode: 'diagram',
      title: '',
      status: status.value,
      diagram_id: props.diagramId,
    })
    historyStore.selectItem(conversationId)
    historyStore.startPolling(conversationId)
    void historyStore.fetchHistory()
    notify.success(String(t('zhihui.diagram.jobStarted')))
  } catch (err) {
    const message = err instanceof Error ? err.message : String(t('zhihui.generateFailed'))
    notify.error(message)
  } finally {
    starting.value = false
  }
}

defineExpose({ generate, busy })
</script>

<template>
  <div class="zhihui-diagram-studio flex min-h-0 flex-1 gap-3 p-3">
    <div class="min-h-0 w-[30%] shrink-0">
      <ZhiHuiDiagramCanvasPane
        :diagram-id="diagramId"
        :focus-node-ids="focusNodeIds"
      />
    </div>
    <div class="min-h-0 min-w-0 flex-1">
      <ZhiHuiDiagramDeck
        :slide-index="slideIndex"
        :slides="slides"
        :status="status"
        :progress="progress"
        :error-message="errorMessage"
        @update:slide-index="onSlideIndexUpdate"
        @resume="resume"
      />
    </div>
  </div>
</template>
