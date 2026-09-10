<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Pencil } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useWorkshopChatStore } from '@/stores/workshopChat'

const props = defineProps<{
  visible: boolean
  mode: 'rename' | 'move'
  topicId: number
  channelId: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const open = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

const store = useWorkshopChatStore()
const { t } = useLanguage()

const newTitle = ref('')
const targetChannelId = ref<number | null>(null)
const saving = ref(false)

const currentTopic = computed(() => store.topics.find((tp) => tp.id === props.topicId))

const availableChannels = computed(() =>
  store.channels.filter((c) => c.id !== props.channelId && c.is_joined)
)

watch(
  () => props.visible,
  (val) => {
    if (val && currentTopic.value) {
      newTitle.value = currentTopic.value.title
      targetChannelId.value = null
    }
  }
)

async function handleSave(): Promise<void> {
  saving.value = true
  if (props.mode === 'rename') {
    await store.renameTopic(props.channelId, props.topicId, newTitle.value)
  } else if (props.mode === 'move' && targetChannelId.value) {
    await store.moveTopic(props.channelId, props.topicId, targetChannelId.value)
  }
  saving.value = false
  emit('update:visible', false)
}
</script>

<template>
  <SwissGlassDialog
    v-model="open"
    :ribbon="t('swissGlass.hero.topicEdit.ribbon')"
    :title="t('swissGlass.hero.topicEdit.title')"
    :line1="t('swissGlass.hero.topicEdit.line1')"
    :icon="Pencil"
    width="min(380px, 92vw)"
  >
    <div class="flex flex-col gap-3">
      <template v-if="mode === 'rename'">
        <el-input
          v-model="newTitle"
          :placeholder="t('workshop.topicTitlePlaceholder')"
          maxlength="200"
          show-word-limit
        />
      </template>

      <template v-if="mode === 'move'">
        <p class="text-xs text-stone-500 mb-1">
          {{ t('workshop.moveTopic') }}: {{ currentTopic?.title }}
        </p>
        <el-select
          v-model="targetChannelId"
          class="w-full"
          :placeholder="t('workshop.selectTopic')"
        >
          <el-option
            v-for="ch in availableChannels"
            :key="ch.id"
            :value="ch.id"
            :label="`${ch.avatar || '#'} ${ch.name}`"
          />
        </el-select>
      </template>
    </div>

    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="open = false"
        >
          {{ t('workshop.dismiss') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="saving || (mode === 'rename' ? !newTitle.trim() : !targetChannelId)"
          @click="handleSave"
        >
          {{ t('workshop.create') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
