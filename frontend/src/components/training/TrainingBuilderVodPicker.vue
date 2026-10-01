<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ElCheckbox, ElOption, ElSelect } from 'element-plus'

import { useLanguage } from '@/composables'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import type { TrainingCourseStep } from '@/types/training'
import {
  type TrainingVodFolder,
  type TrainingVodItem,
  fetchTrainingVodLibrary,
} from '@/utils/trainingVodApi'

const props = defineProps<{
  step: TrainingCourseStep
}>()

const emit = defineEmits<{
  video: [id: string | null]
  autoplay: [value: boolean]
}>()

const { t } = useLanguage()
const flags = useFeatureFlagsStore()
const folders = ref<TrainingVodFolder[]>([])
const items = ref<TrainingVodItem[]>([])
const folderId = ref('')
const loaded = ref(false)

const enabled = computed(() => flags.getFeatureVod())
const visibleItems = computed(() => {
  if (!folderId.value) return items.value
  if (folderId.value === 'none') return items.value.filter((item) => !item.folder_id)
  return items.value.filter((item) => item.folder_id === folderId.value)
})

function syncFolderFromStep(): void {
  const current = items.value.find((item) => item.id === props.step.vod_media_id)
  if (!current) return
  folderId.value = current.folder_id || 'none'
}

function onVideo(value: string | number | boolean): void {
  const next = String(value || '')
  emit('video', next || null)
  if (!next) emit('autoplay', false)
}

onMounted(async () => {
  if (!enabled.value) {
    await flags.fetchFlags()
  }
  if (!flags.getFeatureVod()) return
  try {
    const library = await fetchTrainingVodLibrary()
    folders.value = library.folders
    items.value = library.items
    syncFolderFromStep()
  } catch {
    folders.value = []
    items.value = []
  } finally {
    loaded.value = true
  }
})
</script>

<template>
  <div
    v-if="enabled"
    class="vod-picker"
  >
    <span class="vod-picker__label"><I18nText k="training.builder.vodLibrary" /></span>
    <ElSelect
      v-model="folderId"
      class="admin-swiss-select vod-picker__select"
      size="small"
      :placeholder="t('training.builder.vodFolder')"
    >
      <ElOption
        value=""
        :label="t('admin.vod.folderAll')"
      >
        <I18nText k="admin.vod.folderAll" />
      </ElOption>
      <ElOption
        value="none"
        :label="t('admin.vod.folderNone')"
      >
        <I18nText k="admin.vod.folderNone" />
      </ElOption>
      <ElOption
        v-for="folder in folders"
        :key="folder.id"
        :value="folder.id"
        :label="folder.name"
      />
    </ElSelect>
    <ElSelect
      class="admin-swiss-select vod-picker__select"
      size="small"
      :model-value="step.vod_media_id || ''"
      :placeholder="t('training.builder.vodVideo')"
      @change="onVideo"
    >
      <ElOption
        value=""
        :label="t('training.builder.vodNone')"
      >
        <I18nText k="training.builder.vodNone" />
      </ElOption>
      <ElOption
        v-for="item in visibleItems"
        :key="item.id"
        :value="item.id"
        :label="item.title"
      />
    </ElSelect>
    <label class="vod-picker__auto">
      <ElCheckbox
        :model-value="Boolean(step.vod_autoplay)"
        :disabled="!step.vod_media_id"
        @change="(value: boolean | string | number) => emit('autoplay', Boolean(value))"
      />
      <span><I18nText k="training.builder.vodAutoplay" /></span>
    </label>
    <span
      v-if="loaded && visibleItems.length === 0"
      class="vod-picker__empty"
    >
      <I18nText k="training.builder.vodEmpty" />
    </span>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped>
.vod-picker {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}
.vod-picker__label,
.vod-picker__empty {
  font-size: 0.75rem;
  color: #57534e;
}
.vod-picker__select {
  width: 9.5rem;
}
.vod-picker__auto {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: #44403c;
}
</style>
