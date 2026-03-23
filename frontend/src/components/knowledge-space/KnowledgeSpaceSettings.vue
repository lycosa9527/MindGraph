<script setup lang="ts">
/**
 * KnowledgeSpaceSettings - Settings modal/drawer for RAG configuration
 * Swiss design styling
 */
import { ref } from 'vue'

import { ElButton, ElDivider, ElDrawer, ElForm, ElFormItem, ElInput, ElSelect } from 'element-plus'

import { useLanguage } from '@/composables/useLanguage'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const { t } = useLanguage()

const formData = ref({
  defaultRetrievalMethod: 'hybrid',
  defaultTopK: 5,
  defaultScoreThreshold: 0.0,
  chunkSize: 512,
  chunkOverlap: 50,
})

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

const handleSave = () => {
  // TODO: Implement settings save
  handleClose()
}
</script>

<template>
  <ElDrawer
    :model-value="visible"
    :title="t('knowledge.settings.title')"
    size="400px"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <div class="settings-content p-4">
      <ElForm
        :model="formData"
        label-width="140px"
        label-position="left"
      >
        <ElDivider content-position="left">
          <span class="text-sm font-semibold text-stone-700">
            {{ t('knowledge.settings.retrievalSection') }}
          </span>
        </ElDivider>

        <ElFormItem :label="t('knowledge.settings.defaultMethod')">
          <ElSelect
            v-model="formData.defaultRetrievalMethod"
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
            v-model="formData.defaultTopK"
            style="width: 100%"
          >
            <el-option
              v-for="i in [1, 3, 5, 10, 20]"
              :key="i"
              :label="i"
              :value="i"
            />
          </ElSelect>
        </ElFormItem>

        <ElFormItem :label="t('knowledge.settings.defaultThreshold')">
          <ElInput
            v-model.number="formData.defaultScoreThreshold"
            type="number"
            :min="0"
            :max="1"
            :step="0.1"
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
              v-model.number="formData.chunkSize"
              type="number"
              :min="100"
              :max="2000"
              :step="64"
              style="flex: 1"
            />
            <span class="text-xs text-stone-500 whitespace-nowrap">
              {{ t('knowledge.settings.characters') }}
            </span>
          </div>
        </ElFormItem>

        <ElFormItem :label="t('knowledge.settings.chunkOverlap')">
          <div
            class="flex items-center gap-2"
            style="width: 100%"
          >
            <ElInput
              v-model.number="formData.chunkOverlap"
              type="number"
              :min="0"
              :max="200"
              :step="10"
              style="flex: 1"
            />
            <span class="text-xs text-stone-500 whitespace-nowrap">
              {{ t('knowledge.settings.characters') }}
            </span>
          </div>
        </ElFormItem>
      </ElForm>

      <div class="mt-6 flex justify-end gap-2">
        <ElButton @click="handleClose">
          {{ t('common.cancel') }}
        </ElButton>
        <ElButton
          type="primary"
          class="save-btn"
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
