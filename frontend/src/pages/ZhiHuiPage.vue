<script setup lang="ts">
/**
 * ZhiHui (智绘) — landing and conversations are separate (MindMate-style).
 * Sidebar 智绘 → landing; history select → conversation; dropdown follows diagram.
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import ZhiHuiDiagramDropdown from '@/components/zhihui/ZhiHuiDiagramDropdown.vue'
import ZhiHuiDiagramStudio from '@/components/zhihui/ZhiHuiDiagramStudio.vue'
import ZhiHuiStudio from '@/components/zhihui/ZhiHuiStudio.vue'
import {
  ZHIHUI_MODE_ORDER,
  type ZhihuiMode,
} from '@/components/zhihui/zhihuiModes'
import { useLanguage } from '@/composables'
import { useZhihuiHistoryStore } from '@/stores/zhihuiHistory'

const { t } = useLanguage()
const historyStore = useZhihuiHistoryStore()

const mode = ref<ZhihuiMode>('image')
const diagramId = ref<string | null>(null)
const diagramBusy = ref(false)
const diagramStudioRef = ref<{ generate: () => Promise<void> } | null>(null)
/** Prevent dropdown↔conversation sync loops while hydrating a history row. */
const syncingFromConversation = ref(false)

const modeOptions = computed(() =>
  ZHIHUI_MODE_ORDER.map((value) => ({
    value,
    label: String(t(`zhihui.mode.${value}`)),
  }))
)

const canGenerateDiagram = computed(
  () => Boolean(diagramId.value) && !diagramBusy.value
)

/** Title fallback when the conversation diagram is not in the library list yet. */
const diagramFallbackLabel = computed(() => {
  const id = historyStore.currentId
  if (!id) return null
  const detail =
    historyStore.currentDetail?.id === id ? historyStore.currentDetail : null
  const listItem = historyStore.items.find((row) => row.id === id)
  const title = detail?.diagram_title || listItem?.diagram_title || detail?.title || ''
  return title.trim() || null
})

function isDiagramConversation(id: string): boolean {
  if (historyStore.currentDetail?.id === id) {
    return historyStore.currentDetail.mode === 'diagram'
  }
  return historyStore.items.find((row) => row.id === id)?.mode === 'diagram'
}

onMounted(() => {
  void historyStore.fetchHistory()
})

watch(
  () => historyStore.currentId,
  async (id) => {
    if (!id) {
      diagramBusy.value = false
      const landing = historyStore.landingStudioMode
      if (landing === 'image') {
        mode.value = 'image'
      } else if (landing === 'diagram') {
        mode.value = 'diagram'
      }
      // 'preserve' → keep the mode the user just selected in the segmented control
      return
    }
    syncingFromConversation.value = true
    try {
      // Optimistic: list rows already carry mode/diagram_id — switch studio immediately.
      const listItem = historyStore.items.find((row) => row.id === id)
      if (listItem?.mode === 'diagram') {
        mode.value = 'diagram'
        if (listItem.diagram_id) {
          diagramId.value = listItem.diagram_id
        }
      } else if (listItem?.mode === 'image') {
        mode.value = 'image'
        diagramBusy.value = false
      }
      let detail = historyStore.currentDetail?.id === id ? historyStore.currentDetail : null
      if (!detail) {
        detail = await historyStore.loadConversation(id)
      }
      if (!detail || detail.id !== id || historyStore.currentId !== id) return
      if (detail.mode === 'diagram') {
        mode.value = 'diagram'
        diagramId.value = detail.diagram_id ?? null
        return
      }
      mode.value = 'image'
    } finally {
      // Hold the guard through the mode-watch flush so hydration cannot
      // be mistaken for a manual mode click (which would clear selection).
      await nextTick()
      syncingFromConversation.value = false
    }
  }
)

/**
 * Mode segmented control is source of truth for landing switches.
 * Do not clear a history selection when mode merely matches that conversation
 * (hydration sets mode → must not bounce back to landing).
 */
watch(mode, (next, prev) => {
  if (syncingFromConversation.value) return
  if (next === prev) return
  if (next === 'image') {
    diagramBusy.value = false
  }
  const id = historyStore.currentId
  if (!id) return
  if (next === 'diagram' && isDiagramConversation(id)) return
  if (next === 'image' && !isDiagramConversation(id)) return
  // User switched away from the open conversation's studio type.
  historyStore.startLanding('preserve')
})

function onDiagramIdUpdate(id: string | null): void {
  diagramId.value = id
  if (syncingFromConversation.value) return
  const current = historyStore.currentId
  if (!current || !isDiagramConversation(current)) return
  const convDiagramId =
    historyStore.currentDetail?.id === current
      ? historyStore.currentDetail.diagram_id
      : historyStore.items.find((row) => row.id === current)?.diagram_id
  if (id !== convDiagramId) {
    historyStore.startLanding('diagram')
  }
}

async function onGenerateDiagram(): Promise<void> {
  await diagramStudioRef.value?.generate()
}
</script>

<template>
  <div class="zhihui-page">
    <header class="zhihui-page__header">
      <div class="flex min-w-0 flex-1 items-center gap-3">
        <h1 class="shrink-0 text-sm font-semibold text-stone-800">
          {{ t('zhihui.title') }}
        </h1>
        <ZhiHuiDiagramDropdown
          v-if="mode === 'diagram'"
          :model-value="diagramId"
          :fallback-label="diagramFallbackLabel"
          :disabled="diagramBusy"
          @update:model-value="onDiagramIdUpdate"
        />
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <button
          v-if="mode === 'diagram'"
          type="button"
          class="zhihui-page__generate"
          :disabled="!canGenerateDiagram"
          @click="onGenerateDiagram"
        >
          {{ t('zhihui.generate') }}
        </button>
        <div class="zhihui-page__modes">
          <AdminSwissSegmented
            v-model="mode"
            :options="modeOptions"
            :ariaLabel="String(t('zhihui.modeAria'))"
            fit
          />
        </div>
      </div>
    </header>

    <div class="zhihui-page__body">
      <ZhiHuiDiagramStudio
        v-if="mode === 'diagram'"
        ref="diagramStudioRef"
        :diagram-id="diagramId"
        @update:busy="diagramBusy = $event"
        @generated="historyStore.fetchHistory()"
      />
      <ZhiHuiStudio
        v-else
        v-model:mode="mode"
        @generated="historyStore.fetchHistory()"
      />
    </div>
  </div>
</template>

<style scoped>
/*
 * MindGraph sheen/wind motion, rotated into a top→bottom sunbeam wash.
 * Cream → gold → amber bands travel downward under the header.
 */
.zhihui-page {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  color-scheme: light;
  background: rgb(250 250 249);
}

.zhihui-page__header {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  flex-shrink: 0;
  height: 3.5rem;
  padding: 0 1rem;
  gap: 0.75rem;
  border-bottom: 1px solid rgb(231 229 228);
  background: rgb(255 255 255);
}

.zhihui-page__generate {
  border-radius: 9999px;
  border: 1px solid #e7e5e4;
  background: #1c1917;
  color: #fff;
  font-size: 0.8125rem;
  padding: 0.4rem 0.95rem;
  min-height: 2rem;
}

.zhihui-page__generate:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.zhihui-page__body {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
  background-color: rgb(250 250 249);
  background-image: linear-gradient(
    180deg,
    rgba(254, 243, 199, 0.72) 0%,
    rgba(251, 191, 36, 0.2) 8%,
    rgba(245, 158, 11, 0.14) 16%,
    rgba(255, 255, 255, 0.9) 28%,
    rgba(217, 119, 6, 0.1) 36%,
    rgba(254, 243, 199, 0.45) 42%,
    rgba(180, 83, 9, 0.08) 52%,
    transparent 68%,
    transparent 100%
  );
  background-size: 100% 280%;
  background-position: 50% 0%;
  background-repeat: no-repeat;
  animation: zhihuiBeamSheen 16s linear infinite;
  animation-delay: -5s;
}

.zhihui-page__body::before,
.zhihui-page__body::after {
  content: '';
  position: absolute;
  pointer-events: none;
  z-index: 0;
}

.zhihui-page__body::before {
  top: -55%;
  left: -15%;
  width: 130%;
  height: 160%;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(254, 243, 199, 0.55) 12%,
    rgba(245, 158, 11, 0.16) 28%,
    rgba(255, 251, 235, 0.7) 36%,
    rgba(217, 119, 6, 0.1) 44%,
    rgba(214, 211, 209, 0.12) 58%,
    transparent 78%
  );
  filter: blur(12px);
  transform: translateY(-8%) rotate(0.4deg);
  animation: zhihuiBeamPrimary 22s linear infinite;
  animation-delay: -8s;
}

.zhihui-page__body::after {
  top: -40%;
  left: -20%;
  width: 140%;
  height: 150%;
  background: linear-gradient(
    185deg,
    transparent 0%,
    rgba(255, 255, 255, 0.65) 18%,
    rgba(251, 191, 36, 0.14) 32%,
    rgba(254, 243, 199, 0.5) 40%,
    rgba(180, 83, 9, 0.1) 52%,
    transparent 72%
  );
  filter: blur(10px);
  opacity: 1;
  animation: zhihuiBeamSecondary 30s linear infinite;
  animation-delay: -14s;
}

.zhihui-page__body > :deep(.zhihui-studio),
.zhihui-page__body > :deep(.zhihui-diagram-studio) {
  position: relative;
  z-index: 1;
}

.zhihui-page__modes :deep(.admin-swiss-segmented) {
  border-radius: 9999px;
  padding: 3px;
  gap: 2px;
  background: #f5f5f4;
  border-color: #e7e5e4;
  overflow: visible;
}

.zhihui-page__modes :deep(.admin-swiss-segment) {
  border-radius: 9999px;
  border-left: none !important;
  padding: 0.4rem 0.95rem;
  font-size: 0.8125rem;
  min-height: 2rem;
}

.zhihui-page__modes :deep(.admin-swiss-segment.is-active) {
  background: #fff;
  color: #1c1917;
  box-shadow: 0 1px 2px rgb(28 25 23 / 8%);
}

@keyframes zhihuiBeamSheen {
  0%,
  100% {
    background-position: 50% 0%;
  }
  50% {
    background-position: 50% 100%;
  }
}

@keyframes zhihuiBeamPrimary {
  0%,
  100% {
    transform: translateY(-10%) rotate(0.4deg);
  }
  50% {
    transform: translateY(28%) rotate(-0.2deg);
  }
}

@keyframes zhihuiBeamSecondary {
  0%,
  100% {
    transform: translateY(-6%) translateX(2%);
  }
  50% {
    transform: translateY(34%) translateX(-3%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .zhihui-page__body {
    animation: none;
    background-position: 50% 20%;
  }

  .zhihui-page__body::before,
  .zhihui-page__body::after {
    animation: none;
  }
}
</style>
