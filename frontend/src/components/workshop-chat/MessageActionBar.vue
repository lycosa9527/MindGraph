<script setup lang="ts">
/**
 * MessageActionBar - Floating action bar that appears on message hover.
 *
 * Zulip-style: compact row of icon buttons positioned at the top-right
 * of the message row, visible only on hover via the parent's group class.
 */
import { ref } from 'vue'

import { Delete, Edit } from '@element-plus/icons-vue'

import { ChevronDown, ChevronUp, Link2, Quote, Smile, Star } from 'lucide-vue-next'

import { useLanguage } from '@/composables/useLanguage'

import EmojiPicker from './EmojiPicker.vue'

const { t } = useLanguage()

defineProps<{
  isOwn: boolean
  isStarred: boolean
  isCondensed: boolean
  /** Admin / school manager: delete others' messages (server enforces). */
  canModerate?: boolean
}>()

const emit = defineEmits<{
  addReaction: [emojiName: string, emojiCode: string]
  toggleStar: []
  quote: []
  copyLink: []
  edit: []
  delete: []
  toggleCondense: []
}>()

const showEmojiPicker = ref(false)

function handleEmojiSelect(name: string, code: string): void {
  showEmojiPicker.value = false
  emit('addReaction', name, code)
}

function handleCopyLink(): void {
  emit('copyLink')
}
</script>

<template>
  <div class="ws-action-bar">
    <!-- Add Reaction -->
    <el-popover
      :visible="showEmojiPicker"
      placement="bottom-end"
      :width="260"
      trigger="click"
      :show-arrow="false"
      @update:visible="showEmojiPicker = $event"
    >
      <template #reference>
        <button
          class="action-btn"
          :title="t('workshop.addReaction')"
          @click="showEmojiPicker = !showEmojiPicker"
        >
          <Smile :size="14" />
        </button>
      </template>
      <EmojiPicker @select="handleEmojiSelect" />
    </el-popover>

    <!-- Star -->
    <button
      class="action-btn"
      :class="{ 'action-btn--starred': isStarred }"
      :title="isStarred ? t('workshop.unstarMessage') : t('workshop.starMessage')"
      @click="emit('toggleStar')"
    >
      <Star
        :size="14"
        :fill="isStarred ? 'currentColor' : 'none'"
      />
    </button>

    <!-- Quote -->
    <button
      class="action-btn"
      :title="t('workshop.quoteMessage')"
      @click="emit('quote')"
    >
      <Quote :size="14" />
    </button>

    <!-- Copy Link -->
    <button
      class="action-btn"
      :title="t('workshop.copyLink')"
      @click="handleCopyLink"
    >
      <Link2 :size="14" />
    </button>

    <!-- Expand/Collapse -->
    <button
      class="action-btn"
      :title="isCondensed ? t('workshop.showMore') : t('workshop.showLess')"
      @click="emit('toggleCondense')"
    >
      <ChevronDown
        v-if="isCondensed"
        :size="14"
      />
      <ChevronUp
        v-else
        :size="14"
      />
    </button>

    <!-- Edit (own messages) -->
    <button
      v-if="isOwn"
      class="action-btn"
      title="Edit"
      @click="emit('edit')"
    >
      <el-icon :size="14"><Edit /></el-icon>
    </button>

    <!-- Delete (own or moderator) -->
    <button
      v-if="isOwn || canModerate"
      class="action-btn action-btn--danger"
      title="Delete"
      @click="emit('delete')"
    >
      <el-icon :size="14"><Delete /></el-icon>
    </button>
  </div>
</template>

<style scoped>
.ws-action-bar {
  display: flex;
  align-items: center;
  gap: 1px;
  padding: 2px 3px;
  background: hsl(0deg 0% 100%);
  border: 1px solid hsl(0deg 0% 84%);
  border-radius: 5px;
  box-shadow:
    0 2px 6px hsl(0deg 0% 0% / 10%),
    0 0 1px hsl(0deg 0% 0% / 6%);
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  background: none;
  border-radius: 4px;
  cursor: pointer;
  color: hsl(0deg 0% 48%);
  transition: all 120ms ease;
}

.action-btn:hover {
  background: hsl(228deg 20% 94%);
  color: hsl(228deg 40% 36%);
}

.action-btn--starred {
  color: hsl(45deg 92% 50%);
}

.action-btn--starred:hover {
  background: hsl(45deg 80% 94%);
  color: hsl(45deg 80% 42%);
}

.action-btn--danger {
  color: hsl(0deg 55% 52%);
}

.action-btn--danger:hover {
  color: hsl(0deg 65% 42%);
  background: hsl(0deg 70% 96%);
}
</style>
