<script setup lang="ts">
/**
 * MaiteMentorChat — demo mentor conversation thread.
 */
import MaiteMathText from '@/components/maite/shared/MaiteMathText.vue'

import type { MaiteChatMessage } from '@/types/maite'

defineProps<{
  messages: MaiteChatMessage[]
}>()
</script>

<template>
  <div class="maite-mentor-chat">
    <div
      v-for="message in messages"
      :key="message.id"
      class="maite-mentor-chat__message"
      :class="`maite-mentor-chat__message--${message.role}`"
    >
      <MaiteMathText :text="message.content" tag="p" />
    </div>
  </div>
</template>

<style scoped>
.maite-mentor-chat {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 320px;
  overflow-y: auto;
}

.maite-mentor-chat__message {
  max-width: 85%;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.maite-mentor-chat__message p {
  margin: 0;
}

.maite-mentor-chat__message--user {
  align-self: flex-end;
  background: #667eea;
  color: #fff;
}

.maite-mentor-chat__message--assistant {
  align-self: flex-start;
  background: var(--el-fill-color-light, #f5f5f4);
  color: var(--el-text-color-primary, #1c1917);
}
</style>
