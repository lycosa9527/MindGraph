<script setup lang="ts">
/**
 * KnowledgeSpaceSettings - Settings modal/drawer for RAG configuration
 * Swiss design styling
 */
import { ref } from 'vue'
import { ElDrawer, ElForm, ElFormItem, ElSelect, ElInput, ElButton, ElDivider } from 'element-plus'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const { isZh } = useLanguage()

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
    :title="isZh ? '知识库设置' : 'Knowledge Base Settings'"
    size="400px"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <div class="settings-content p-4">
      <ElForm :model="formData" label-width="140px" label-position="left">
        <ElDivider content-position="left">
          <span class="text-sm font-semibold text-stone-700">
            {{ isZh ? '检索设置' : 'Retrieval Settings' }}
          </span>
        </ElDivider>

        <ElFormItem :label="isZh ? '默认检索方法' : 'Default Retrieval Method'">
          <ElSelect v-model="formData.defaultRetrievalMethod" style="width: 100%">
            <el-option
              :label="isZh ? '混合检索' : 'Hybrid Search'"
              value="hybrid"
            />
            <el-option
              :label="isZh ? '语义检索' : 'Semantic Search'"
              value="semantic"
            />
            <el-option
              :label="isZh ? '关键词检索' : 'Keyword Search'"
              value="keyword"
            />
          </ElSelect>
        </ElFormItem>

        <ElFormItem :label="isZh ? '默认返回数量' : 'Default Top K'">
          <ElSelect v-model="formData.defaultTopK" style="width: 100%">
            <el-option :label="i" :value="i" v-for="i in [1, 3, 5, 10, 20]" :key="i" />
          </ElSelect>
        </ElFormItem>

        <ElFormItem :label="isZh ? '默认分数阈值' : 'Default Score Threshold'">
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
            {{ isZh ? '分块设置' : 'Chunking Settings' }}
          </span>
        </ElDivider>

        <ElFormItem :label="isZh ? '分块大小' : 'Chunk Size'">
          <div class="flex items-center gap-2" style="width: 100%">
            <ElInput
              v-model.number="formData.chunkSize"
              type="number"
              :min="100"
              :max="2000"
              :step="64"
              style="flex: 1"
            />
            <span class="text-xs text-stone-500 whitespace-nowrap">
              {{ isZh ? '字符数' : 'characters' }}
            </span>
          </div>
        </ElFormItem>

        <ElFormItem :label="isZh ? '分块重叠' : 'Chunk Overlap'">
          <div class="flex items-center gap-2" style="width: 100%">
            <ElInput
              v-model.number="formData.chunkOverlap"
              type="number"
              :min="0"
              :max="200"
              :step="10"
              style="flex: 1"
            />
            <span class="text-xs text-stone-500 whitespace-nowrap">
              {{ isZh ? '字符数' : 'characters' }}
            </span>
          </div>
        </ElFormItem>
      </ElForm>

      <div class="mt-6 flex justify-end gap-2">
        <ElButton @click="handleClose">
          {{ isZh ? '取消' : 'Cancel' }}
        </ElButton>
        <ElButton
          type="primary"
          class="save-btn"
          @click="handleSave"
        >
          {{ isZh ? '保存' : 'Save' }}
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
