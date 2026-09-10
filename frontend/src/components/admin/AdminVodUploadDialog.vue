<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { ElProgress } from 'element-plus'

import { Video } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage, useNotifications } from '@/composables'
import { uploadVodFile } from '@/composables/admin/uploadVodFile'

const props = defineProps<{
  modelValue: boolean
  organizationId?: number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  uploaded: []
}>()

const { t } = useLanguage()
const notify = useNotifications()

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const title = ref('')
const file = ref<File | null>(null)
const percent = ref(0)
const uploading = ref(false)

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      title.value = ''
      file.value = null
      percent.value = 0
      uploading.value = false
    }
  }
)

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const next = input.files?.[0] ?? null
  file.value = next
  if (next && !title.value.trim()) {
    title.value = next.name.replace(/\.[^.]+$/, '')
  }
}

function close(): void {
  if (uploading.value) {
    return
  }
  emit('update:modelValue', false)
}

async function submit(): Promise<void> {
  const chosen = file.value
  const name = title.value.trim()
  if (!chosen || !name) {
    notify.error(t('admin.vod.uploadFile'))
    return
  }
  uploading.value = true
  percent.value = 0
  try {
    await uploadVodFile({
      file: chosen,
      title: name,
      organizationId: props.organizationId,
      onProgress: (progress) => {
        percent.value = Math.round(progress.percent * 100)
      },
    })
    notify.success(t('admin.vod.uploadSuccess'))
    emit('uploaded')
    emit('update:modelValue', false)
  } catch {
    notify.error(t('admin.vod.uploadFailed'))
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <SwissGlassDialog
    v-model="open"
    :ribbon="t('swissGlass.hero.adminVod.ribbon')"
    :title="t('swissGlass.hero.adminVod.title')"
    :line1="t('swissGlass.hero.adminVod.line1')"
    :icon="Video"
    width="28rem"
    :close-on-click-modal="!uploading"
    @close="close"
  >
    <label class="vod-field">
      <span>{{ t('admin.vod.titleColumn') }}</span>
      <input
        v-model="title"
        type="text"
        class="vod-input"
        :disabled="uploading"
      />
    </label>
    <label class="vod-field">
      <span>{{ t('admin.vod.uploadFile') }}</span>
      <input
        type="file"
        accept="video/*"
        :disabled="uploading"
        @change="onFileChange"
      />
    </label>
    <ElProgress
      v-if="uploading"
      :percentage="percent"
      class="mt-3"
    />
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          :disabled="uploading"
          @click="close"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="uploading"
          @click="submit"
        >
          {{ t('admin.vod.upload') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.vod-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.85rem;
  font-size: 0.875rem;
}
.vod-input {
  border: 1px solid #d6d3d1;
  border-radius: 0.375rem;
  padding: 0.4rem 0.6rem;
}
</style>
