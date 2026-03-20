<script setup lang="ts">
/**
 * MessageReactions - Reaction pills row with add-reaction button.
 *
 * Each pill shows an emoji and its count. Highlighted if the current user
 * has reacted. Clicking an existing pill toggles the current user's reaction.
 */
import { ref } from 'vue'

import { Plus } from '@element-plus/icons-vue'

import type { ReactionGroup } from '@/stores/workshopChat'

import EmojiPicker from './EmojiPicker.vue'

defineProps<{
  reactions: ReactionGroup[]
  messageId: number
}>()

const emit = defineEmits<{
  toggle: [messageId: number, emojiName: string, emojiCode: string]
}>()

const showPicker = ref(false)

function handlePillClick(reaction: ReactionGroup, messageId: number): void {
  emit('toggle', messageId, reaction.emoji_name, reaction.emoji_code)
}
</script>

<template>
  <div
    v-if="reactions.length > 0 || true"
    class="reaction-row"
    :data-reaction-msg-id="messageId"
  >
    <!-- Reaction pills -->
    <button
      v-for="reaction in reactions"
      :key="reaction.emoji_name"
      class="reaction-pill"
      :class="{ 'reaction-pill--reacted': reaction.reacted }"
      :title="reaction.emoji_name"
      @click="handlePillClick(reaction, messageId)"
    >
      <span class="reaction-pill__emoji">{{ reaction.emoji_code }}</span>
      <span class="reaction-pill__count">{{ reaction.count }}</span>
    </button>

    <!-- Add reaction button -->
    <el-popover
      :visible="showPicker"
      placement="bottom-start"
      :width="260"
      trigger="click"
      :show-arrow="false"
      @update:visible="showPicker = $event"
    >
      <template #reference>
        <button
          class="reaction-add-btn"
          @click="showPicker = !showPicker"
        >
          <el-icon :size="11"><Plus /></el-icon>
        </button>
      </template>
      <EmojiPicker
        @select="
          (name: string, code: string) => {
            showPicker = false
            emit('toggle', messageId, name, code)
          }
        "
      />
    </el-popover>
  </div>
</template>

<style scoped>
.reaction-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
}

.reaction-pill {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  font-size: 12px;
  border-radius: 12px;
  border: 1px solid hsl(0deg 0% 0% / 10%);
  background: hsl(0deg 0% 98%);
  color: hsl(0deg 0% 36%);
  cursor: pointer;
  transition: all 120ms ease;
}

.reaction-pill:hover {
  background: hsl(0deg 0% 95%);
  border-color: hsl(0deg 0% 0% / 16%);
}

.reaction-pill--reacted {
  background: hsl(228deg 60% 96%);
  border-color: hsl(228deg 50% 76%);
  color: hsl(228deg 50% 40%);
}

.reaction-pill--reacted:hover {
  background: hsl(228deg 60% 93%);
}

.reaction-pill__emoji {
  font-size: 14px;
  line-height: 1;
}

.reaction-pill__count {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.reaction-add-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px dashed hsl(0deg 0% 0% / 15%);
  background: none;
  color: hsl(0deg 0% 48%);
  cursor: pointer;
  transition: all 120ms ease;
}

.reaction-add-btn:hover {
  border-color: hsl(0deg 0% 0% / 25%);
  color: hsl(0deg 0% 28%);
  background: hsl(0deg 0% 0% / 3%);
}
</style>
