<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useWorkshopChatStore } from '@/stores/workshopChat'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  visible: boolean
  mode: 'rename' | 'move'
  topicId: number
  channelId: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const store = useWorkshopChatStore()
const { t } = useLanguage()

const newTitle = ref('')
const targetChannelId = ref<number | null>(null)
const saving = ref(false)

const currentTopic = computed(() =>
  store.topics.find(tp => tp.id === props.topicId),
)

const availableChannels = computed(() =>
  store.channels.filter(c => c.id !== props.channelId && c.is_joined),
)

watch(
  () => props.visible,
  (val) => {
    if (val && currentTopic.value) {
      newTitle.value = currentTopic.value.title
      targetChannelId.value = null
    }
  },
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
  <el-dialog
    :model-value="visible"
    :title="mode === 'rename' ? t('workshop.renameTopic') : t('workshop.moveTopic')"
    width="380px"
    @update:model-value="emit('update:visible', $event)"
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
        <el-select v-model="targetChannelId" class="w-full" :placeholder="t('workshop.selectTopic')">
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
      <el-button @click="emit('update:visible', false)">
        {{ t('workshop.dismiss') }}
      </el-button>
      <el-button
        type="primary"
        :loading="saving"
        :disabled="mode === 'rename' ? !newTitle.trim() : !targetChannelId"
        @click="handleSave"
      >
        {{ t('workshop.create') }}
      </el-button>
    </template>
  </el-dialog>
</template>
