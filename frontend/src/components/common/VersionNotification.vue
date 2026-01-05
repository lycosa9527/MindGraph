<script setup lang="ts">
/**
 * Version Update Notification
 * Shows a non-blocking notification when a new app version is available
 */
import { Refresh } from '@element-plus/icons-vue'

import { useLanguage, useVersionCheck } from '@/composables'

const { t } = useLanguage()
const { needsUpdate, currentVersion, serverVersion, forceRefresh, dismissUpdate } = useVersionCheck()
</script>

<template>
  <Transition name="slide-up">
    <div
      v-if="needsUpdate"
      class="version-notification"
    >
      <div class="version-notification__content">
        <div class="version-notification__icon">
          <el-icon
            :size="20"
            color="#409eff"
          >
            <Refresh />
          </el-icon>
        </div>
        <div class="version-notification__text">
          <span class="version-notification__message">
            {{ t('notification.newVersionAvailable') }}
          </span>
          <span class="version-notification__versions">
            {{ currentVersion }} → {{ serverVersion }}
          </span>
        </div>
        <div class="version-notification__actions">
          <button
            class="version-notification__btn version-notification__btn--primary"
            @click="forceRefresh"
          >
            {{ t('common.refresh') || 'Refresh' }}
          </button>
          <button
            class="version-notification__btn version-notification__btn--dismiss"
            @click="dismissUpdate"
          >
            &times;
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.version-notification {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  max-width: 400px;
}

.version-notification__content {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.dark .version-notification__content {
  background: #1f2937;
  border-color: #374151;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.version-notification__icon {
  flex-shrink: 0;
}

.version-notification__text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.version-notification__message {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.version-notification__versions {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.version-notification__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-notification__btn {
  border: none;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.version-notification__btn--primary {
  padding: 6px 14px;
  background: #409eff;
  color: white;
  border-radius: 4px;
}

.version-notification__btn--primary:hover {
  background: #66b1ff;
}

.version-notification__btn--dismiss {
  padding: 4px 8px;
  background: transparent;
  color: var(--el-text-color-secondary);
  font-size: 18px;
  line-height: 1;
}

.version-notification__btn--dismiss:hover {
  color: var(--el-text-color-primary);
}

/* Animation */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
