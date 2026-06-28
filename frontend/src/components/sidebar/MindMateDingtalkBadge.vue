<script setup lang="ts">
/**
 * Small pill badge for MindBot / DingTalk-sourced MindMate conversations.
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables'

const props = defineProps<{
  /** When omitted, badge is shown (caller gates visibility). */
  visible?: boolean
}>()

const { t } = useLanguage()

const show = computed(() => props.visible !== false)

const label = computed(() => t('sidebar.chatHistory.dingtalkBadge'))
const hint = computed(() => t('sidebar.chatHistory.dingtalkBadgeHint'))
</script>

<template>
  <span
    v-if="show"
    class="mindmate-dingtalk-badge"
    :title="hint"
    aria-hidden="true"
  >
    <svg
      class="mindmate-dingtalk-badge__icon"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M3.2 8.4c0-2.87 2.33-5.2 5.2-5.2.96 0 1.86.26 2.63.72L8.8 4.15a3.35 3.35 0 0 0-2.4-.98c-1.85 0-3.35 1.5-3.35 3.35 0 .67.2 1.29.54 1.81l-1.39 1.02a5.15 5.15 0 0 1-.8-2.95Z"
        fill="currentColor"
        opacity="0.85"
      />
      <path
        d="M12.8 7.6c0 2.87-2.33 5.2-5.2 5.2-.96 0-1.86-.26-2.63-.72l2.23-1.23a3.35 3.35 0 0 0 2.4.98c1.85 0 3.35-1.5 3.35-3.35 0-.67-.2-1.29-.54-1.81l1.39-1.02c.48.84.8 1.8.8 2.95Z"
        fill="currentColor"
      />
      <circle
        cx="8"
        cy="8"
        r="1.15"
        fill="currentColor"
        opacity="0.55"
      />
    </svg>
    <span class="mindmate-dingtalk-badge__label">{{ label }}</span>
  </span>
</template>

<style scoped>
.mindmate-dingtalk-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  flex-shrink: 0;
  max-width: 100%;
  padding: 1px 6px 1px 4px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.03em;
  line-height: 1.35;
  color: #0077e6;
  background: linear-gradient(145deg, #e8f4ff 0%, #f3faff 48%, #eef6ff 100%);
  border: 1px solid rgb(0 119 230 / 0.2);
  box-shadow:
    0 1px 2px rgb(0 119 230 / 0.1),
    inset 0 1px 0 rgb(255 255 255 / 0.85);
}

.mindmate-dingtalk-badge__icon {
  width: 11px;
  height: 11px;
  flex-shrink: 0;
}

.mindmate-dingtalk-badge__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
