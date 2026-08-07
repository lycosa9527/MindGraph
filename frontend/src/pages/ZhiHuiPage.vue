<script setup lang="ts">
/**
 * ZhiHui (智绘) — studio landing / conversation; history lives in the left sidebar.
 */
import { computed, onMounted, ref, watch } from 'vue'

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

const modeOptions = computed(() =>
  ZHIHUI_MODE_ORDER.map((value) => ({
    value,
    label: String(t(`zhihui.mode.${value}`)),
  }))
)

const canGenerateDiagram = computed(
  () => Boolean(diagramId.value) && !diagramBusy.value
)

onMounted(() => {
  void historyStore.fetchHistory()
})

watch(
  () => historyStore.currentId,
  async (id) => {
    if (!id) return
    // Prefer cached detail to avoid racing the studio hydrate fetch.
    let detail = historyStore.currentDetail?.id === id ? historyStore.currentDetail : null
    if (!detail) {
      detail = await historyStore.loadConversation(id)
    }
    if (!detail) return
    if (detail.mode === 'diagram') {
      mode.value = 'diagram'
      diagramId.value = detail.diagram_id ?? null
      return
    }
    if (!diagramBusy.value) {
      mode.value = 'image'
    }
  }
)

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
          v-model="diagramId"
          :disabled="diagramBusy"
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
            :disabled="diagramBusy"
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
</style>
