<script setup lang="ts">
/**
 * DebaterAvatar - Avatar image with nametag
 */
import { computed } from 'vue'

import type { DebateParticipant } from '@/stores/debateverse'

// Import avatar images
import qwenAvatar from '@/assets/qwen-avatar.png'
import deepseekAvatar from '@/assets/deepseek-avatar.png'
import doubaoAvatar from '@/assets/doubao-avatar.png'
import kimiAvatar from '@/assets/kimi-avatar.png'
import judgeAvatar from '@/assets/judge-avatar.png'
import userAvatar from '@/assets/user-avatar.png'

const props = defineProps<{
  participant: DebateParticipant
  isSpeaking?: boolean
}>()

// ============================================================================
// Computed
// ============================================================================

const avatarImage = computed(() => {
  // User avatar (when not AI)
  if (!props.participant.is_ai) {
    return userAvatar
  }

  // Judge avatar
  if (props.participant.role === 'judge') {
    return judgeAvatar
  }

  // LLM avatars based on model_id
  const avatarMap: Record<string, string> = {
    qwen: qwenAvatar,
    deepseek: deepseekAvatar,
    doubao: doubaoAvatar,
    kimi: kimiAvatar,
  }

  return avatarMap[props.participant.model_id || 'qwen'] || qwenAvatar
})

const avatarSize = 96
</script>

<template>
  <div
    class="debater-avatar-container flex flex-col items-center"
    :class="{ 'speaking': isSpeaking }"
  >
    <!-- Avatar Image -->
    <div class="relative">
      <img
        :src="avatarImage"
        :alt="participant.name"
        class="debater-avatar"
        :style="{ width: `${avatarSize}px`, height: `${avatarSize}px` }"
      />
      <!-- Speaking indicator ring -->
      <div
        v-if="isSpeaking"
        class="speaking-ring absolute inset-0 rounded-full border-2 border-blue-500 animate-pulse"
      />
    </div>

    <!-- Name Label -->
    <span class="text-xs font-medium text-gray-700 mt-1 text-center max-w-[80px] truncate">
      {{ participant.name }}
    </span>

    <!-- Role Label -->
    <span class="text-xs text-gray-500 mt-0.5">
      {{ participant.role }}
    </span>
  </div>
</template>

<style scoped>
.debater-avatar-container {
  transition: transform 0.2s ease;
}

.debater-avatar-container.speaking {
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}

.debater-avatar {
  border-radius: 8px;
  object-fit: cover;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
  transition: all 0.2s ease;
}

.debater-avatar-container.speaking .debater-avatar {
  filter: drop-shadow(0 2px 8px rgba(59, 130, 246, 0.4));
}

.speaking-ring {
  pointer-events: none;
  border-radius: 8px;
  animation: ring-pulse 1.5s ease-in-out infinite;
}

@keyframes ring-pulse {
  0%, 100% {
    opacity: 0.6;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.1);
  }
}
</style>
