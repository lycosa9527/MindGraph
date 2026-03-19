<script setup lang="ts">
/**
 * TopicCard - Card for a conversation topic within a lesson-study channel.
 * Shows title, description, message count, and creator.
 */
import { ref } from 'vue'

import { ChatLineSquare } from '@element-plus/icons-vue'
import { MoreVertical } from 'lucide-vue-next'

import TopicActionsPopover from './TopicActionsPopover.vue'
import { useLanguage } from '@/composables/useLanguage'
import type { ChatTopic } from '@/stores/workshopChat'

const { t } = useLanguage()

defineProps<{
  topic: ChatTopic
}>()

const emit = defineEmits<{
  click: [topicId: number]
  contextMenu: [topicId: number, event: MouseEvent]
  rename: [topicId: number]
  move: [topicId: number]
}>()

const showPopover = ref(false)
</script>

<template>
  <div
    class="topic-card group"
    :class="{ 'topic-card--muted': topic.visibility_policy === 'muted' }"
    @click="emit('click', topic.id)"
    @contextmenu.prevent="emit('contextMenu', topic.id, $event)"
  >
    <div class="topic-card__header">
      <h4 class="topic-card__title">{{ topic.title }}</h4>
      <div class="topic-card__actions">
        <TopicActionsPopover
          :topic="topic"
          :channel-id="topic.channel_id"
          :visible="showPopover"
          @update:visible="showPopover = $event"
          @rename="(id: number) => emit('rename', id)"
          @move="(id: number) => emit('move', id)"
        >
          <button class="topic-card__kebab" @click.stop>
            <MoreVertical :size="14" />
          </button>
        </TopicActionsPopover>
      </div>
    </div>

    <p v-if="topic.description" class="topic-card__desc">
      {{ topic.description }}
    </p>

    <div class="topic-card__meta">
      <span class="topic-card__meta-item">
        <el-icon :size="12"><ChatLineSquare /></el-icon>
        {{ topic.message_count }}
      </span>
    </div>

    <div class="topic-card__creator">
      {{ t('workshop.by') }} {{ topic.creator_name || t('workshop.unknown') }}
    </div>
  </div>
</template>

<style scoped>
.topic-card {
  border: 1px solid hsl(0deg 0% 0% / 10%);
  border-radius: 8px;
  padding: 14px 16px;
  background: hsl(0deg 0% 100%);
  cursor: pointer;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

.topic-card:hover {
  border-color: hsl(0deg 0% 0% / 16%);
  box-shadow: 0 2px 8px hsl(0deg 0% 0% / 6%);
}

.topic-card--muted {
  opacity: 0.55;
}

.topic-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.topic-card__title {
  font-size: 14px;
  font-weight: 600;
  color: hsl(0deg 0% 12%);
  line-height: 1.4;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 0;
  letter-spacing: -0.005em;
}

.topic-card__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.topic-card__kebab {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  border-radius: 4px;
  cursor: pointer;
  color: hsl(0deg 0% 55%);
  opacity: 0;
  transition: all 120ms ease;
}

.topic-card:hover .topic-card__kebab {
  opacity: 0.6;
}

.topic-card__kebab:hover {
  opacity: 1 !important;
  background: hsl(0deg 0% 0% / 6%);
  color: hsl(0deg 0% 30%);
}

.topic-card__desc {
  font-size: 12px;
  color: hsl(0deg 0% 42%);
  margin-top: 8px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.topic-card__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  font-size: 12px;
}

.topic-card__meta-item {
  display: flex;
  align-items: center;
  gap: 3px;
  color: hsl(0deg 0% 48%);
}

.topic-card__creator {
  margin-top: 8px;
  font-size: 11px;
  color: hsl(0deg 0% 52%);
}
</style>
