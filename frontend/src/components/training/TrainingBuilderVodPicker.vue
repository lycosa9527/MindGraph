<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ElCheckbox } from 'element-plus'

import { Clapperboard, Folder, Play, Video } from '@lucide/vue'

import TrainingBuilderPickButton from '@/components/training/TrainingBuilderPickButton.vue'
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
const folderOptions = computed(() => [
  { value: '', label: String(t('admin.vod.folderAll')) },
  { value: 'none', label: String(t('admin.vod.folderNone')) },
  ...folders.value.map((folder) => ({ value: folder.id, label: folder.name })),
])
const videoOptions = computed(() => [
  { value: '', label: String(t('training.builder.vodNone')) },
  ...visibleItems.value.map((item) => ({ value: item.id, label: item.title })),
])

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
    <span class="vod-picker__label">
      <Video
        :size="15"
        aria-hidden="true"
      />
      <I18nText k="training.builder.vodLibrary" />
    </span>
    <TrainingBuilderPickButton
      :model-value="folderId"
      :options="folderOptions"
      :ariaLabel="String(t('training.builder.vodFolder'))"
      @change="folderId = $event"
    >
      <template #icon>
        <Folder
          :size="15"
          aria-hidden="true"
        />
      </template>
    </TrainingBuilderPickButton>
    <TrainingBuilderPickButton
      :model-value="step.vod_media_id || ''"
      :options="videoOptions"
      :ariaLabel="String(t('training.builder.vodVideo'))"
      @change="onVideo"
    >
      <template #icon>
        <Clapperboard
          :size="15"
          aria-hidden="true"
        />
      </template>
    </TrainingBuilderPickButton>
    <label class="vod-picker__auto">
      <Play
        :size="15"
        aria-hidden="true"
      />
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
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: #57534e;
}
.vod-picker__auto {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: #44403c;
}
</style>
