<script setup lang="ts">
/**
 * KnowledgeSpaceSettings - persisted RAG/chunking preferences for the user.
 */
import { computed, ref, watch } from 'vue'

import {
  ElAlert,
  ElButton,
  ElDivider,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElTag,
} from 'element-plus'

import { notify, useLanguage } from '@/composables'
import {
  type RAGSettings,
  type RAGSettingsUpdatePayload,
  useRAGSettings,
  useUpdateRAGSettings,
} from '@/composables/queries'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const { t } = useLanguage()
const settingsQuery = useRAGSettings()
const updateMutation = useUpdateRAGSettings()

const formData = ref<RAGSettingsUpdatePayload>({
  default_method: 'hybrid',
  top_k: 5,
  score_threshold: 0.5,
  chunk_size: 500,
  chunk_overlap: 50,
})

const serverInfo = computed(() => settingsQuery.data.value ?? null)
const saving = computed(() => updateMutation.isPending.value)
const loading = computed(() => settingsQuery.isLoading.value)

function applySettings(settings: RAGSettings): void {
  formData.value = {
    default_method: settings.default_method,
    top_k: settings.top_k,
    score_threshold: settings.score_threshold,
    chunk_size: settings.chunk_size,
    chunk_overlap: settings.chunk_overlap,
  }
}

watch(
  () => settingsQuery.data.value,
  (settings) => {
    if (settings) {
      applySettings(settings)
    }
  },
  { immediate: true }
)

watch(
  () => props.visible,
  (open) => {
    if (open) {
      void settingsQuery.refetch()
    }
  }
)

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

const handleSave = async () => {
  try {
    const result = await updateMutation.mutateAsync(formData.value)
    applySettings(result.settings)
    notify.success(t('knowledge.settings.saveSuccess'))
    if (result.reindex_required) {
      notify.warning(t('knowledge.settings.reindexRequired'))
    }
    handleClose()
  } catch {
    notify.error(t('knowledge.settings.saveFailed'))
  }
}
</script>

<template>
  <ElDrawer
    :model-value="visible"
    :title="t('knowledge.settings.title')"
    size="420px"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <div
      v-if="loading"
      class="p-4 text-sm text-stone-500"
    >
      {{ t('common.loading') }}
    </div>

    <div
      v-else
      class="settings-content p-4"
    >
      <ElAlert
        type="info"
        :closable="false"
        class="mb-4"
        :title="t('knowledge.settings.helpTitle')"
        :description="t('knowledge.settings.helpBody')"
      />

      <ElForm
        :model="formData"
        label-width="150px"
        label-position="left"
      >
        <ElDivider content-position="left">
          <span class="text-sm font-semibold text-stone-700">
            {{ t('knowledge.settings.retrievalSection') }}
          </span>
        </ElDivider>

        <ElFormItem :label="t('knowledge.settings.defaultMethod')">
          <ElSelect
            v-model="formData.default_method"
            style="width: 100%"
          >
            <el-option
              :label="t('knowledge.retrieval.hybrid')"
              value="hybrid"
            />
            <el-option
              :label="t('knowledge.retrieval.semantic')"
              value="semantic"
            />
            <el-option
              :label="t('knowledge.retrieval.keyword')"
              value="keyword"
            />
          </ElSelect>
        </ElFormItem>

        <ElFormItem :label="t('knowledge.settings.defaultTopK')">
          <ElSelect
            v-model="formData.top_k"
            style="width: 100%"
          >
            <el-option
              v-for="value in [1, 3, 5, 10, 20]"
              :key="value"
              :label="value"
              :value="value"
            />
          </ElSelect>
        </ElFormItem>

        <ElFormItem :label="t('knowledge.settings.defaultThreshold')">
          <ElInput
            v-model.number="formData.score_threshold"
            type="number"
            :min="0"
            :max="1"
            :step="0.05"
            style="width: 100%"
          />
        </ElFormItem>

        <ElDivider content-position="left">
          <span class="text-sm font-semibold text-stone-700">
            {{ t('knowledge.settings.chunkSection') }}
          </span>
        </ElDivider>

        <ElFormItem :label="t('knowledge.settings.chunkSize')">
          <div
            class="flex items-center gap-2"
            style="width: 100%"
          >
            <ElInput
              v-model.number="formData.chunk_size"
              type="number"
              :min="100"
              :max="2000"
              :step="50"
              style="flex: 1"
            />
            <span class="text-xs text-stone-500 whitespace-nowrap">
              {{ t('knowledge.settings.tokens') }}
            </span>
          </div>
        </ElFormItem>

        <ElFormItem :label="t('knowledge.settings.chunkOverlap')">
          <div
            class="flex items-center gap-2"
            style="width: 100%"
          >
            <ElInput
              v-model.number="formData.chunk_overlap"
              type="number"
              :min="0"
              :max="200"
              :step="10"
              style="flex: 1"
            />
            <span class="text-xs text-stone-500 whitespace-nowrap">
              {{ t('knowledge.settings.tokens') }}
            </span>
          </div>
        </ElFormItem>

        <ElDivider content-position="left">
          <span class="text-sm font-semibold text-stone-700">
            {{ t('knowledge.settings.serverSection') }}
          </span>
        </ElDivider>

        <div
          v-if="serverInfo"
          class="space-y-2 text-sm text-stone-600"
        >
          <div class="flex items-center justify-between gap-2">
            <span>{{ t('knowledge.settings.rerankingMode') }}</span>
            <ElTag size="small">{{ serverInfo.reranking_mode }}</ElTag>
          </div>
          <div class="flex items-center justify-between gap-2">
            <span>{{ t('knowledge.settings.hybridWeights') }}</span>
            <ElTag size="small">
              {{ serverInfo.vector_weight }} / {{ serverInfo.keyword_weight }}
            </ElTag>
          </div>
          <div class="flex items-center justify-between gap-2">
            <span>{{ t('knowledge.settings.chunkingEngine') }}</span>
            <ElTag size="small">{{ serverInfo.chunking_engine }}</ElTag>
          </div>
          <div class="flex items-center justify-between gap-2">
            <span>{{ t('knowledge.settings.wikiCompile') }}</span>
            <ElTag
              size="small"
              :type="serverInfo.wiki_compile_enabled ? 'success' : 'info'"
            >
              {{
                serverInfo.wiki_compile_enabled
                  ? t('knowledge.settings.wikiEnabled')
                  : t('knowledge.settings.wikiDisabled')
              }}
            </ElTag>
          </div>
        </div>
      </ElForm>

      <div class="mt-6 flex justify-end gap-2">
        <ElButton @click="handleClose">
          {{ t('common.cancel') }}
        </ElButton>
        <ElButton
          type="primary"
          class="save-btn"
          :loading="saving"
          @click="handleSave"
        >
          {{ t('common.save') }}
        </ElButton>
      </div>
    </div>
  </ElDrawer>
</template>

<style scoped>
.settings-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.save-btn {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
  font-weight: 500;
}
</style>
